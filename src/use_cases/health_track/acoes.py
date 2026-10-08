"""Ações do Health Track (§15). Ver `models/health_track_acao_model.py`.

Quem cria, edita e conclui é quem preenche o Health Track do projeto
(diretoria de projetos ou gerente da frente), checado na rota. Ler é de
quem tem a caixa.
"""

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.health_track_pilar_model import HealthTrackPilarModel
from src.models.projeto_model import ProjetoModel
from src.repositories.health_track_acao_repository import HealthTrackAcaoRepository
from src.use_cases.health_track.notificar_acoes import notificar_acao_atribuida, notificar_acao_concluida
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc, hoje_local


class AcaoRequest(BaseModel):
    problema: str = Field(min_length=3, max_length=1000)
    proxima_acao: str = Field(min_length=3, max_length=1000)
    responsavel_id: Optional[int] = None
    prazo: Optional[date] = None
    pilar_id: Optional[int] = None


class _Base:
    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackAcaoRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def serializar(self, acao, nomes: Dict[int, str], pilares: Dict[int, str], projetos: Dict[int, str]) -> dict:
        hoje = hoje_local()
        return {
            "id": acao.id,
            "projeto_id": acao.projeto_id,
            "projeto_nome": projetos.get(acao.projeto_id),
            "pilar_id": acao.pilar_id,
            "pilar_nome": pilares.get(acao.pilar_id) if acao.pilar_id else None,
            "problema": acao.problema,
            "proxima_acao": acao.proxima_acao,
            "responsavel_id": acao.responsavel_id,
            "responsavel_nome": nomes.get(acao.responsavel_id) if acao.responsavel_id else None,
            "prazo": acao.prazo,
            "atrasada": acao.concluida_em is None and acao.prazo is not None and acao.prazo < hoje,
            "concluida_em": acao.concluida_em,
            "concluida_por_nome": nomes.get(acao.concluida_por) if acao.concluida_por else None,
            "criado_por_nome": nomes.get(acao.criado_por) if acao.criado_por else None,
            "criado_em": acao.criado_em,
        }

    def serializar_varias(self, acoes: List) -> List[dict]:
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}
        pilares = {p.id: p.nome for p in self.db.query(HealthTrackPilarModel)}
        ids = {a.projeto_id for a in acoes}
        projetos = {
            p.id: p.nome for p in self.db.query(ProjetoModel).filter(ProjetoModel.id.in_(ids or [-1]))
        }
        return [self.serializar(a, nomes, pilares, projetos) for a in acoes]

    def _validar(self, request: AcaoRequest) -> None:
        if request.responsavel_id is not None and not self.usuario_repo.get_by_id(request.responsavel_id):
            raise RegraDeNegocioError("Responsável não encontrado.")
        if request.pilar_id is not None and not self.db.get(HealthTrackPilarModel, request.pilar_id):
            raise RegraDeNegocioError("Pilar não encontrado.")

    def _nome(self, usuario_id: Optional[int]) -> Optional[str]:
        u = self.usuario_repo.get_by_id(usuario_id) if usuario_id else None
        return u.nome if u else None

    def _nome_projeto(self, projeto_id: int) -> str:
        p = self.db.get(ProjetoModel, projeto_id)
        return p.nome if p else f"Projeto {projeto_id}"

    def _ou_erro(self, acao_id: int, projeto_id: int):
        acao = self.repository.get_by_id(acao_id)
        if not acao or acao.projeto_id != projeto_id:
            raise RegraDeNegocioError("Ação não encontrada.")
        return acao


class ListAcoesDoProjetoUseCase(_Base):
    def execute(self, projeto_id: int) -> List[dict]:
        return self.serializar_varias(self.repository.get_by_projeto(projeto_id))


class ListAcoesAbertasUseCase(_Base):
    """Todas as abertas da carteira: a seção "projetos que exigem atenção"."""

    def execute(self) -> List[dict]:
        return self.serializar_varias(self.repository.get_abertas())


class CriarAcaoUseCase(_Base):
    def execute(self, projeto_id: int, request: AcaoRequest, current_user) -> dict:
        self._validar(request)
        acao = self.repository.create(
            projeto_id=projeto_id,
            pilar_id=request.pilar_id,
            problema=request.problema.strip(),
            proxima_acao=request.proxima_acao.strip(),
            responsavel_id=request.responsavel_id,
            prazo=request.prazo,
            criado_por=getattr(current_user, "id", None),
            criado_em=agora_utc(),
        )
        notificar_acao_atribuida(self.db, acao, self._nome_projeto(projeto_id), self._nome(acao.criado_por))
        return self.serializar_varias([acao])[0]


class EditarAcaoUseCase(_Base):
    def execute(self, projeto_id: int, acao_id: int, request: AcaoRequest) -> dict:
        acao = self._ou_erro(acao_id, projeto_id)
        self._validar(request)
        responsavel_antes = acao.responsavel_id
        acao = self.repository.update(
            acao.id,
            pilar_id=request.pilar_id,
            problema=request.problema.strip(),
            proxima_acao=request.proxima_acao.strip(),
            responsavel_id=request.responsavel_id,
            prazo=request.prazo,
        )
        # Só a pessoa NOVA é avisada; a chave de dedup já segura o resto.
        if acao.responsavel_id and acao.responsavel_id != responsavel_antes:
            notificar_acao_atribuida(self.db, acao, self._nome_projeto(projeto_id), self._nome(acao.criado_por))
        return self.serializar_varias([acao])[0]


class ConcluirAcaoUseCase(_Base):
    """Concluir, ou reabrir (`concluida=False`) se foi sem querer."""

    def execute(self, projeto_id: int, acao_id: int, concluida: bool, current_user) -> dict:
        acao = self._ou_erro(acao_id, projeto_id)
        quem = getattr(current_user, "id", None)
        acao = self.repository.update(
            acao.id,
            concluida_em=agora_utc() if concluida else None,
            concluida_por=quem if concluida else None,
        )
        if concluida:
            notificar_acao_concluida(self.db, acao, self._nome_projeto(projeto_id), quem, self._nome(quem))
        return self.serializar_varias([acao])[0]


class ListMinhasAcoesUseCase(_Base):
    """O que foi atribuído a MIM, em qualquer projeto. Não passa pela caixa
    do Health Track: o responsável costuma ser coordenador, que não a tem.
    Leva só a ação, nunca as cores."""

    def execute(self, usuario_id: int) -> List[dict]:
        return self.serializar_varias(self.repository.get_por_responsavel(usuario_id))


class ConcluirMinhaAcaoUseCase(_Base):
    """O responsável marca a própria ação como feita (ou desfaz)."""

    def execute(self, acao_id: int, concluida: bool, current_user) -> dict:
        acao = self.repository.get_by_id(acao_id)
        if not acao or acao.responsavel_id != getattr(current_user, "id", None):
            raise RegraDeNegocioError("Esta ação não está atribuída a você.")
        quem = current_user.id
        acao = self.repository.update(
            acao.id,
            concluida_em=agora_utc() if concluida else None,
            concluida_por=quem if concluida else None,
        )
        if concluida:
            notificar_acao_concluida(self.db, acao, self._nome_projeto(acao.projeto_id), quem, self._nome(quem))
        return self.serializar_varias([acao])[0]


class ApagarAcaoUseCase(_Base):
    def execute(self, projeto_id: int, acao_id: int) -> None:
        self._ou_erro(acao_id, projeto_id)
        self.repository.delete(acao_id)

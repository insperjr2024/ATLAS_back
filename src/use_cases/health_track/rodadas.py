"""Rodadas do Health Track. Ver `models/health_track_rodada_model.py`.

Abrir congela os projetos EM ACOMPANHAMENTO (`EM_ACOMPANHAMENTO`, a mesma
régua do bloco de cima do mapa). Cada um começa pendente; avaliar o
projeto (qualquer avaliação registrada enquanto a rodada está aberta) o
marca como avaliado, e quem não vai ser avaliado leva uma justificativa.
Concluir só com zero pendentes: a rodada existe justamente pra nada ficar
pra trás sem alguém dizer por quê.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.health_track_rodada_repository import (
    HealthTrackRodadaProjetoRepository,
    HealthTrackRodadaRepository,
)
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.health_track.notificar_acoes import notificar_rodada_aberta
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc

#: As etapas em que o projeto está sendo tocado e, portanto, entra na rodada.
#: Pausado entra de propósito: a diretoria justifica ("está parado") em vez
#: de o sistema decidir por ela. Pós-banca (envio TEP, ajustes, finalizado)
#: fica no bloco de encerrados do mapa e fora da rodada; antes da venda
#: fechar não há equipe pra avaliar.
EM_ACOMPANHAMENTO = ("ambientacao", "em_andamento", "validacao_bancas", "pausado")
POS_BANCA = ("envio_tep", "periodo_ajustes", "finalizado")


class JustificarRequest(BaseModel):
    justificativa: str = Field(min_length=3, max_length=1000)


class _Base:
    def __init__(self, db: Session):
        self.db = db
        self.rodada_repo = HealthTrackRodadaRepository(db)
        self.item_repo = HealthTrackRodadaProjetoRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def _nomes(self) -> Dict[int, str]:
        return {u.id: u.nome for u in self.usuario_repo.get_all()}

    def serializar(self, rodada, nomes: Optional[Dict[int, str]] = None) -> dict:
        nomes = nomes if nomes is not None else self._nomes()
        itens = self.item_repo.get_by_rodada(rodada.id)
        projetos = {
            p.id: p
            for p in self.db.query(ProjetoModel).filter(ProjetoModel.id.in_([i.projeto_id for i in itens] or [-1]))
        }
        linhas = []
        for item in itens:
            projeto = projetos.get(item.projeto_id)
            linhas.append(
                {
                    "projeto_id": item.projeto_id,
                    "projeto_nome": projeto.nome if projeto else f"Projeto {item.projeto_id}",
                    "projeto_status": projeto.status if projeto else None,
                    "situacao": item.situacao,
                    "justificativa": item.justificativa,
                    "resolvido_em": item.resolvido_em,
                    "resolvido_por_nome": nomes.get(item.resolvido_por) if item.resolvido_por else None,
                }
            )
        # Pendentes primeiro, depois por nome: é a fila de quem está rodando.
        linhas.sort(key=lambda l: (l["situacao"] != "pendente", l["projeto_nome"].casefold()))
        contagem = {s: sum(1 for l in linhas if l["situacao"] == s) for s in ("pendente", "avaliada", "justificada")}
        return {
            "id": rodada.id,
            "aberta_em": rodada.aberta_em,
            "aberta_por_nome": nomes.get(rodada.aberta_por) if rodada.aberta_por else None,
            "concluida_em": rodada.concluida_em,
            "concluida_por_nome": nomes.get(rodada.concluida_por) if rodada.concluida_por else None,
            "total": len(linhas),
            **contagem,
            "projetos": linhas,
        }


class GetRodadaAtualUseCase(_Base):
    def execute(self) -> Optional[dict]:
        rodada = self.rodada_repo.get_aberta()
        return self.serializar(rodada) if rodada else None


class ListRodadasUseCase(_Base):
    def execute(self) -> List[dict]:
        nomes = self._nomes()
        return [self.serializar(r, nomes) for r in self.rodada_repo.get_todas()]


class AbrirRodadaUseCase(_Base):
    def execute(self, current_user) -> dict:
        if self.rodada_repo.get_aberta():
            raise RegraDeNegocioError("Já existe uma rodada em andamento. Conclua antes de abrir outra.")
        projetos = (
            self.db.query(ProjetoModel)
            .filter(ProjetoModel.arquivado_em.is_(None))
            .filter(ProjetoModel.institucional.is_(False))
            .filter(ProjetoModel.status.in_(EM_ACOMPANHAMENTO))
            .all()
        )
        if not projetos:
            raise RegraDeNegocioError("Não há projeto em acompanhamento pra avaliar.")
        quem = getattr(current_user, "id", None)
        rodada = self.rodada_repo.create(aberta_em=agora_utc(), aberta_por=quem)
        self.item_repo.bulk_create([{"rodada_id": rodada.id, "projeto_id": p.id} for p in projetos])
        abriu = self.usuario_repo.get_by_id(quem) if quem else None
        notificar_rodada_aberta(self.db, rodada, len(projetos), quem, abriu.nome if abriu else None)
        return self.serializar(rodada)


class JustificarProjetoUseCase(_Base):
    """Marca que o projeto NÃO vai ser avaliado nesta rodada e por quê. Vale
    pra pendente e pra trocar o texto de uma justificativa; um projeto já
    avaliado não precisa de justificativa."""

    def execute(self, rodada_id: int, projeto_id: int, request: JustificarRequest, current_user) -> dict:
        rodada = self._aberta_ou_erro(rodada_id)
        item = self.item_repo.get_item(rodada.id, projeto_id)
        if not item:
            raise RegraDeNegocioError("Este projeto não está nesta rodada.")
        if item.situacao == "avaliada":
            raise RegraDeNegocioError("Este projeto já foi avaliado nesta rodada.")
        self.item_repo.update(
            item.id,
            situacao="justificada",
            justificativa=request.justificativa.strip(),
            resolvido_em=agora_utc(),
            resolvido_por=getattr(current_user, "id", None),
        )
        return self.serializar(rodada)

    def _aberta_ou_erro(self, rodada_id: int):
        rodada = self.rodada_repo.get_by_id(rodada_id)
        if not rodada:
            raise RegraDeNegocioError("Rodada não encontrada.")
        if rodada.concluida_em is not None:
            raise RegraDeNegocioError("Esta rodada já foi concluída.")
        return rodada


class DesfazerJustificativaUseCase(_Base):
    """Volta o projeto pra pendente: a diretoria mudou de ideia e vai avaliar."""

    def execute(self, rodada_id: int, projeto_id: int) -> dict:
        rodada = JustificarProjetoUseCase(self.db)._aberta_ou_erro(rodada_id)
        item = self.item_repo.get_item(rodada.id, projeto_id)
        if not item or item.situacao != "justificada":
            raise RegraDeNegocioError("Só uma justificativa pode ser desfeita.")
        self.item_repo.update(item.id, situacao="pendente", justificativa=None, resolvido_em=None, resolvido_por=None)
        return self.serializar(rodada)


class ConcluirRodadaUseCase(_Base):
    def execute(self, rodada_id: int, current_user) -> dict:
        rodada = JustificarProjetoUseCase(self.db)._aberta_ou_erro(rodada_id)
        pendentes = [i for i in self.item_repo.get_by_rodada(rodada.id) if i.situacao == "pendente"]
        if pendentes:
            n = len(pendentes)
            raise RegraDeNegocioError(
                f"Ainda há {n} projeto{'s' if n > 1 else ''} pendente{'s' if n > 1 else ''}: "
                "avalie ou justifique antes de concluir."
            )
        rodada = self.rodada_repo.update(
            rodada.id, concluida_em=agora_utc(), concluida_por=getattr(current_user, "id", None)
        )
        return self.serializar(rodada)


def marcar_avaliado_na_rodada(db: Session, projeto_id: int, usuario_id: Optional[int]) -> None:
    """Chamado por quem registra uma avaliação: se há rodada aberta com este
    projeto, ele deixa de estar pendente (ou justificado) e vira avaliado.
    Sem rodada aberta, não faz nada: avaliar fora de rodada continua livre."""
    rodada_repo = HealthTrackRodadaRepository(db)
    rodada = rodada_repo.get_aberta()
    if not rodada:
        return
    item_repo = HealthTrackRodadaProjetoRepository(db)
    item = item_repo.get_item(rodada.id, projeto_id)
    if not item or item.situacao == "avaliada":
        return
    item_repo.update(
        item.id, situacao="avaliada", justificativa=None, resolvido_em=agora_utc(), resolvido_por=usuario_id
    )

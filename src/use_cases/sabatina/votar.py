"""A cédula: o que cada membro vê e o voto em si."""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.sabatina_repository import (
    SabatinaCandidatoRepository,
    SabatinaEleicaoRepository,
    SabatinaPesoRepository,
    SabatinaVotoRepository,
)
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc
from src.utils.sabatina_apuracao import peso_do_usuario


class VotoRequest(BaseModel):
    #: `None` é voto em branco.
    candidato_id: Optional[int] = None


class MinhasEleicoesUseCase:
    """As eleições abertas em que eu voto (ou em que sou candidato, pra saber
    por que não voto). É o que decide se a aba "Sabatina" aparece."""

    def __init__(self, db: Session):
        self.eleicao_repo = SabatinaEleicaoRepository(db)
        self.candidato_repo = SabatinaCandidatoRepository(db)
        self.voto_repo = SabatinaVotoRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.peso_repo = SabatinaPesoRepository(db)

    def execute(self, usuario_id: int) -> list[dict]:
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}
        # O peso com que a pessoa votaria AGORA, pela mesma conta do voto, pra
        # cédula mostrar e ela conferir antes de votar (a pedido, 2026-10-07).
        eu = self.usuario_repo.get_by_id(usuario_id)
        meu_peso = peso_do_usuario(
            getattr(eu, "posicao", None), getattr(eu, "cargo_extra", None), self.peso_repo.como_dict()
        )
        saida = []
        for eleicao in self.eleicao_repo.get_abertas():
            candidatos = self.candidato_repo.get_by_eleicao(eleicao.id)
            sou_candidato = any(c.usuario_id == usuario_id for c in candidatos)
            posso_votar = usuario_id in (eleicao.eleitores_ids or [])
            if not sou_candidato and not posso_votar:
                continue
            meu_voto = self.voto_repo.get_do_eleitor(eleicao.id, usuario_id)
            saida.append(
                {
                    "id": eleicao.id,
                    "nome": eleicao.nome,
                    "aberta_em": eleicao.aberta_em,
                    "candidatos": [
                        {"id": c.id, "usuario_id": c.usuario_id, "nome": nomes.get(c.usuario_id, f"Usuário {c.usuario_id}")}
                        for c in candidatos
                    ],
                    "sou_candidato": sou_candidato,
                    "ja_votei": meu_voto is not None,
                    "meu_peso": meu_peso,
                }
            )
        return saida


class VotarUseCase:
    def __init__(self, db: Session):
        self.eleicao_repo = SabatinaEleicaoRepository(db)
        self.candidato_repo = SabatinaCandidatoRepository(db)
        self.voto_repo = SabatinaVotoRepository(db)
        self.peso_repo = SabatinaPesoRepository(db)

    def execute(self, eleicao_id: int, request: VotoRequest, current_user) -> dict:
        eleicao = self.eleicao_repo.get_by_id(eleicao_id)
        if not eleicao:
            raise RegraDeNegocioError("Eleição não encontrada")
        if eleicao.status != "aberta":
            raise RegraDeNegocioError("Esta eleição não está aberta pra votos.")
        if current_user.id not in (eleicao.eleitores_ids or []):
            raise RegraDeNegocioError("Você não vota nesta eleição.")
        if self.voto_repo.get_do_eleitor(eleicao_id, current_user.id):
            raise RegraDeNegocioError("Você já votou nesta eleição.")
        if request.candidato_id is not None:
            candidato = self.candidato_repo.get_by_id(request.candidato_id)
            if not candidato or candidato.eleicao_id != eleicao_id:
                raise RegraDeNegocioError("Candidato não pertence a esta eleição.")

        posicao = getattr(current_user, "posicao", None)
        cargo_extra = getattr(current_user, "cargo_extra", None)
        voto = self.voto_repo.create(
            eleicao_id=eleicao_id,
            eleitor_id=current_user.id,
            candidato_id=request.candidato_id,
            posicao=posicao or "",
            peso=peso_do_usuario(posicao, cargo_extra, self.peso_repo.como_dict()),
            # No mesmo relógio de `aberta_em` (UTC naive), e não no `now()` do
            # banco: a corrida da diretoria põe os dois no mesmo eixo, e um
            # banco local em America/Sao_Paulo deslocava os votos em 3 h.
            criado_em=agora_utc(),
        )
        return {"id": voto.id, "eleicao_id": eleicao_id, "em_branco": request.candidato_id is None}

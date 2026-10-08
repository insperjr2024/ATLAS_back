from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.health_track_avaliacao_model import CORES_HEALTH_TRACK
from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.repositories.health_track_pilar_repository import HealthTrackPilarRepository
from src.use_cases.health_track.rodadas import marcar_avaliado_na_rodada
from src.use_cases.health_track.serializar import nomes_para, serializar_avaliacao
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc


class CorPilarRequest(BaseModel):
    pilar_id: int
    cor: Literal[CORES_HEALTH_TRACK]
    comentario: Optional[str] = None


class RegistrarAvaliacaoRequest(BaseModel):
    avaliacoes: List[CorPilarRequest]


class RegistrarAvaliacaoUseCase:
    """Um preenchimento do Health Track: a cor de TODOS os pilares ativos.

    **Todos, e só os ativos.** Faltar pilar deixaria o ciclo incompleto, e
    o status geral (§4) seria calculado com menos cores do
    que a regra espera. A lista do que é exigido vem do banco, não do código —
    se a diretoria desativar um pilar, ele deixa de ser cobrado aqui sem
    mudar uma linha.

    Nunca sobrescreve: cada chamada grava linhas novas com o mesmo
    `avaliado_em`, que é o que marca o ciclo.

    O acesso (quem pode preencher) é checado na rota, antes daqui.
    """

    def __init__(self, db: Session):
        self.db = db
        self.pilar_repo = HealthTrackPilarRepository(db)
        self.repository = HealthTrackAvaliacaoRepository(db)

    def execute(self, projeto_id: int, request: RegistrarAvaliacaoRequest, current_user) -> list[dict]:
        ativos = {p.id: p for p in self.pilar_repo.get_ativos()}
        enviados = [a.pilar_id for a in request.avaliacoes]

        repetidos = sorted({pid for pid in enviados if enviados.count(pid) > 1})
        if repetidos:
            raise RegraDeNegocioError(f"Pilar enviado mais de uma vez: {_ids(repetidos)}")

        desconhecidos = sorted(set(enviados) - set(ativos))
        if desconhecidos:
            raise RegraDeNegocioError(f"Pilar inexistente ou desativado: {_ids(desconhecidos)}")

        faltando = [p.nome for p in ativos.values() if p.id not in set(enviados)]
        if faltando:
            raise RegraDeNegocioError(f"Falta avaliar: {', '.join(faltando)}")

        agora = agora_utc()
        criadas = self.repository.registrar_ciclo([
            {
                "projeto_id": projeto_id,
                "pilar_id": a.pilar_id,
                "cor": a.cor,
                # Comentário em branco é ausência de comentário, não um texto vazio.
                "comentario": (a.comentario or "").strip() or None,
                "avaliado_por": current_user.id,
                "avaliado_em": agora,
            }
            for a in request.avaliacoes
        ])

        # Se há rodada aberta com este projeto, ele sai de pendente.
        marcar_avaliado_na_rodada(self.db, projeto_id, getattr(current_user, "id", None))

        # Na ordem de exibição, como a tela desenha os pilares.
        criadas.sort(key=lambda a: (ativos[a.pilar_id].ordem, a.pilar_id))
        pilares, usuarios = nomes_para(self.db, criadas)
        return [serializar_avaliacao(a, pilares, usuarios) for a in criadas]


def _ids(ids) -> str:
    return ", ".join(str(i) for i in ids)

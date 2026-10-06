from typing import Iterable

from sqlalchemy.orm import Session

from src.models.health_track_pilar_model import HealthTrackPilarModel
from src.models.usuario_model import UsuarioModel


def serializar_pilar(pilar) -> dict:
    return {
        "id": pilar.id,
        "nome": pilar.nome,
        "descricao": pilar.descricao,
        "ordem": pilar.ordem,
        "ativo": pilar.ativo,
    }


def serializar_avaliacao(avaliacao, pilares: dict, usuarios: dict) -> dict:
    pilar = pilares.get(avaliacao.pilar_id)
    avaliador = usuarios.get(avaliacao.avaliado_por)
    return {
        "id": avaliacao.id,
        "projeto_id": avaliacao.projeto_id,
        "pilar_id": avaliacao.pilar_id,
        "pilar_nome": pilar.nome if pilar else None,
        "cor": avaliacao.cor,
        "comentario": avaliacao.comentario,
        "avaliado_por": avaliacao.avaliado_por,
        "avaliado_por_nome": avaliador.nome if avaliador else None,
        "avaliado_em": avaliacao.avaliado_em,
    }


def nomes_para(db: Session, avaliacoes: Iterable) -> tuple[dict, dict]:
    """Os pilares e avaliadores citados, numa query de cada. Inclui pilar
    inativo: no histórico ele continua precisando de nome."""
    avaliacoes = list(avaliacoes)
    pilar_ids = {a.pilar_id for a in avaliacoes}
    usuario_ids = {a.avaliado_por for a in avaliacoes}
    pilares = {
        p.id: p
        for p in db.query(HealthTrackPilarModel).filter(HealthTrackPilarModel.id.in_(pilar_ids or [-1]))
    }
    usuarios = {
        u.id: u
        for u in db.query(UsuarioModel).filter(UsuarioModel.id.in_(usuario_ids or [-1]))
    }
    return pilares, usuarios

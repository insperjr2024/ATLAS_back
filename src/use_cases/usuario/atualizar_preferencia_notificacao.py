"""Quais tipos de notificação a própria pessoa recebe por e-mail (2026-08-17).

Só os tipos de `TIPOS_NOTIFICACAO_OPCIONAIS` entram aqui — os fixos nunca
aparecem na tela e continuam saindo sempre, ver `enviar_email_notificacao.py`.
"""

from typing import List

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.notificacao_model import TIPOS_NOTIFICACAO_OPCIONAIS
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError


class AtualizarPreferenciaNotificacaoRequest(BaseModel):
    #: Os tipos que a pessoa NÃO quer mais por e-mail. Lista vazia = tudo
    #: ligado, o padrão de quem nunca mexeu nisso.
    desativadas: List[str]


class AtualizarPreferenciaNotificacaoUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int, request: AtualizarPreferenciaNotificacaoRequest):
        # Recusa tipo fixo ou inexistente na lista: aceitar caladamente
        # deixaria alguém desligar sem saber que não tinha efeito nenhum
        # (fixo) ou guardar lixo que nunca mais é lido (tipo inexistente).
        invalidos = set(request.desativadas) - TIPOS_NOTIFICACAO_OPCIONAIS
        if invalidos:
            raise RegraDeNegocioError(
                f"Estes tipos não podem ser desativados: {', '.join(sorted(invalidos))}."
            )

        atualizado = self.repository.update(
            usuario_id, notificacoes_email_desativadas=list(dict.fromkeys(request.desativadas))
        )
        if not atualizado:
            return None
        return {"notificacoes_email_desativadas": atualizado.notificacoes_email_desativadas}

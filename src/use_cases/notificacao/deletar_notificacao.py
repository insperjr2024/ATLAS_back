"""Excluir/limpar notificações já lidas.

Só `origem="evento"` pode ser apagado. Uma linha de `origem="condicao"` não
é a notificação, é a marcação de leitura dela (ver `notificacao_model.py`):
apagá-la faria o alerta voltar a contar no sino mesmo com o problema
continuando resolvido, o oposto do que "limpar" deveria fazer. Por isso o
front nem oferece excluir para item de condição.
"""

from sqlalchemy.orm import Session

from src.repositories.notificacao_repository import NotificacaoRepository
from src.utils.exceptions import RegraDeNegocioError


class ExcluirNotificacaoUseCase:
    def __init__(self, db: Session):
        self.repository = NotificacaoRepository(db)

    def execute(self, current_user, notificacao_id: int) -> None:
        linha = self.repository.get_evento_do_usuario(notificacao_id, current_user.id)
        if not linha:
            # Mesma resposta para "não existe", "é de outra pessoa" e "é
            # condição": diferenciar deixaria varrer ids alheios.
            raise RegraDeNegocioError("Notificação não encontrada.", codigo="nao_encontrada")
        if linha.lida_em is None:
            raise RegraDeNegocioError("Marque como lida antes de excluir.")
        self.repository.excluir(linha)


class LimparNotificacoesLidasUseCase:
    def __init__(self, db: Session):
        self.repository = NotificacaoRepository(db)

    def execute(self, current_user) -> dict:
        return {"excluidas": self.repository.limpar_eventos_lidos(current_user.id)}

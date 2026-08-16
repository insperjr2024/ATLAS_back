"""A porta de entrada das notificações de BANCAS (§8).

Existia antes da fusão com a central do §6.6 e continua existindo por um
motivo prático: os quatro pontos que a chamam (push automático, abertura e
confirmação de troca, prazo de avaliação) não precisam saber nada sobre
`tipo`, `origem` ou `chave_dedup`. Eles têm uma frase pronta e um
destinatário — e é só isso que esta função pede. Mantê-la evita reescrever
quatro use cases de bancas para caber num formato que não é problema deles.

⚠ **Sem dedup por padrão, ao contrário do resto da central.** Um aviso de
banca é fato novo a cada vez: duas trocas abertas para a mesma banca são duas
notícias, não uma repetida. Por isso, quando `chave` não vem, cada chamada
gera a sua e a linha é sempre criada. Quem quiser o comportamento anti-spam
do §6.6 passa `chave` explicitamente.
"""

from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from src.use_cases.notificacao.registrar_notificacao import registrar

#: Usado quando quem chama não diz o tipo. Genérico de propósito: melhor uma
#: notificação com rótulo vago do que uma exceção derrubando a confirmação de
#: uma troca.
TIPO_PADRAO = "banca_aviso"


def notificar(
    db: Session,
    usuario_id: int,
    mensagem: str,
    banca_id: Optional[int] = None,
    tipo: str = TIPO_PADRAO,
    chave: Optional[str] = None,
) -> None:
    """Cria a linha da notificação. A listagem é de quem lê (`GET /notificacoes`)."""
    registrar(
        db,
        usuario_id=usuario_id,
        tipo=tipo,
        titulo=mensagem,
        # `banca_id` viaja no payload, não em coluna própria: uma FK por
        # domínio faria a tabela ganhar uma coluna a cada área que passasse a
        # notificar.
        payload={"banca_id": banca_id} if banca_id else None,
        rota=f"/bancas?banca={banca_id}" if banca_id else None,
        chave_dedup=chave or f"{tipo}:{uuid4()}",
    )

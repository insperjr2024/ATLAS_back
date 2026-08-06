"""A central de notificações do §6.6 — hoje só o canal in-app.

🔐 Nenhuma rota aceita `usuario_id`: o destinatário é sempre o do token. Não é
economia de parâmetro — é o que impede alguém de ler o sino dos outros, e por
tabela de descobrir projetos que não enxerga.

`/contagem` existe separada porque é ela que o sino chama em polling (~60s) e
não precisa carregar tarefa, banca nem escopo de projeto nenhum quando o
número é a única coisa que muda na tela.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.notificacao.listar_notificacoes import ListarNotificacoesUseCase
from src.use_cases.notificacao.marcar_lida import (
    MarcarLidaRequest,
    MarcarLidaUseCase,
    MarcarTodasLidasUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(
    prefix="/notificacoes", tags=["notificacoes"], dependencies=[Depends(get_current_user)]
)


@router.get("")
def listar(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ListarNotificacoesUseCase(db).execute(current_user)


@router.get("/contagem")
def contagem(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"nao_lidas": ListarNotificacoesUseCase(db).execute(current_user)["nao_lidas"]}


@router.patch("/lida")
def marcar_lida(request: MarcarLidaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Aceita `id` (evento) ou `chave` (condição) — ver `marcar_lida.py`.

    404, e não 422: id de outra pessoa e chave inventada caem os dois aqui, e
    a mesma resposta para os dois é de propósito — distingui-los deixaria
    varrer ids alheios pela diferença de status.
    """
    try:
        return MarcarLidaUseCase(db).execute(current_user, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/marcar-todas-lidas")
def marcar_todas_lidas(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return MarcarTodasLidasUseCase(db).execute(current_user)

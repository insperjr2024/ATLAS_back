"""Notificação push (Web Push): ativar e desativar num aparelho, e testar.

Qualquer pessoa logada usa, pra si mesma. Nenhuma rota aceita `usuario_id`:
a inscrição é sempre de quem está no token. Ver
`use_cases/notificacao/enviar_push_notificacao.py`.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config.config import get_settings
from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.push_inscricao_repository import PushInscricaoRepository
from src.use_cases.notificacao.enviar_push_notificacao import enviar_push, push_configurado

router = APIRouter(prefix="/push", tags=["push"], dependencies=[Depends(get_current_user)])


class ChavesInscricao(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class InscricaoRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)
    keys: ChavesInscricao
    user_agent: Optional[str] = Field(default=None, max_length=300)


class CancelarRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)


@router.get("/chave-publica")
def chave_publica():
    """Nula quando o servidor não tem push configurado: o front esconde a opção."""
    return {"chave": get_settings().VAPID_PUBLIC_KEY or None}


@router.post("/inscricoes", status_code=201)
def inscrever(request: InscricaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not push_configurado():
        raise HTTPException(status_code=409, detail="Notificação no celular não está configurada no servidor.")
    if not request.endpoint.startswith("https://"):
        raise HTTPException(status_code=422, detail="Inscrição inválida.")
    PushInscricaoRepository(db).salvar(
        usuario_id=current_user.id,
        endpoint=request.endpoint,
        p256dh=request.keys.p256dh,
        auth=request.keys.auth,
        user_agent=request.user_agent,
    )
    return {"ok": True}


@router.delete("/inscricoes")
def cancelar(request: CancelarRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Só apaga se o aparelho for de quem pediu."""
    PushInscricaoRepository(db).remover_por_endpoint(request.endpoint, usuario_id=current_user.id)
    return {"ok": True}


@router.post("/teste")
def teste(current_user=Depends(get_current_user)):
    """Manda um aviso de teste pros aparelhos de quem pediu, na hora (não
    enfileira: a pessoa está olhando e quer saber se chegou)."""
    if not push_configurado():
        raise HTTPException(status_code=409, detail="Notificação no celular não está configurada no servidor.")
    entregues = enviar_push(
        usuario_id=current_user.id,
        tipo="teste",
        titulo="Notificações do ATLAS ativadas",
        corpo="É assim que os avisos vão aparecer neste aparelho.",
        rota="/notificacoes",
    )
    return {"entregues": entregues}

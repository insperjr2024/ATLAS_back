"""Comunicados manuais (2026-10-11, a pedido): a diretoria escolhe um recorte
de pessoas e manda sino + e-mail. Ver `use_cases/comunicado/enviar_comunicado.py`.

O router inteiro exige a caixa `pode_enviar_comunicados`, que nasce marcada
pros tres cargos de diretoria. Quem usa e a aba Comunicados (grupo Sistema).

A previa e POST, nao GET, porque o filtro e um objeto (listas de ids, de
posicoes) e nao cabe bem em query string.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_pode_enviar_comunicados
from src.use_cases.comunicado.enviar_comunicado import (
    ApagarComunicadoUseCase,
    ComunicadoRequest,
    EnviarComunicadoUseCase,
    FiltroComunicado,
    ListarComunicadosUseCase,
    ResolverDestinatariosUseCase,
)
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(
    prefix="/comunicados",
    tags=["comunicados"],
    dependencies=[Depends(require_pode_enviar_comunicados)],
)


@router.get("")
def historico(db: Session = Depends(get_db)):
    """Os disparos já feitos, do mais recente pro mais antigo."""
    return ListarComunicadosUseCase(db).execute()


@router.post("/destinatarios")
def previa_destinatarios(filtro: FiltroComunicado, db: Session = Depends(get_db)):
    try:
        return ResolverDestinatariosUseCase(db).execute(filtro)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.post("", status_code=201)
def enviar(
    request: ComunicadoRequest,
    current_user=Depends(require_pode_enviar_comunicados),
    db: Session = Depends(get_db),
):
    try:
        return EnviarComunicadoUseCase(db).execute(request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.delete("/{comunicado_id}")
def apagar(comunicado_id: str, db: Session = Depends(get_db)):
    """Tira do histórico e do sino de quem recebeu. E-mail enviado não volta."""
    try:
        return {"apagadas": ApagarComunicadoUseCase(db).execute(comunicado_id)}
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)

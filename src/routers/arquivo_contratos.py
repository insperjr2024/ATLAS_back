"""Arquivo de contratos: a pasta compartilhada. Ver `models/arquivo_contratos_model.py`.

Tudo aqui exige a caixa `pode_acessar_arquivo_contratos`.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_pode_acessar_arquivo_contratos
from src.use_cases.arquivo_contratos.itens import (
    ApagarItemUseCase,
    BaixarItemUseCase,
    EditarItemRequest,
    EditarItemUseCase,
    ImportarItemUseCase,
    SubstituirItemUseCase,
)
from src.use_cases.arquivo_contratos.pastas import (
    ApagarPastaUseCase,
    BuscarUseCase,
    CriarPastaUseCase,
    EditarPastaUseCase,
    GetPastaUseCase,
    PastaRequest,
    RenomearPastaRequest,
)
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(
    prefix="/arquivo-contratos",
    tags=["arquivo de contratos"],
    dependencies=[Depends(require_pode_acessar_arquivo_contratos)],
)


def _regra(fn):
    try:
        return fn()
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/pastas")
def raiz(db: Session = Depends(get_db)):
    return GetPastaUseCase(db).execute(None)


@router.get("/busca")
def buscar(q: str = "", db: Session = Depends(get_db)):
    return BuscarUseCase(db).execute(q)


@router.get("/pastas/{pasta_id}")
def pasta(pasta_id: int, db: Session = Depends(get_db)):
    return _regra(lambda: GetPastaUseCase(db).execute(pasta_id))


@router.post("/pastas", status_code=201)
def criar_pasta(
    request: PastaRequest, usuario=Depends(require_pode_acessar_arquivo_contratos), db: Session = Depends(get_db)
):
    return _regra(lambda: CriarPastaUseCase(db).execute(request, usuario.id))


@router.patch("/pastas/{pasta_id}")
def editar_pasta(pasta_id: int, request: RenomearPastaRequest, db: Session = Depends(get_db)):
    return _regra(lambda: EditarPastaUseCase(db).execute(pasta_id, request))


@router.delete("/pastas/{pasta_id}", status_code=204)
def apagar_pasta(pasta_id: int, recursivo: bool = False, db: Session = Depends(get_db)):
    _regra(lambda: ApagarPastaUseCase(db).execute(pasta_id, recursivo))
    return None


@router.post("/pastas/{pasta_id}/itens", status_code=201)
async def importar_item(
    pasta_id: int,
    arquivo: UploadFile = File(...),
    nome: Optional[str] = None,
    usuario=Depends(require_pode_acessar_arquivo_contratos),
    db: Session = Depends(get_db),
):
    conteudo = await arquivo.read()
    return _regra(
        lambda: ImportarItemUseCase(db).execute(
            pasta_id, conteudo, nome or arquivo.filename or "", arquivo.content_type, usuario.id
        )
    )


@router.get("/itens/{item_id}/arquivo")
def baixar_item(item_id: int, db: Session = Depends(get_db)):
    try:
        conteudo, nome, mime = BaixarItemUseCase(db).execute(item_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=404, detail=str(e))
    nome_ascii = nome.encode("ascii", "ignore").decode() or "arquivo"
    return Response(
        content=conteudo,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{nome_ascii}"'},
    )


@router.patch("/itens/{item_id}")
def editar_item(item_id: int, request: EditarItemRequest, db: Session = Depends(get_db)):
    return _regra(lambda: EditarItemUseCase(db).execute(item_id, request))


@router.put("/itens/{item_id}/arquivo")
async def substituir_item(item_id: int, arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    return _regra(lambda: SubstituirItemUseCase(db).execute(item_id, conteudo, arquivo.filename or "", arquivo.content_type))


@router.delete("/itens/{item_id}", status_code=204)
def apagar_item(item_id: int, db: Session = Depends(get_db)):
    _regra(lambda: ApagarItemUseCase(db).execute(item_id))
    return None

"""Institucional: o que a diretoria publica no SITE da Insper Jr.

Por enquanto só os ex-membros em destaque (2026-10-09, a pedido); a aba foi
feita pra receber outras seções do site depois. Ver `models/ex_membro_model.py`.

Dois routers, de propósito:

- `router` — tudo que escreve, mais a listagem completa (inclui ocultos).
  Exige a caixa `pode_acessar_institucional`, que nasce marcada só pra os
  três cargos de diretoria.
- `router_publico` — SÓ leitura, sem login, só o que está publicado. É o que
  o site institucional chama; quem visita o site não tem conta aqui. Mesma
  família de `auth.router_publico` e `aprovacao_contratual.router_publico`.
  Não recebe corpo, não filtra por parâmetro, não devolve nada além do que
  `serializar_publico` lista. `Cache-Control` curto: o site é lido muito mais
  do que a lista muda.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_pode_acessar_institucional
from src.use_cases.institucional.ex_membros import (
    FOTO_MIME,
    ApagarExMembroUseCase,
    AtualizarFotoUseCase,
    CriarExMembroUseCase,
    EditarExMembroUseCase,
    ExMembroRequest,
    GetFotoUseCase,
    ImportarIniciaisUseCase,
    ListarPublicadosUseCase,
    ListarTodosUseCase,
    PublicarExMembroUseCase,
    RemoverFotoUseCase,
    ReordenarExMembrosUseCase,
    ReordenarRequest,
)
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(
    prefix="/institucional",
    tags=["institucional"],
    dependencies=[Depends(require_pode_acessar_institucional)],
)
router_publico = APIRouter(prefix="/publico", tags=["institucional (público)"])

#: Curto: o site busca a lista com `cache: "no-store"` (uma edição no ATLAS
#: aparece no próximo carregamento da página); este header só vale pra
#: algum proxy/CDN no caminho.
CACHE_LISTA = "public, max-age=60"
#: A URL da foto carrega `foto_versao`, então pode ficar cacheada por muito
#: tempo: trocar a foto troca a URL.
CACHE_FOTO = "public, max-age=2592000, immutable"


def _regra(fn):
    try:
        return fn()
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


# ---------------------------------------------------------------- público (o site)

@router_publico.get("/ex-membros")
def listar_publicados(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = CACHE_LISTA
    return ListarPublicadosUseCase(db).execute()


@router_publico.get("/ex-membros/{ex_membro_id}/foto")
def foto_publica(ex_membro_id: int, db: Session = Depends(get_db)):
    try:
        conteudo = GetFotoUseCase(db).execute(ex_membro_id, apenas_publicado=True)
    except RegraDeNegocioError:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    return Response(content=conteudo, media_type=FOTO_MIME, headers={"Cache-Control": CACHE_FOTO})


# ---------------------------------------------------------------- aba Institucional

@router.get("/ex-membros")
def listar_todos(db: Session = Depends(get_db)):
    return ListarTodosUseCase(db).execute()


@router.post("/ex-membros", status_code=201)
def criar(
    request: ExMembroRequest,
    usuario=Depends(require_pode_acessar_institucional),
    db: Session = Depends(get_db),
):
    return _regra(lambda: CriarExMembroUseCase(db).execute(request, usuario.id))


@router.put("/ex-membros/ordem")
def reordenar(request: ReordenarRequest, db: Session = Depends(get_db)):
    return _regra(lambda: ReordenarExMembrosUseCase(db).execute(request))


@router.post("/ex-membros/importar-iniciais")
def importar_iniciais(usuario=Depends(require_pode_acessar_institucional), db: Session = Depends(get_db)):
    return _regra(lambda: ImportarIniciaisUseCase(db).execute(usuario.id))


@router.put("/ex-membros/{ex_membro_id}")
def editar(ex_membro_id: int, request: ExMembroRequest, db: Session = Depends(get_db)):
    return _regra(lambda: EditarExMembroUseCase(db).execute(ex_membro_id, request))


class PublicarRequest(BaseModel):
    publicado: bool


@router.patch("/ex-membros/{ex_membro_id}/publicado")
def publicar(ex_membro_id: int, request: PublicarRequest, db: Session = Depends(get_db)):
    return _regra(lambda: PublicarExMembroUseCase(db).execute(ex_membro_id, request.publicado))


@router.delete("/ex-membros/{ex_membro_id}", status_code=204)
def apagar(ex_membro_id: int, db: Session = Depends(get_db)):
    _regra(lambda: ApagarExMembroUseCase(db).execute(ex_membro_id))
    return Response(status_code=204)


@router.get("/ex-membros/{ex_membro_id}/foto")
def foto_admin(ex_membro_id: int, db: Session = Depends(get_db)):
    """A mesma foto da rota pública, mas também de quem está oculto — é o
    preview da aba. Sem cache longo: aqui a URL não carrega a versão."""
    try:
        conteudo = GetFotoUseCase(db).execute(ex_membro_id, apenas_publicado=False)
    except RegraDeNegocioError:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    return Response(content=conteudo, media_type=FOTO_MIME, headers={"Cache-Control": "private, no-cache"})


@router.put("/ex-membros/{ex_membro_id}/foto")
def atualizar_foto(ex_membro_id: int, arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = arquivo.file.read()
    return _regra(lambda: AtualizarFotoUseCase(db).execute(ex_membro_id, conteudo))


@router.delete("/ex-membros/{ex_membro_id}/foto")
def remover_foto(ex_membro_id: int, db: Session = Depends(get_db)):
    return _regra(lambda: RemoverFotoUseCase(db).execute(ex_membro_id))

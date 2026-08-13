"""Prioridade 2 — formulário versionado por semestre, perguntas, avaliações e notas."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    require_pode_definir_cronograma,
    require_diretor,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.avaliacao.create_avaliacao import CreateAvaliacaoUseCase, CreateAvaliacaoRequest
from src.use_cases.avaliacao.get_avaliacao import GetAvaliacaoUseCase, ListAvaliacoesUseCase
from src.use_cases.avaliacao.get_avaliacoes_pendentes import GetAvaliacoesPendentesUseCase
from src.use_cases.avaliacao.submeter_avaliacao import (
    SubmeterAvaliacaoRequest,
    SubmeterAvaliacaoUseCase,
)
from src.use_cases.avaliacao.update_avaliacao import (
    UpdateAvaliacaoUseCase,
    UpdateAvaliacaoRequest,
    DeleteAvaliacaoUseCase,
)
from src.use_cases.avaliacao_nota.create_avaliacao_nota import CreateAvaliacaoNotaUseCase, CreateAvaliacaoNotaRequest
from src.use_cases.avaliacao_nota.get_avaliacao_nota import GetAvaliacaoNotaUseCase, ListAvaliacoesNotasUseCase
from src.use_cases.avaliacao_nota.update_avaliacao_nota import (
    UpdateAvaliacaoNotaUseCase,
    UpdateAvaliacaoNotaRequest,
    DeleteAvaliacaoNotaUseCase,
)
from src.use_cases.formulario.create_nova_versao_formulario import (
    CreateNovaVersaoFormularioUseCase,
    CreateNovaVersaoFormularioRequest,
)
from src.use_cases.formulario.get_formulario import GetFormularioUseCase, ListFormulariosUseCase
from src.use_cases.formulario.get_formulario_ativo import GetFormularioAtivoUseCase
from src.use_cases.formulario.update_formulario import (
    UpdateFormularioUseCase,
    UpdateFormularioRequest,
    DeleteFormularioUseCase,
)
from src.use_cases.pergunta.get_pergunta import GetPerguntaUseCase, ListPerguntasUseCase
from src.use_cases.pergunta.update_pergunta import UpdatePerguntaUseCase, UpdatePerguntaRequest, DeletePerguntaUseCase
from src.utils.exceptions import RegraDeNegocioError, ResourceInUseError

router = APIRouter(tags=["avaliações"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------- formulários
# ⚠️ /formularios/ativo precisa vir ANTES de /formularios/{id}, senão o FastAPI
# casa "ativo" como path param e devolve 422.

@router.get("/formularios/ativo")
def get_formulario_ativo(db: Session = Depends(get_db)):
    result = GetFormularioAtivoUseCase(db).execute()
    if not result:
        raise HTTPException(status_code=404, detail="Nenhum formulário ativo encontrado")
    return result


@router.post("/formularios/nova-versao")
def create_nova_versao_formulario(request: CreateNovaVersaoFormularioRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    try:
        return CreateNovaVersaoFormularioUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/formularios")
def list_formularios(db: Session = Depends(get_db)):
    return ListFormulariosUseCase(db).execute()


@router.get("/formularios/{formulario_id}")
def get_formulario(formulario_id: int, db: Session = Depends(get_db)):
    result = GetFormularioUseCase(db).execute(formulario_id)
    if not result:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return result


@router.patch("/formularios/{formulario_id}")
def update_formulario(formulario_id: int, request: UpdateFormularioRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    result = UpdateFormularioUseCase(db).execute(formulario_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return result


@router.delete("/formularios/{formulario_id}", status_code=204)
def delete_formulario(formulario_id: int, _=Depends(require_diretor), db: Session = Depends(get_db)):
    try:
        deleted = DeleteFormularioUseCase(db).execute(formulario_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este formulário")
    if not deleted:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return None


# ---------------------------------------------------------------- perguntas

@router.get("/perguntas")
def list_perguntas(db: Session = Depends(get_db)):
    return ListPerguntasUseCase(db).execute()


@router.get("/perguntas/{pergunta_id}")
def get_pergunta(pergunta_id: int, db: Session = Depends(get_db)):
    result = GetPerguntaUseCase(db).execute(pergunta_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return result


@router.patch("/perguntas/{pergunta_id}")
def update_pergunta(pergunta_id: int, request: UpdatePerguntaRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    result = UpdatePerguntaUseCase(db).execute(pergunta_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return result


@router.delete("/perguntas/{pergunta_id}", status_code=204)
def delete_pergunta(pergunta_id: int, _=Depends(require_diretor), db: Session = Depends(get_db)):
    try:
        deleted = DeletePerguntaUseCase(db).execute(pergunta_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta pergunta")
    if not deleted:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return None


# ---------------------------------------------------------------- avaliações

@router.post("/avaliacoes")
def create_avaliacao(request: CreateAvaliacaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return CreateAvaliacaoUseCase(db).execute(request, avaliador_id=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/avaliacoes-pendentes")
def get_avaliacoes_pendentes(_=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    return GetAvaliacoesPendentesUseCase(db).execute()


@router.get("/avaliacoes")
def list_avaliacoes(db: Session = Depends(get_db)):
    return ListAvaliacoesUseCase(db).execute()


@router.get("/avaliacoes/{avaliacao_id}")
def get_avaliacao(avaliacao_id: int, db: Session = Depends(get_db)):
    result = GetAvaliacaoUseCase(db).execute(avaliacao_id)
    if not result:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result


@router.post("/avaliacoes/{avaliacao_id}/submeter")
def submeter_avaliacao(
    avaliacao_id: int,
    request: SubmeterAvaliacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """⭐ Enviar a avaliação — com o VOTO que decide a banca (§8).

    Rota própria porque submeter é uma AÇÃO com pré-condições (voto presente,
    banca realizada, prazo aberto, não reenviar), e não a edição de um campo.
    O `PATCH` ao lado é um passthrough genérico; pendurar a regra nele a
    deixaria contornável.

    A resposta traz a apuração para a tela dizer na hora se aquele voto fechou
    a banca ("3 de 4 votaram") em vez de mandar a pessoa recarregar.
    """
    try:
        result = SubmeterAvaliacaoUseCase(db).execute(avaliacao_id, request, current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result


@router.patch("/avaliacoes/{avaliacao_id}")
def update_avaliacao(avaliacao_id: int, request: UpdateAvaliacaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    existente = GetAvaliacaoUseCase(db).execute(avaliacao_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    if existente["avaliador_id"] != current_user.id and not current_user.posicao == "diretor":
        raise HTTPException(status_code=403, detail="Você só pode editar suas próprias avaliações")
    # ⚠ A SUBMISSÃO tem porta própria (`POST /avaliacoes/{id}/submeter`), que
    # exige o voto e dispara a apuração. Deixar esta rota genérica virar o
    # status seria um caminho paralelo sem nenhuma dessas regras — a avaliação
    # entraria como submetida sem voto e ficaria fora da conta para sempre.
    if getattr(request, "status", None) == "submetida":
        raise HTTPException(
            status_code=422,
            detail="Use POST /avaliacoes/{id}/submeter para enviar — é lá que o voto entra",
        )
    # 🔒 Voto dado é voto dado: uma avaliação SUBMETIDA não muda mais de banca
    # nem volta a rascunho.
    #
    # ⚠ Os dois vetores que isto fecha, e ambos apareceram no teste ponta a
    # ponta: trocar o `banca_id` levava o voto para a apuração de OUTRA banca,
    # de um projeto que o votante nem enxerga; e voltar o status para
    # `rascunho` retirava o voto da urna depois de contado — a diretoria podia
    # desfazer o voto alheio, porque esta rota também aceita quem é diretor.
    #
    # A trava de verdade está na apuração, que só conta quem tem candidatura.
    # Esta aqui é a que preserva o REGISTRO: sem ela, o histórico da avaliação
    # mentiria mesmo com a conta certa.
    if existente["status"] == "submetida":
        proibidos = [
            campo
            for campo in ("banca_id", "status", "submetida_em")
            if campo in request.dict(exclude_unset=True)
        ]
        if proibidos:
            raise HTTPException(
                status_code=422,
                detail="Esta avaliação já foi enviada e não pode mais ser alterada",
            )
    result = UpdateAvaliacaoUseCase(db).execute(avaliacao_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result


@router.delete("/avaliacoes/{avaliacao_id}", status_code=204)
def delete_avaliacao(avaliacao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    existente = GetAvaliacaoUseCase(db).execute(avaliacao_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    if existente["avaliador_id"] != current_user.id and not current_user.posicao == "diretor":
        raise HTTPException(status_code=403, detail="Você só pode remover suas próprias avaliações")
    try:
        deleted = DeleteAvaliacaoUseCase(db).execute(avaliacao_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta avaliação")
    if not deleted:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return None


# ---------------------------------------------------------------- notas

@router.post("/avaliacoes-notas")
def create_avaliacao_nota(request: CreateAvaliacaoNotaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    avaliacao = GetAvaliacaoUseCase(db).execute(request.avaliacao_id)
    if not avaliacao:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    if avaliacao["avaliador_id"] != current_user.id and not current_user.posicao == "diretor":
        raise HTTPException(status_code=403, detail="Você só pode adicionar notas às suas próprias avaliações")
    try:
        return CreateAvaliacaoNotaUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/avaliacoes-notas")
def list_avaliacoes_notas(db: Session = Depends(get_db)):
    return ListAvaliacoesNotasUseCase(db).execute()


@router.get("/avaliacoes-notas/{avaliacao_nota_id}")
def get_avaliacao_nota(avaliacao_nota_id: int, db: Session = Depends(get_db)):
    result = GetAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id)
    if not result:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    return result


@router.patch("/avaliacoes-notas/{avaliacao_nota_id}")
def update_avaliacao_nota(avaliacao_nota_id: int, request: UpdateAvaliacaoNotaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    nota_existente = GetAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id)
    if not nota_existente:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    avaliacao = GetAvaliacaoUseCase(db).execute(nota_existente["avaliacao_id"])
    if not avaliacao or (avaliacao["avaliador_id"] != current_user.id and not current_user.posicao == "diretor"):
        raise HTTPException(status_code=403, detail="Você só pode editar notas das suas próprias avaliações")
    try:
        result = UpdateAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    return result


@router.delete("/avaliacoes-notas/{avaliacao_nota_id}", status_code=204)
def delete_avaliacao_nota(avaliacao_nota_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    nota_existente = GetAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id)
    if not nota_existente:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    avaliacao = GetAvaliacaoUseCase(db).execute(nota_existente["avaliacao_id"])
    if not avaliacao or (avaliacao["avaliador_id"] != current_user.id and not current_user.posicao == "diretor"):
        raise HTTPException(status_code=403, detail="Você só pode remover notas das suas próprias avaliações")
    try:
        deleted = DeleteAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta nota")
    if not deleted:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    return None

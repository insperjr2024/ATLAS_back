"""A grade de aulas do próprio membro (§11)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.grade_horaria.grade_horaria import (
    FAIXAS_INSPER,
    GradeHorariaUseCase,
    SalvarGradeRequest,
)
from src.utils.exceptions import RegraDeNegocioError

# Sem guarda de permissão: é área de todo mundo, sobre os próprios dados. O id do
# usuário vem sempre do token — nenhuma rota aceita "grade de outra pessoa".
router = APIRouter(tags=["grade-horaria"], dependencies=[Depends(get_current_user)])


@router.get("/grade-horaria/faixas")
def listar_faixas():
    """As 6 faixas do Insper, para a tela desenhar o quadro.

    Vem do backend em vez de estar fixa no front porque é a mesma lista que
    valida a gravação — duas cópias sairiam do ar uma da outra no dia em que
    entrar curso com horário diferente.
    """
    return [
        {"hora_inicio": inicio.strftime("%H:%M"), "hora_fim": fim.strftime("%H:%M")}
        for inicio, fim in FAIXAS_INSPER
    ]


@router.get("/grade-horaria/compatibilidade")
def compatibilidade(
    usuario_ids: List[int] = Query(default=[]),
    semestre_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Em que faixas todos os escolhidos estão livres ao mesmo tempo (§11).

    Serve a tela de montar equipe: quem escolhe o time precisa saber se ele
    consegue se reunir antes de fechar a escolha, não depois.

    Devolve só o cruzamento — nunca a grade individual de ninguém. Quem quer
    montar equipe não precisa saber a que horas cada um tem aula.
    """
    try:
        return GradeHorariaUseCase(db).compatibilidade(usuario_ids, semestre_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/grade-horaria")
def minha_grade(
    semestre_id: Optional[int] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GradeHorariaUseCase(db).listar(current_user.id, semestre_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/grade-horaria")
def salvar_grade(
    request: SalvarGradeRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Substitui a grade inteira pelo estado final do quadro.

    Lista vazia é gravação válida: significa "não tenho aula em horário
    nenhum", e é assim que a pessoa limpa a grade.
    """
    try:
        return GradeHorariaUseCase(db).salvar(current_user.id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))

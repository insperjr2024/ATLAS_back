from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.cargo_repository import CargoRepository


def usuario_tem_permissao(current_user, db: Session, campo: str) -> bool:
    cargo = CargoRepository(db).get_by_id(current_user.cargo_id)
    return bool(cargo and getattr(cargo, campo, False))


def _exigir_permissao(current_user, db: Session, campo: str, mensagem: str):
    if not usuario_tem_permissao(current_user, db, campo):
        raise HTTPException(status_code=403, detail=mensagem)
    return current_user


def require_pode_definir_formulario(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_definir_formulario",
                              "Apenas o Diretor de Projetos pode editar o formulário")


def require_pode_agendar_banca(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_agendar_banca",
                              "Você não tem permissão para gerenciar bancas")


def require_pode_gerenciar_cargos(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_gerenciar_cargos",
                              "Apenas o Diretor de Projetos pode realizar esta ação")


def require_self_or_admin(usuario_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.id != usuario_id and not usuario_tem_permissao(current_user, db, "pode_gerenciar_cargos"):
        raise HTTPException(status_code=403, detail="Você só pode acessar seus próprios dados")
    return current_user
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository


class UpdateDescricaoRequest(BaseModel):
    descricao: Optional[str] = None
    # Nome errado na criação (duplicado, digitado errado) precisa de conserto
    # depois — mora aqui, e não num use case próprio: é edição de texto
    # simples, sem regra de negócio nenhuma amarrada. `cliente` e
    # `link_proposta` são o mesmo caso.
    nome: Optional[str] = None
    cliente: Optional[str] = None
    link_proposta: Optional[str] = None


class UpdateDescricaoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateDescricaoRequest):
        dados = request.dict(exclude_unset=True)
        if "nome" in dados and not (dados["nome"] or "").strip():
            dados.pop("nome")
        projeto = self.repository.update(projeto_id, **dados)
        if not projeto:
            return None
        return {
            "id": projeto.id,
            "nome": projeto.nome,
            "descricao": projeto.descricao,
            "cliente": projeto.cliente,
            "link_proposta": projeto.link_proposta,
        }

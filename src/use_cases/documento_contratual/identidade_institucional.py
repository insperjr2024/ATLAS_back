"""Ler e editar a Identidade Institucional (§ Contratos).

⭐ 2026-09-18 — presidente + as duas testemunhas fixas da Insper Jr, usadas
em todo documento gerado (`render_template.py`). Muda a cada troca de
gestão — daí ser editável, não hardcoded.
"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.models.identidade_institucional_model import IdentidadeInstitucionalModel
from src.repositories.identidade_institucional_repository import IdentidadeInstitucionalRepository
from src.utils.exceptions import RegraDeNegocioError

#: Os únicos campos editáveis — impede que um PATCH solto tente sobrescrever
#: `id` ou um campo que nem existe no model.
CAMPOS_EDITAVEIS = {
    "presidente_nome", "presidente_cpf", "presidente_rg", "presidente_orgao_emissor",
    "presidente_endereco", "presidente_estado_civil", "presidente_nacionalidade",
    "presidente_profissao", "presidente_email", "presidente_telefone",
    "testemunha1_nome", "testemunha1_cpf", "testemunha1_email", "testemunha1_telefone",
    "testemunha2_nome", "testemunha2_cpf", "testemunha2_email", "testemunha2_telefone",
}


class GetIdentidadeInstitucionalUseCase:
    def __init__(self, db: Session):
        self.identidade = IdentidadeInstitucionalRepository(db)

    def execute(self) -> Optional[IdentidadeInstitucionalModel]:
        return self.identidade.get()


class AtualizarIdentidadeInstitucionalUseCase:
    def __init__(self, db: Session):
        self.identidade = IdentidadeInstitucionalRepository(db)

    def execute(self, dados: Dict[str, Any]) -> IdentidadeInstitucionalModel:
        desconhecidos = set(dados) - CAMPOS_EDITAVEIS
        if desconhecidos:
            raise RegraDeNegocioError(f"Campo(s) desconhecido(s): {', '.join(sorted(desconhecidos))}.")
        atualizado = self.identidade.update(**dados)
        if not atualizado:
            raise RegraDeNegocioError("Identidade institucional não encontrada.")
        return atualizado

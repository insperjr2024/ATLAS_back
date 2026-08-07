"""§7.4 — apagar uma nota de justificativa.

O histórico continua sendo um retrato do que a diretoria escreveu, não um
campo qualquer: isto não é pra correção de rotina, é pra tirar engano/teste.
Só a diretoria (mesma trava de quem registra).
"""

from sqlalchemy.orm import Session

from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)


class ExcluirJustificativaAtrasoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoJustificativaAtrasoRepository(db)

    def execute(self, projeto_id: int, justificativa_id: int) -> bool:
        justificativa = self.repository.get_by_id(justificativa_id)
        if not justificativa or justificativa.projeto_id != projeto_id:
            return False
        return self.repository.delete(justificativa_id)

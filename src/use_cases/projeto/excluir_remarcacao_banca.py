"""§5.6 — apagar um registro de remarcação de banca.

Mesma lógica de `ExcluirJustificativaAtrasoUseCase`: o histórico não é campo
de edição de rotina, isto é pra engano/teste. Só a diretoria.
"""

from sqlalchemy.orm import Session

from src.repositories.projeto_remarcacao_banca_repository import ProjetoRemarcacaoBancaRepository


class ExcluirRemarcacaoBancaUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRemarcacaoBancaRepository(db)

    def execute(self, projeto_id: int, remarcacao_id: int) -> bool:
        remarcacao = self.repository.get_by_id(remarcacao_id)
        if not remarcacao or remarcacao.projeto_id != projeto_id:
            return False
        return self.repository.delete(remarcacao_id)

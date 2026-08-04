from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.utils.exceptions import RegraDeNegocioError


class ArquivarProjetoUseCase:
    """Arquivar não é excluir (§6.2): o projeto some das listagens normais,
    mas nada é apagado — banca, avaliação e histórico continuam intactos."""

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None
        if projeto.arquivado_em is not None:
            raise RegraDeNegocioError("O projeto já está arquivado")
        return self.repository.update(projeto_id, arquivado_em=datetime.utcnow())


class DesarquivarProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None
        if projeto.arquivado_em is None:
            raise RegraDeNegocioError("O projeto não está arquivado")
        return self.repository.update(projeto_id, arquivado_em=None)

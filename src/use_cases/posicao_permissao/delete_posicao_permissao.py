from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.utils.exceptions import RegraDeNegocioError


class DeletePosicaoPermissaoUseCase:
    """Apagar um cargo criado pela diretoria.

    Os 6 cargos padrão (`e_padrao=True`) são recusados aqui, antes de chegar
    no banco — apagá-los quebraria as regras de identidade hardcoded a eles
    por nome em `middlewares/authorization.py` e afins (ver a migration
    `a9cae5c30c6d`). Quem ainda tem gente no cargo é recusado pela FK
    `usuario.posicao -> posicao_permissao.posicao`, que o repositório traduz
    em `ResourceInUseError` — a mesma recusa que já existe para frente/escopo.
    """

    def __init__(self, db: Session):
        self.repository = PosicaoPermissaoRepository(db)

    def execute(self, posicao: str) -> bool:
        registro = self.repository.get_by_posicao(posicao)
        if not registro:
            return False
        if registro.e_padrao:
            raise RegraDeNegocioError(
                "Este é um dos cargos padrão da plataforma e não pode ser excluído."
            )
        return self.repository.delete(posicao)

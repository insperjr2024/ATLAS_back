from sqlalchemy.orm import Session
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from pydantic import BaseModel


class CreateUsuarioFrenteRequest(BaseModel):
    usuario_id: int
    frente_id: int


class CreateUsuarioFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioFrenteRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, request: CreateUsuarioFrenteRequest):
        # O recorte de visão do gerente (`aplicar_recorte_visao`) trava numa
        # frente só — mais de uma vira ambiguidade sobre o que ele deveria
        # enxergar. Coordenador/consultor não têm essa restrição: a frente ali
        # é só metadado de alocação, não controla acesso.
        usuario = self.usuario_repository.get_by_id(request.usuario_id)
        if usuario and usuario.posicao == "gerente":
            ja_tem = self.repository.get_by_usuario(request.usuario_id)
            if len(ja_tem) >= 1:
                raise RegraDeNegocioError(
                    "Um gerente só pode ter uma frente — remova a atual antes de adicionar outra."
                )

        usuario_frente = self.repository.create(
            usuario_id=request.usuario_id,
            frente_id=request.frente_id
        )
        return {
            "id": usuario_frente.id,
            "usuario_id": usuario_frente.usuario_id,
            "frente_id": usuario_frente.frente_id
        }
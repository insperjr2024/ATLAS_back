from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.usuario_repository import UsuarioRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.cargo_repository import CargoRepository
from src.utils.senha import hash_senha
from src.utils.exceptions import RegraDeNegocioError


class RegistrarRequest(BaseModel):
    nome: str
    email_insper: str
    senha: str


class RegistrarUseCase:
    def __init__(self, db: Session):
        self.usuario_repository = UsuarioRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.cargo_repository = CargoRepository(db)

    def execute(self, request: RegistrarRequest):
        existente = self.usuario_repository.get_by_email_insper(request.email_insper)
        if existente:
            raise RegraDeNegocioError("Já existe uma conta com este email")

        configuracao = self.configuracao_repository.get()
        if not configuracao or not configuracao.cargo_padrao_id:
            raise RegraDeNegocioError("Cargo padrão de registro ainda não foi configurado pelo administrador")

        cargo = self.cargo_repository.get_by_id(configuracao.cargo_padrao_id)
        if not cargo:
            raise RegraDeNegocioError("Cargo padrão configurado não existe mais")

        usuario = self.usuario_repository.create(
            nome=request.nome,
            email_insper=request.email_insper,
            cargo_id=cargo.id,
            senha_hash=hash_senha(request.senha),
            ativo=True
        )
        return {
            "id": usuario.id,
            "nome": usuario.nome,
            "email_insper": usuario.email_insper,
            "cargo_id": usuario.cargo_id,
            "ativo": usuario.ativo
        }
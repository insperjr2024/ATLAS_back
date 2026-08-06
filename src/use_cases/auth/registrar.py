from typing import Literal, Optional

from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from src.repositories.usuario_repository import UsuarioRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.cargo_repository import CargoRepository
from src.use_cases.usuario.get_usuario import serializar_usuario
from src.utils.senha import hash_senha
from src.utils.exceptions import RegraDeNegocioError


class RegistrarRequest(BaseModel):
    """Pré-cadastro feito pela diretoria (§10) — a rota já exige token.

    `posicao` entra aqui porque é o que define o que a pessoa enxerga assim que
    faz o primeiro login.
    """

    nome: str
    email_insper: str
    senha: str
    posicao: Literal["diretor", "gerente", "coordenador", "consultor"] = "consultor"
    cargo_id: Optional[int] = None
    semestre_graduacao: Optional[int] = Field(default=None, ge=1, le=8)


class RegistrarUseCase:
    def __init__(self, db: Session):
        self.usuario_repository = UsuarioRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.cargo_repository = CargoRepository(db)

    def execute(self, request: RegistrarRequest):
        existente = self.usuario_repository.get_by_email_insper(request.email_insper)
        if existente:
            raise RegraDeNegocioError("Já existe uma conta com este email")

        if request.cargo_id is not None:
            cargo = self.cargo_repository.get_by_id(request.cargo_id)
            if not cargo:
                raise RegraDeNegocioError("Cargo informado não existe")
        else:
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
            posicao=request.posicao,
            status="ativo",
            ativo=True,
            semestre_graduacao=request.semestre_graduacao,
        )
        return serializar_usuario(usuario)
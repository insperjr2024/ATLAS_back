from typing import Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.usuario_posicao_historico_model import UsuarioPosicaoHistoricoModel
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.usuario.get_usuario import serializar_usuario

Posicao = Literal["diretor", "gerente", "coordenador", "consultor"]
StatusUsuario = Literal["ativo", "ex_membro", "desligado"]


class UpdateUsuarioRequest(BaseModel):
    nome: Optional[str] = None
    email_insper: Optional[str] = None
    cargo_id: Optional[int] = None
    posicao: Optional[Posicao] = None
    status: Optional[StatusUsuario] = None
    ativo: Optional[bool] = None


class UpdateUsuarioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UsuarioRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, usuario_id: int, request: UpdateUsuarioRequest, alterado_por: Optional[int] = None):
        data = request.model_dump(exclude_unset=True)

        anterior = self.repository.get_by_id(usuario_id)
        if not anterior:
            return None
        posicao_anterior = anterior.posicao

        # `ativo` é espelho de `status`: mexer num mantém o outro coerente, senão
        # o login (que lê `ativo`) e a tela de Membros (que lê `status`) divergem.
        if "status" in data:
            data["ativo"] = data["status"] == "ativo"
        elif "ativo" in data and data["ativo"] is False and anterior.status == "ativo":
            data["status"] = "ex_membro"

        usuario = self.repository.update(usuario_id, **data)
        if not usuario:
            return None

        # A promoção da virada não pode reescrever o passado: o arquivo da
        # gestão anterior precisa continuar mostrando quem a pessoa ERA.
        nova_posicao = data.get("posicao")
        if nova_posicao and nova_posicao != posicao_anterior:
            semestre_ativo = self.semestre_repository.get_ativo()
            self.db.add(
                UsuarioPosicaoHistoricoModel(
                    usuario_id=usuario_id,
                    posicao=nova_posicao,
                    semestre_id=semestre_ativo.id if semestre_ativo else None,
                    alterado_por=alterado_por,
                )
            )
            self.db.commit()

        alocados = self.membro_repository.contar_ativos_por_usuario()
        return serializar_usuario(usuario, alocados.get(usuario.id, 0))


class DeleteUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int) -> bool:
        return self.repository.delete(usuario_id)
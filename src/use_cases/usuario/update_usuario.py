from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.usuario_posicao_historico_model import UsuarioPosicaoHistoricoModel
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.usuario.get_usuario import serializar_usuario
from src.utils.exceptions import RegraDeNegocioError

Posicao = Literal[
    "diretor_projetos",
    "diretor_pessoas",
    "diretor",
    "gerente",
    "coordenador",
    "consultor",
]
StatusUsuario = Literal["ativo", "ex_membro", "desligado"]


class UpdateUsuarioRequest(BaseModel):
    nome: Optional[str] = None
    email_insper: Optional[str] = None
    posicao: Optional[Posicao] = None
    status: Optional[StatusUsuario] = None
    ativo: Optional[bool] = None
    semestre_graduacao: Optional[int] = Field(default=None, ge=1, le=8)


class UpdateUsuarioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UsuarioRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def _impedir_ficar_sem_diretoria(self, anterior, data: dict):
        """🔒 A plataforma nunca pode ficar sem diretoria DE PROJETOS.

        Rebaixar ou desativar a última pessoa nesse cargo trancaria a
        administração para sempre, sem ninguém capaz de destrancar. Para a
        virada de gestão existe `TransferirDiretoriaUseCase`, que promove
        antes de rebaixar.

        ⚠ **A trava vale só para `diretor_projetos`**, e não para os três
        cargos de diretoria. Depois da divisão (2026-08-20), ele é o único com
        `pode_administrar_configuracoes` — os outros dois podem chegar a zero
        sem trancar nada, e travá-los junto só impediria a diretoria de
        reorganizar os próprios cargos.
        """
        CARGO = "diretor_projetos"
        if anterior.posicao != CARGO:
            return

        virou_outra_posicao = data.get("posicao", CARGO) != CARGO
        saiu_da_ativa = data.get("status", anterior.status) != "ativo"
        if not virou_outra_posicao and not saiu_da_ativa:
            return

        outros = [
            u
            for u in self.repository.get_por_posicao(CARGO)
            if u.id != anterior.id and u.status == "ativo"
        ]
        if not outros:
            raise RegraDeNegocioError(
                "Esta é a última pessoa na diretoria — promova outra antes, "
                "ou use a transferência de diretoria."
            )

    def execute(self, usuario_id: int, request: UpdateUsuarioRequest, alterado_por: Optional[int] = None):
        data = request.model_dump(exclude_unset=True)

        anterior = self.repository.get_by_id(usuario_id)
        if not anterior:
            return None
        posicao_anterior = anterior.posicao

        # Troca de email: barra o branco e a colisão com outra conta antes de
        # bater na constraint UNIQUE do banco, que viraria um 500 sem mensagem.
        if "email_insper" in data:
            novo_email = (data["email_insper"] or "").strip()
            if not novo_email:
                raise RegraDeNegocioError("O email não pode ficar em branco")
            data["email_insper"] = novo_email
            ja_existe = self.repository.get_by_email_insper(novo_email)
            if ja_existe and ja_existe.id != usuario_id:
                raise RegraDeNegocioError("Já existe uma conta com este email")

        # `ativo` é espelho de `status`: mexer num mantém o outro coerente, senão
        # o login (que lê `ativo`) e a tela de Membros (que lê `status`) divergem.
        if "status" in data:
            data["ativo"] = data["status"] == "ativo"
        elif "ativo" in data and data["ativo"] is False and anterior.status == "ativo":
            data["status"] = "ex_membro"

        self._impedir_ficar_sem_diretoria(anterior, data)

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
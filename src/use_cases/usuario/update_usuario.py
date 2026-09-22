from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.usuario_posicao_historico_model import UsuarioPosicaoHistoricoModel
from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.usuario.get_usuario import serializar_usuario
from src.utils.exceptions import RegraDeNegocioError

# ⚠ Não é mais `Literal` fechado nos 6 cargos padrão desde 2026-09-16 — ver o
# mesmo comentário em `RegistrarRequest`. Quem valida é `UpdateUsuarioUseCase`.
StatusUsuario = Literal["ativo", "ex_membro", "desligado"]


class UpdateUsuarioRequest(BaseModel):
    nome: Optional[str] = None
    email_insper: Optional[str] = None
    posicao: Optional[str] = None
    status: Optional[StatusUsuario] = None
    ativo: Optional[bool] = None
    #: ⭐ 2026-09-16 — substitui os booleanos soltos `coordenador_vendas` e
    #: `bdr`. "Coordenador de vendas" virou cargo de verdade, escolhido em
    #: `posicao` como qualquer outro; o que sobra aqui é a pessoa acumular
    #: duas posições — a principal (`posicao`) e esta, opcional.
    #: ⭐ 2026-09-22 — a pedido: generalizado. Antes só aceitava "bdr" e só
    #: em cima de "consultor" (hardcoded); agora aceita qualquer cargo
    #: marcado `sobreponivel=True` (ver `posicao_permissao_model.py`), em
    #: cima de qualquer posição — validado em `execute`.
    cargo_extra: Optional[str] = None
    semestre_graduacao: Optional[int] = Field(default=None, ge=1, le=8)


class UpdateUsuarioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UsuarioRepository(db)
        self.posicao_repository = PosicaoPermissaoRepository(db)
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

        if "posicao" in data and not self.posicao_repository.get_by_posicao(data["posicao"]):
            raise RegraDeNegocioError("Posição inválida")

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

        # ⭐ 2026-09-22 — a pedido: generalizado. Cargo extra é qualquer
        # posição marcada `sobreponivel=True` — decidido na hora de criar o
        # cargo (ver `create_posicao_permissao.py`), não mais hardcoded pra
        # só "bdr" em cima de "consultor".
        if data.get("cargo_extra"):
            extra_registro = self.posicao_repository.get_by_posicao(data["cargo_extra"])
            if not extra_registro or not extra_registro.sobreponivel:
                raise RegraDeNegocioError(f'"{data["cargo_extra"]}" não pode ser usado como cargo extra')
            posicao_efetiva = data.get("posicao", anterior.posicao)
            if data["cargo_extra"] == posicao_efetiva:
                raise RegraDeNegocioError("O cargo extra não pode ser igual à posição principal")

        # Virar a MESMA posição do cargo extra pendurado não faz sentido
        # (extra igual à principal) — limpa. Qualquer outra combinação
        # continua válida, já que cargo extra não é mais restrito a uma
        # posição base específica.
        posicao_pedida = data.get("posicao")
        if posicao_pedida:
            cargo_extra_atual = data.get("cargo_extra", anterior.cargo_extra)
            if cargo_extra_atual == posicao_pedida:
                data["cargo_extra"] = None

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
        posicoes_vendas = self.posicao_repository.get_posicoes_com_permissao(
            "pode_responsavel_por_vendas"
        )
        return serializar_usuario(usuario, alocados.get(usuario.id, 0), posicoes_vendas)


class DeleteUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int) -> bool:
        return self.repository.delete(usuario_id)
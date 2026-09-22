import re
import unicodedata

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.use_cases.posicao_permissao.get_posicao_permissao import serializar_posicao_permissao
from src.utils.exceptions import RegraDeNegocioError


def slugificar(nome: str) -> str:
    """"Vendas" -> "vendas"; "Gestão de Pessoas Jr." -> "gestao_de_pessoas_jr".

    É o valor que passa a viver em `usuario.posicao` — sem acento e sem
    espaço pelo mesmo motivo de qualquer outro identificador interno da
    plataforma (os 6 cargos padrão já seguem este formato)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


class CreatePosicaoPermissaoRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    #: ⭐ 2026-09-22 — a pedido: perguntado na hora de criar o cargo, não
    #: depois. Se este cargo pode ser o `cargo_extra` de qualquer pessoa —
    #: uma segunda posição somada à principal (ver `usuario_model.py`).
    #: Exemplo dado pela diretoria: "consultor" não seria sobreponível (é
    #: sempre posição base); "bdr"/"adm jurídico" seriam.
    sobreponivel: bool


class CreatePosicaoPermissaoUseCase:
    """Cargo novo, criado pela diretoria — ver a migration `a9cae5c30c6d`.

    ⭐ Nasce com TODAS as caixas de `posicao_permissao` desligadas: quem criou
    marca o que quiser depois, em "Editar" — igual o cargo padrão nasceria se
    pudesse ser criado do zero. Não entra em nenhuma lista de identidade
    hardcoded (mentor, composição de banca, portfólio inteiro); isso é
    escopo de fora desta ação, de propósito. A única exceção é `sobreponivel`
    (⭐ 2026-09-22): decidida já na criação, porque é sobre COMO o cargo se
    combina com outros, não uma permissão de ação.
    """

    def __init__(self, db: Session):
        self.repository = PosicaoPermissaoRepository(db)

    def execute(self, request: CreatePosicaoPermissaoRequest):
        nome = request.nome.strip()
        if not nome:
            raise RegraDeNegocioError("Informe um nome para o cargo")

        posicao = slugificar(nome)
        if not posicao:
            raise RegraDeNegocioError("Informe um nome válido para o cargo")

        if self.repository.get_by_posicao(posicao):
            raise RegraDeNegocioError("Já existe um cargo com esse nome")

        registro = self.repository.create(
            posicao=posicao, nome=nome, e_padrao=False, sobreponivel=request.sobreponivel
        )
        return serializar_posicao_permissao(registro)

"""Modelos base (.docx) dos documentos jurídicos: ver, baixar, trocar e
voltar ao padrão (2026-10-07, a pedido).

O padrão de cada tipo vem no deploy (`documentos_contratuais/templates/`).
Trocar grava o .docx em `documento_modelo`; a geração passa a usar ele.
O arquivo novo tem que ser renderizável e só pode usar campos que o padrão
já usa: uma cláusula a mais ou um texto diferente entra sem mexer em nada;
um `{{ campo_novo }}` que o preenchimento não fornece é recusado, com o
nome do campo, em vez de virar um documento com buraco.
"""

import io
from typing import Optional

from docxtpl import DocxTemplate
from sqlalchemy.orm import Session

from src.documentos_contratuais.render_template import TEMPLATE_POR_TIPO, caminho_template_padrao
from src.repositories.documento_modelo_repository import DocumentoModeloRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError

ROTULOS = {
    "contrato": "Contrato de Prestação de Serviços",
    "tep": "TEP",
    "nda": "NDA",
    "uso_imagem": "Termo de Uso de Imagem",
    "aditivo": "Termo Aditivo",
}

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _variaveis(doc: DocxTemplate) -> set:
    # O DocxTemplate só abre o arquivo aqui, então é aqui que um arquivo que
    # não é .docx estoura.
    try:
        return set(doc.get_undeclared_template_variables())
    except Exception as e:  # noqa: BLE001 - docx corrompido ou jinja inválido
        if "zip" in str(e).lower():
            raise RegraDeNegocioError("O arquivo enviado não é um .docx válido.")
        raise RegraDeNegocioError(f"Não foi possível ler os campos do modelo: {e}")


def _abrir(conteudo: bytes) -> DocxTemplate:
    try:
        return DocxTemplate(io.BytesIO(conteudo))
    except Exception:  # noqa: BLE001
        raise RegraDeNegocioError("O arquivo enviado não é um .docx válido.")


class ListarModelosUseCase:
    def __init__(self, db: Session):
        self.modelos = DocumentoModeloRepository(db)
        self.usuarios = UsuarioRepository(db)

    def execute(self) -> list[dict]:
        saida = []
        for tipo, arquivo in TEMPLATE_POR_TIPO.items():
            personalizado = self.modelos.get_por_tipo(tipo)
            autor = self.usuarios.get_by_id(personalizado.enviado_por) if personalizado and personalizado.enviado_por else None
            saida.append(
                {
                    "tipo": tipo,
                    "rotulo": ROTULOS.get(tipo, tipo),
                    "arquivo_padrao": arquivo,
                    "personalizado": personalizado is not None,
                    "arquivo_nome": personalizado.arquivo_nome if personalizado else arquivo,
                    "enviado_em": personalizado.enviado_em if personalizado else None,
                    "enviado_por_nome": autor.nome if autor else None,
                }
            )
        return saida


class BaixarModeloUseCase:
    """O modelo em uso: o personalizado, se houver, senão o padrão do deploy."""

    def __init__(self, db: Session):
        self.modelos = DocumentoModeloRepository(db)

    def execute(self, tipo: str) -> tuple[bytes, str]:
        if tipo not in TEMPLATE_POR_TIPO:
            raise RegraDeNegocioError(f'Não há modelo para documentos do tipo "{tipo}".')
        personalizado = self.modelos.get_por_tipo(tipo)
        if personalizado:
            return bytes(personalizado.arquivo_conteudo), personalizado.arquivo_nome
        with open(caminho_template_padrao(tipo), "rb") as f:
            return f.read(), TEMPLATE_POR_TIPO[tipo]


class EnviarModeloUseCase:
    def __init__(self, db: Session):
        self.modelos = DocumentoModeloRepository(db)

    def execute(self, tipo: str, conteudo: bytes, arquivo_nome: str, usuario_id: Optional[int]) -> dict:
        if tipo not in TEMPLATE_POR_TIPO:
            raise RegraDeNegocioError(f'Não há modelo para documentos do tipo "{tipo}".')
        if not conteudo:
            raise RegraDeNegocioError("O arquivo está vazio.")
        novo = _abrir(conteudo)
        with open(caminho_template_padrao(tipo), "rb") as f:
            padrao = DocxTemplate(io.BytesIO(f.read()))
        extras = sorted(_variaveis(novo) - _variaveis(padrao))
        if extras:
            raise RegraDeNegocioError(
                "O modelo usa campos que o preenchimento não fornece: "
                + ", ".join(f"{{{{ {v} }}}}" for v in extras)
                + ". Mantenha só os campos do modelo padrão (o texto em volta pode mudar à vontade)."
            )
        nome = arquivo_nome or TEMPLATE_POR_TIPO[tipo]
        if not nome.lower().endswith(".docx"):
            nome += ".docx"
        self.modelos.substituir(tipo, nome, conteudo, usuario_id)
        return next(m for m in ListarModelosUseCase(self.modelos.db).execute() if m["tipo"] == tipo)


class RemoverModeloUseCase:
    """Volta ao padrão do deploy."""

    def __init__(self, db: Session):
        self.modelos = DocumentoModeloRepository(db)

    def execute(self, tipo: str) -> None:
        atual = self.modelos.get_por_tipo(tipo)
        if atual:
            self.modelos.delete(atual.id)

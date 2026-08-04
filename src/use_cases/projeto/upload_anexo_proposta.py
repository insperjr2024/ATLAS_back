import uuid

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.storage import pasta_propostas

TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024  # 15MB
ASSINATURA_PDF = b"%PDF-"


class UploadAnexoPropostaUseCase:
    """Recebe o PDF da proposta (§6.3) e substitui o link, se houver um —
    a proposta é ou link, ou anexo, nunca os dois."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, arquivo: UploadFile) -> dict:
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            raise RegraDeNegocioError("Projeto não encontrado")

        nome_original = (arquivo.filename or "proposta.pdf").strip()
        if not nome_original.lower().endswith(".pdf"):
            raise RegraDeNegocioError("O anexo da proposta precisa ser um PDF")

        conteudo = arquivo.file.read()
        if not conteudo:
            raise RegraDeNegocioError("O arquivo enviado está vazio")
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            raise RegraDeNegocioError("O PDF da proposta precisa ter até 15MB")
        # Confere a assinatura real do arquivo, não só a extensão — evita
        # gravar um arquivo renomeado como .pdf que na verdade não é um.
        if not conteudo.startswith(ASSINATURA_PDF):
            raise RegraDeNegocioError("O arquivo enviado não é um PDF válido")

        pasta = pasta_propostas()
        nome_arquivo = f"{uuid.uuid4().hex}.pdf"
        (pasta / nome_arquivo).write_bytes(conteudo)

        anexo_anterior = projeto.anexo_proposta_path
        self.repository.update(
            projeto_id,
            anexo_proposta_path=nome_arquivo,
            anexo_proposta_nome=nome_original,
            link_proposta=None,
        )

        if anexo_anterior:
            antigo = pasta / anexo_anterior
            if antigo.exists():
                antigo.unlink()

        return {"anexo_proposta_nome": nome_original}

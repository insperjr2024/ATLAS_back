"""Contrato institucional (Agro etc.) — um documento jurídico avulso, sem
projeto de entrega nenhum por trás (§ Contratos, 2026-09-21).

⭐ Reverte a abordagem anterior (`create_projeto_institucional.py`, migration
`743e671bffea`): criar um `ProjetoModel` só pra pendurar um documento
poluía a tabela `projeto` com linhas que nunca vão virar entrega de
consultoria de verdade. Agora o "projeto" é só um NOME digitado no próprio
formulário do documento (`nome_projeto_externo`/`cliente_externo`,
diretamente em `DocumentoContratualModel` — ver a migration
`9c1e5a7d3f42`), sem linha nenhuma em `projeto`.
"""

from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.utils.dados_documento_contratual import montar_dados_iniciais
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_documento_contratual import StatusDocumentoContratual, TipoDocumentoContratual


class CriarDocumentoInstitucionalRequest(BaseModel):
    nome_projeto: str
    cliente: Optional[str] = None
    tipo: str


class CriarDocumentoInstitucionalUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)

    def execute(self, request: CriarDocumentoInstitucionalRequest, criado_por: Optional[int] = None):
        try:
            TipoDocumentoContratual(request.tipo)
        except ValueError:
            raise RegraDeNegocioError(f'Tipo de documento desconhecido: "{request.tipo}".')

        dados_iniciais = montar_dados_iniciais(request.tipo, None, request.nome_projeto)

        return self.documentos.create(
            projeto_id=None,
            nome_projeto_externo=request.nome_projeto,
            cliente_externo=request.cliente,
            tipo=request.tipo,
            status=StatusDocumentoContratual.AGUARDANDO_PREENCHIMENTO.value,
            dados=dados_iniciais,
            confirmado=False,
            criado_por=criado_por,
        )

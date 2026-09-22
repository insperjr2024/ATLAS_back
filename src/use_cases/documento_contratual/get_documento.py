from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.documento_contratual_model import DocumentoContratualModel
from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.use_cases.documento_contratual.marcar_assinado import dias_restantes_aceite_tacito


def serializar_documento_contratual(
    documento: DocumentoContratualModel,
    ultima_versao: Optional[int] = None,
    frente_ids: Optional[List[int]] = None,
) -> dict:
    return {
        "id": documento.id,
        "projeto_id": documento.projeto_id,
        # ⭐ 2026-09-21 — a pedido: a página do documento virou standalone
        # (fora da aba do projeto), então precisa trazer o nome/cliente do
        # projeto junto — antes vinha só do contexto do `ProjetoPage` que
        # não existe mais aqui. Institucional (`projeto_id` nulo) não tem
        # projeto de verdade — o nome/cliente são os campos digitados no
        # próprio documento (`nome_projeto_externo`/`cliente_externo`).
        "projeto_nome": documento.projeto.nome if documento.projeto_id else documento.nome_projeto_externo,
        "projeto_cliente": documento.projeto.cliente if documento.projeto_id else documento.cliente_externo,
        # Pro destaque de frente no cabeçalho da página — institucional
        # (sem projeto) nunca tem frente nenhuma.
        "frente_ids": frente_ids or [],
        "tipo": documento.tipo,
        "status": documento.status,
        "dados": documento.dados,
        "confirmado": documento.confirmado,
        "gestao_id": documento.gestao_id,
        "criado_em": documento.criado_em,
        "atualizado_em": documento.atualizado_em,
        "ultima_versao": ultima_versao,
        # Só não-`None` pro TEP em "aprovado_pelo_cliente" — o front usa isto
        # pra liberar o botão "Considerar assinado (prazo vencido)".
        "dias_restantes_aceite_tacito": dias_restantes_aceite_tacito(documento),
    }


class GetDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.frentes = ProjetoFrenteRepository(db)

    def execute(self, documento_id: int) -> Optional[dict]:
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            return None
        ultima_versao = self.versoes.ultima_versao(documento_id)
        frente_ids = (
            [f.frente_id for f in self.frentes.get_by_projeto(documento.projeto_id)]
            if documento.projeto_id
            else []
        )
        return serializar_documento_contratual(documento, ultima_versao or None, frente_ids)


class ListDocumentosContratuaisPorProjetoUseCase:
    """Todos os documentos jurídicos de um projeto — a aba Contratos dele."""

    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, projeto_id: int) -> List[dict]:
        documentos = self.documentos.list_by_projeto(projeto_id)
        return [
            serializar_documento_contratual(d, self.versoes.ultima_versao(d.id) or None)
            for d in documentos
        ]

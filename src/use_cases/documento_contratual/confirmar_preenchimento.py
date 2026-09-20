"""Confirmar que os dados de um documento jurídico estão certos (§ Contratos).

⭐ 2026-09-16 — porta de `POST /contratos/{id}/confirmar`. Quem preencheu
confirma e manda pro Jurídico — até aqui dava pra editar ou desistir à
vontade; depois desta chamada, a edição vira função de quem tem
`pode_editar_documento_juridico` (ver `atualizar_dados.py`).

⭐ 2026-09-18 — avisa quem tem `pode_editar_documento_juridico` que já pode
gerar (porta `NotificacaoService.documento_pronto_para_gerar`).

⭐ 2026-09-20 — a pedido: recusa confirmar com campo obrigatório vazio (CNPJ,
nome do representante etc.) — antes dava pra confirmar e até gerar um
contrato inteiro em branco.
"""

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar_documento_contratual import documento_pronto_para_gerar
from src.utils.validar_dados_documento_contratual import campos_faltando


class ConfirmarPreenchimentoDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)

    def execute(self, documento_id: int):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        if documento.status != "aguardando_preenchimento":
            raise RegraDeNegocioError(
                'Só é possível confirmar um documento "aguardando preenchimento".'
            )
        if documento.confirmado:
            raise RegraDeNegocioError("Este documento já foi confirmado.")

        faltando = campos_faltando(documento.tipo, documento.dados)
        if faltando:
            raise RegraDeNegocioError(f"Faltam campos obrigatórios: {', '.join(faltando)}.")

        confirmado = self.documentos.update(documento_id, confirmado=True)
        documento_pronto_para_gerar(self.db, confirmado)
        return confirmado

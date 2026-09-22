"""Preparar o envio do rascunho ao cliente para aprovação (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/projeto/exportar_aprovacao.py`
+ `wa_link.py`. Gera um link público de uso único (`TokenAprovacaoContratualModel`)
apontando pra ÚLTIMA versão gerada e move o documento pra
`aguardando_aprovacao_cliente`.

⚠ O sistema antigo pegava `documentos[0]` (a PRIMEIRA versão) em vez da mais
recente — bug que não é replicado aqui: usa-se sempre
`versoes.ultima_versao_obj`.
"""

import secrets

from sqlalchemy.orm import Session

from src.config.config import get_settings
from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.token_aprovacao_contratual_repository import (
    TokenAprovacaoContratualRepository,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.mudar_status_projeto_automatico import mudar_status_projeto_automaticamente
from src.utils.notificar_documento_contratual import documento_liberado_para_cliente
from src.utils.status_documento_contratual import (
    STATUS_EXPORTACAO_PERMITIDA,
    TipoDocumentoContratual,
    nome_do_projeto,
)
from src.utils.wa_link_contratual import mensagem_aprovacao


class ExportarAprovacaoDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.tokens = TokenAprovacaoContratualRepository(db)

    def execute(self, documento_id: int) -> dict:
        documento = self._get(documento_id)
        if documento.status not in STATUS_EXPORTACAO_PERMITIDA:
            raise RegraDeNegocioError(
                'Só é possível exportar para aprovação do cliente com o documento '
                'em "aprovado_internamente".'
            )
        return self._gerar_link(documento)

    def recusar_assinatura_tep(self, documento_id: int) -> dict:
        """Cliente aprovou o texto do TEP mas avisou (fora da plataforma) que
        não vai assinar. Só existe pro TEP: nos demais tipos a recusa é
        tratada manualmente fora do sistema. Gera um link NOVO (o anterior já
        foi usado quando o cliente aprovou) e reabre o ciclo de aprovação."""
        documento = self._get(documento_id)
        if documento.tipo != TipoDocumentoContratual.TEP.value:
            raise RegraDeNegocioError("Registrar recusa de assinatura só se aplica ao TEP.")
        if documento.status != "aprovado_pelo_cliente":
            raise RegraDeNegocioError(
                'Só é possível registrar recusa com o documento em "aprovado_pelo_cliente".'
            )
        return self._gerar_link(documento)

    def _gerar_link(self, documento) -> dict:
        versao = self.versoes.ultima_versao_obj(documento.id)
        if not versao:
            raise RegraDeNegocioError("Nenhum rascunho gerado ainda para este documento.")

        token = secrets.token_urlsafe(32)
        self.tokens.create(token=token, documento_id=documento.id, versao_id=versao.id)
        documento = self.documentos.update(documento.id, status="aguardando_aprovacao_cliente")
        documento_liberado_para_cliente(self.db, documento)

        # 🤖 2026-09-21 — a pedido: TEP enviado pro cliente move o projeto
        # sozinho pra "Envio do TEP". Só na primeira vez de fato importa —
        # reenviar (recusar_assinatura_tep) já encontra o projeto lá e não
        # faz nada (ver o guard em mudar_status_projeto_automaticamente).
        if documento.tipo == TipoDocumentoContratual.TEP.value:
            mudar_status_projeto_automaticamente(self.db, documento.projeto_id, "envio_tep")

        settings = get_settings()
        link_aprovacao = f"{settings.FRONTEND_URL.rstrip('/')}/aprovacao/{token}"

        # ⭐ 2026-09-20 — a pedido: quem manda decide o telefone na hora (o
        # cadastrado pode estar errado, ou o WhatsApp certo pra isso é de
        # outra pessoa) — o back só entrega o texto pronto, o número e o
        # link de wa.me são montados no front (`montarLinkWhatsapp`).
        mensagem_whatsapp = mensagem_aprovacao(nome_do_projeto(documento), link_aprovacao)

        return {
            "token": token,
            "link_aprovacao": link_aprovacao,
            "mensagem_whatsapp": mensagem_whatsapp,
        }

    def _get(self, documento_id: int):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        return documento

"""Fechar o ciclo de assinatura: marcar como assinado e arquivar (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/projeto/avancar_status.py`
(`_arquivar_documento_assinado`/`considerar_tep_assinado_por_prazo`), com uma
simplificação deliberada: o sistema antigo MOVIA os arquivos pra uma pasta
por gestão (`arquivamento.py`) — organização por filesystem que o ATLAS não
usa em nenhum outro lugar. Aqui só se marca `gestao_id` nas linhas do banco
(documento + versão); os arquivos continuam onde `gerar_documento.py` os
salvou. O Repositório filtra por `gestao_id`, não por pasta.

A gestão vem de `SemestreRepository` (a entidade que o resto do ATLAS já usa
pra "semestre corrente") — não se reimplementa `calcular_gestao()` do sistema
antigo.
"""

from datetime import date

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.semestre_repository import SemestreRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.mudar_status_projeto_automatico import mudar_status_projeto_automaticamente
from src.utils.notificar_projeto import projeto_vendido
from src.utils.status_documento_contratual import PRAZO_ACEITE_TACITO_TEP_DIAS


def dias_restantes_aceite_tacito(documento) -> int | None:
    """Quantos dias corridos faltam até o TEP poder ser considerado aceito
    por prazo (0 ou negativo = prazo já vencido, botão liberado). `None`
    quando a cláusula não se aplica (não é TEP, ou não está esperando
    assinatura do cliente).

    A contagem começa quando o documento entra em "aprovado_pelo_cliente": a
    partir daí os dados ficam travados (`STATUS_DADOS_TRAVADOS`), então
    `atualizado_em` só muda de novo quando ele é de fato arquivado — ou seja,
    enquanto o status for esse, ele reflete o momento da aprovação.
    """
    if documento.tipo != "tep" or documento.status != "aprovado_pelo_cliente":
        return None
    dias_passados = (date.today() - documento.atualizado_em.date()).days
    return PRAZO_ACEITE_TACITO_TEP_DIAS - dias_passados


class MarcarAssinadoDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.semestres = SemestreRepository(db)

    def execute(self, documento_id: int):
        """O time baixa o PDF/.docx (já liberado desde "aprovado_pelo_cliente")
        e assina fora da plataforma, por conta própria. Sem integração
        automática — esta chamada é que fecha o ciclo."""
        documento = self._get(documento_id)
        if documento.status != "aprovado_pelo_cliente":
            raise RegraDeNegocioError(
                'Só é possível marcar como assinado com o documento em "aprovado_pelo_cliente".'
            )
        return self._arquivar(documento)

    def considerar_aceito_por_prazo(self, documento_id: int):
        """Cláusula de aceite tácito do TEP: cliente que não assina no prazo
        é considerado como tendo aceito. Nunca acontece sozinho — precisa
        deste clique explícito do time depois que o prazo já venceu."""
        documento = self._get(documento_id)
        if documento.tipo != "tep":
            raise RegraDeNegocioError("A cláusula de aceite tácito só se aplica ao TEP.")
        if documento.status != "aprovado_pelo_cliente":
            raise RegraDeNegocioError(
                'Só é possível considerar aceito com o documento em "aprovado_pelo_cliente".'
            )
        dias_restantes = dias_restantes_aceite_tacito(documento)
        if dias_restantes is not None and dias_restantes > 0:
            raise RegraDeNegocioError(
                f"Ainda faltam {dias_restantes} dia(s) para o prazo de aceite tácito vencer."
            )
        return self._arquivar(documento)

    def _arquivar(self, documento):
        semestre_ativo = self.semestres.get_por_data(date.today()) or self.semestres.get_ativo()
        gestao_id = semestre_ativo.id if semestre_ativo else None

        versao = self.versoes.ultima_versao_obj(documento.id)
        if versao:
            self.versoes.marcar_final(versao, gestao_id)

        atualizado = self.documentos.update(
            documento.id, status="assinado_e_arquivado", gestao_id=gestao_id
        )

        # 🤖 2026-09-21 — a pedido: TEP assinado (ou aceito por prazo) move o
        # projeto sozinho pra "Período de ajustes" — a entrega final já foi
        # validada, o que resta é ajuste fino, não mais execução.
        if documento.tipo == "tep":
            mudar_status_projeto_automaticamente(self.db, documento.projeto_id, "periodo_ajustes")

        # 🤖 2026-09-21 — a pedido: Contrato de Prestação assinado é o que de
        # fato torna a venda real — antes disso o projeto só existe como
        # "contrato em elaboração" (`create_projeto.py`).
        if documento.tipo == "contrato":
            mudar_status_projeto_automaticamente(self.db, documento.projeto_id, "vendido")
            projeto_vendido(self.db, documento.projeto)

        return atualizado

    def _get(self, documento_id: int):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        return documento

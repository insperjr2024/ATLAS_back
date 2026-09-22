"""Marcar uma solicitação de alteração do cliente como analisada (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/solicitacao/analisar.py`.

⚠ Marcar como analisada é só um registro de acompanhamento — não edita o
documento sozinho. O ajuste de verdade é manual: o Jurídico edita os dados
ou o texto e gera de novo (ver `gerar_documento.py`/`editar_texto.py`).
"""

from sqlalchemy.orm import Session

from src.repositories.solicitacao_alteracao_contratual_repository import (
    SolicitacaoAlteracaoContratualRepository,
)
from src.utils.exceptions import RegraDeNegocioError


class AnalisarSolicitacaoAlteracaoUseCase:
    def __init__(self, db: Session):
        self.solicitacoes = SolicitacaoAlteracaoContratualRepository(db)

    def execute(self, solicitacao_id: int):
        solicitacao = self.solicitacoes.get_by_id(solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Solicitação não encontrada.")
        if solicitacao.status == "analisada":
            raise RegraDeNegocioError("Esta solicitação já foi analisada.")
        return self.solicitacoes.marcar_analisada(solicitacao)

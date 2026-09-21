"""Criar um projeto institucional (Agro etc.) — só pra pendurar um documento
jurídico (§ Contratos, 2026-09-21).

⭐ Um contrato institucional (ex.: parceria com o Agro Insper) não é uma
entrega de consultoria: não tem frente, não tem equipe, não tem escopo. Mas
`documento_contratual.projeto_id` é uma FK obrigatória — precisa de um
`ProjetoModel` de verdade por trás. Em vez de forçar `CreateProjetoUseCase`
(que exige `frente_ids`/`equipe` por design — são o cadastro de verdade do
§6.3) a aceitar campos vazios, este use case cria a linha mínima direto:
só `nome` (e `cliente`, se vier).

`projeto.institucional = True` marca a linha pra sempre — é o que
`ProjetosList.tsx`/Monitoramento usam pra nunca misturar isso com entrega de
consultoria de verdade, mesmo depois de "vendido".
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.use_cases.projeto.get_projeto import serializar_projeto_resumo
from src.utils.notificar_projeto import projeto_criado


class CreateProjetoInstitucionalRequest(BaseModel):
    nome: str
    cliente: Optional[str] = None


class CreateProjetoInstitucionalUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, request: CreateProjetoInstitucionalRequest, criado_por: int):
        projeto = self.repository.create(
            nome=request.nome,
            cliente=request.cliente,
            institucional=True,
            status="contrato_em_elaboracao",
            criado_por=criado_por,
        )

        self.historico_repository.create(
            projeto_id=projeto.id,
            status_anterior=None,
            status_novo="contrato_em_elaboracao",
            alterado_por=criado_por,
        )

        # Mesma notificação de "projeto criado em contrato" de sempre — sem
        # vendedor pra incluir (não tem equipe/venda aqui), diretoria e
        # gerentes recebem normalmente.
        projeto_criado(self.db, projeto)

        return serializar_projeto_resumo(projeto, self.frente_repository, self.membro_repository)

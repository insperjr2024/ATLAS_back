"""Sugerir dias de exceção a partir do calendário acadêmico (§ Contratos,
2026-09-21).

⭐ A pedido: em vez de digitar cada dia de exceção à mão, o formulário do
Contrato de Prestação pode puxar do calendário acadêmico (`DiaNaoLetivoModel`,
já usado pra contar dia útil em todo o resto do ATLAS) as datas tipo
"prova" que caem dentro do intervalo do contrato — provas do Insper
atravancam o trabalho tanto quanto um feriado, mas feriado já não é dia
útil pra ninguém (não precisa virar "exceção" nenhuma); só "prova" entra
aqui. "Recesso" fica de fora pelo mesmo motivo do feriado.

Só SUGERE — quem preenche decide o que entra, o formulário faz merge sem
duplicar e sem apagar o que já foi editado à mão."""

from datetime import date
from typing import List

from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.utils.exceptions import RegraDeNegocioError


class SugerirDiasExcecaoUseCase:
    def __init__(self, db: Session):
        self.dias = DiaNaoLetivoRepository(db)
        self.frentes = ProjetoFrenteRepository(db)

    def execute(self, projeto_id: int, inicio: date, fim: date) -> List[dict]:
        if fim < inicio:
            raise RegraDeNegocioError("A data de término não pode vir antes da data de início.")

        frente_ids = {f.frente_id for f in self.frentes.get_by_projeto(projeto_id)}
        candidatos = self.dias.get_por_intervalo(inicio, fim)

        provas = [
            d
            for d in candidatos
            if d.tipo == "prova" and (d.frente_id is None or d.frente_id in frente_ids)
        ]
        return [{"inicio": d.data.isoformat(), "fim": d.data.isoformat()} for d in provas]

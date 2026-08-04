"""Tarefa vencida (§6.4) e a janela da semana (§6.4, reunião semanal).

🧮 Nenhum dos dois é campo no banco:

- **vencida** = `prazo` passado e status fora dos terminais. Um booleano
  gravado exigiria um job para virá-lo à meia-noite, e ficaria errado entre
  uma passada e outra.
- **semana** = a janela seg–dom. `date.weekday()` do Python já é
  segunda-first (0=seg … 6=dom), então não precisa de parâmetro de início de
  semana como no front.

Ambas moram no BACKEND, e não no componente React, porque o monitoramento
(§7.2) precisa da mesma regra agregando vários projetos numa rota totalmente
separada da tela do kanban. Duplicar em TypeScript seria garantir divergência
no dia em que alguém mexesse só num lado.
"""

from datetime import date, timedelta
from typing import Optional

STATUS_TERMINAIS = frozenset({"concluido", "cancelado"})


def eh_vencida(prazo: Optional[date], status: str, hoje: Optional[date] = None) -> bool:
    if prazo is None:
        return False
    hoje = hoje or date.today()
    return prazo < hoje and status not in STATUS_TERMINAIS


def esta_ativa(status: str) -> bool:
    """Tarefa que ainda conta como trabalho pendente."""
    return status not in STATUS_TERMINAIS


def inicio_semana(dia: Optional[date] = None) -> date:
    """A segunda-feira da semana de `dia`."""
    dia = dia or date.today()
    return dia - timedelta(days=dia.weekday())


def fim_semana(dia: Optional[date] = None) -> date:
    """O domingo da semana de `dia`."""
    return inicio_semana(dia) + timedelta(days=6)


def janela_semana(dia: Optional[date] = None) -> tuple[date, date]:
    dia = dia or date.today()
    return inicio_semana(dia), fim_semana(dia)

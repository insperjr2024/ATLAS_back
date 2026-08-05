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

def eh_vencida(
    prazo: Optional[date], coluna_encerra: bool, hoje: Optional[date] = None
) -> bool:
    """Prazo passado E tarefa ainda aberta.

    ⭐ `coluna_encerra` vem de `tarefa_coluna.encerra_tarefa`, e não de uma
    lista fixa de status: as colunas do kanban são configuráveis pela
    diretoria. Quem cria uma coluna diz se ela encerra a tarefa — é o que
    impede que uma coluna nova ("Arquivado", "Em espera") deixe tudo que cai
    ali vencido para sempre.
    """
    if prazo is None:
        return False
    hoje = hoje or date.today()
    return prazo < hoje and not coluna_encerra


def esta_ativa(coluna_encerra: bool) -> bool:
    """Tarefa que ainda conta como trabalho pendente (§7.2)."""
    return not coluna_encerra


# ⏰ Os níveis de urgência, do prazo se aproximando até ele passar.
#
# `vencida` já existia como booleano e continua — o monitoramento conta por
# ele. A gradação abaixo é para a TELA: um card que vence amanhã e um que
# vence em três semanas não podem parecer a mesma coisa, e esperar virar
# vermelho no dia seguinte ao prazo é tarde demais.
URGENCIA_VENCIDA = "vencida"
URGENCIA_CRITICA = "critica"   # vence hoje ou amanhã
URGENCIA_ATENCAO = "atencao"   # vence em 2 ou 3 dias
URGENCIA_NORMAL = "normal"

DIAS_CRITICA = 1
DIAS_ATENCAO = 3


def dias_para_prazo(prazo: Optional[date], hoje: Optional[date] = None) -> Optional[int]:
    """Dias CORRIDOS até o prazo. Negativo = já passou."""
    if prazo is None:
        return None
    hoje = hoje or date.today()
    return (prazo - hoje).days


def calcular_urgencia(
    prazo: Optional[date], coluna_encerra: bool, hoje: Optional[date] = None
) -> str:
    """O nível de urgência do prazo.

    Tarefa em coluna que encerra é sempre `normal`: ela saiu, o prazo não
    importa mais. Mesma regra de `eh_vencida`, para as duas nunca discordarem.
    """
    if coluna_encerra:
        return URGENCIA_NORMAL
    restantes = dias_para_prazo(prazo, hoje)
    if restantes is None:
        return URGENCIA_NORMAL
    if restantes < 0:
        return URGENCIA_VENCIDA
    if restantes <= DIAS_CRITICA:
        return URGENCIA_CRITICA
    if restantes <= DIAS_ATENCAO:
        return URGENCIA_ATENCAO
    return URGENCIA_NORMAL


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

"""A máquina de estados do ciclo de vida do projeto (§4).

    Vendido → Ambientação → Em andamento → Validação em bancas
            → Envio do TEP → Período de ajustes → Finalizado
    (+ Pausado, um estado à parte, acessível de qualquer etapa ativa)

✋ Toda transição é manual, escolhida de uma lista — não "um passo por vez":
a diretoria/coordenação pode pular direto pra qualquer etapa ativa, pra
frente ou pra trás (inclusive reabrir um projeto finalizado). A única regra
de ordem que sobra é sair de **Vendido**: só vira Ambientação, e só depois
do kickoff marcado — sem kickoff não tem data pra registrar o início (§5.2).

🗓 Marcar o kickoff não move mais o status sozinho: dá pra cadastrar em junho
com kickoff planejado pra agosto, e o projeto continua Vendido até alguém
confirmar Ambientação pelo seletor de etapa — o kickoff só *habilita* esse
passo, quem aciona é sempre uma pessoa.
"""

from typing import List, Optional

from src.utils.exceptions import RegraDeNegocioError

STATUS_ORDEM = [
    "vendido",
    "ambientacao",
    "em_andamento",
    "validacao_bancas",
    "envio_tep",
    "periodo_ajustes",
    "finalizado",
]

# Tudo que não é Vendido transita livremente entre si, nos dois sentidos.
STATUS_ATIVOS = set(STATUS_ORDEM[1:])

STATUS_PAUSAVEIS = {"ambientacao", "em_andamento", "validacao_bancas", "envio_tep", "periodo_ajustes"}


def pode_pausar(status_atual: str) -> bool:
    return status_atual in STATUS_PAUSAVEIS


def transicao_manual_valida(status_atual: str, status_novo: str, tem_kickoff: bool) -> bool:
    """Pode ir de `status_atual` pra `status_novo`?

    Vendido só vira Ambientação, e só com `data_kickoff` já marcada. Qualquer
    etapa ativa (fora Vendido e Pausado, que têm mecanismo próprio) vai pra
    qualquer outra ativa, livremente.
    """
    if status_novo == status_atual:
        return False
    if status_atual == "vendido":
        return status_novo == "ambientacao" and tem_kickoff
    return status_atual in STATUS_ATIVOS and status_novo in STATUS_ATIVOS


def destinos_validos(status_atual: str, tem_kickoff: bool) -> List[str]:
    """As etapas que o seletor mostra como opção — a mesma régua de
    `transicao_manual_valida`, mas devolvendo a lista em vez de validar um
    clique só. `pausado` não tem destino por aqui: sai pelo retomar."""
    if status_atual == "pausado":
        return []
    if status_atual == "vendido":
        return ["ambientacao"] if tem_kickoff else []
    return [s for s in STATUS_ORDEM[1:] if s != status_atual]


def pausar(status_atual: str) -> tuple[str, str]:
    """Devolve (novo_status, status_a_guardar_para_retomar)."""
    if not pode_pausar(status_atual):
        raise RegraDeNegocioError(f"Não é possível pausar um projeto em '{status_atual}'")
    return "pausado", status_atual


def retomar(status_guardado: Optional[str]) -> str:
    """Volta ao status anterior à pausa — guardado em projeto.status_antes_pausa
    (redundante com o histórico, mas evita reconsultá-lo a cada retomada)."""
    if not status_guardado:
        raise RegraDeNegocioError("Não há status anterior registrado para retomar")
    return status_guardado

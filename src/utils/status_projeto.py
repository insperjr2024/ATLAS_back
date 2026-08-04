"""A máquina de estados do ciclo de vida do projeto (§4).

    Vendido → Ambientação → Em andamento → Validação em bancas
            → Envio do TEP → Período de ajustes → Finalizado
    (+ Pausado, um estado à parte, acessível de qualquer status ativo)

🤖 = o sistema muda sozinho · ✋ = alguém muda manualmente (coordenador; diretor
e gerente herdam).
"""

from typing import Optional

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

# 🤖 Transições automáticas — disparadas por evento, não por clique.
TRANSICOES_AUTOMATICAS = {
    "vendido": "ambientacao",  # ao marcar o kickoff
    "ambientacao": "em_andamento",  # quando acabam os dias de ambientação
}

# ✋ Transições manuais — só a próxima da fila; nunca pula etapa.
TRANSICOES_MANUAIS = {
    "em_andamento": "validacao_bancas",
    "validacao_bancas": "envio_tep",
    "envio_tep": "periodo_ajustes",
    "periodo_ajustes": "finalizado",
}

STATUS_PAUSAVEIS = {"ambientacao", "em_andamento", "validacao_bancas", "envio_tep", "periodo_ajustes"}


def pode_pausar(status_atual: str) -> bool:
    return status_atual in STATUS_PAUSAVEIS


def transicao_manual_valida(status_atual: str, status_novo: str) -> bool:
    return TRANSICOES_MANUAIS.get(status_atual) == status_novo


def aplicar_transicao_manual(status_atual: str) -> str:
    """A próxima etapa manual — ou erro se não houver uma daqui."""
    proximo = TRANSICOES_MANUAIS.get(status_atual)
    if proximo is None:
        raise RegraDeNegocioError(
            f"Não há transição manual a partir de '{status_atual}'. "
            "Pausado só volta pelo botão de retomar."
        )
    return proximo


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

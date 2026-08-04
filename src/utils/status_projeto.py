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
#
# ⚠ `ambientacao → em_andamento` aparece nos DOIS mapas, e é de propósito:
# o §4 diz que ela é automática ao fim dos dias de ambientação, mas o
# disparador ainda não existe — e, sem o caminho manual, um projeto que chega
# em Ambientação fica preso lá para sempre. Com a volta de etapa isso ficou
# pior: dava para regredir até Ambientação e não ter como sair.
#
# Manter o manual também é correto depois que o automático existir: a equipe
# pode terminar a ambientação antes do prazo, e aí quem decide é a
# coordenação, não o calendário.
TRANSICOES_MANUAIS = {
    "ambientacao": "em_andamento",
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


# ↩ A VOLTA — um passo atrás na mesma fila.
#
# Avançar sem poder voltar deixa um clique errado travando o projeto para
# sempre: só um DBA desfaria. A régua é a mesma da ida — **um passo por vez,
# nunca pula etapa** —, então a volta é o índice anterior em STATUS_ORDEM.
# Isso inclui reabrir um projeto finalizado, que é o caso em que o erro mais
# dói.
#
# ⛔ **O piso é Ambientação.** Voltar dali para Vendido seria desmarcar o
# kickoff, e a data já registrada é um fato do projeto — não um passo de
# fluxo que se desfaz clicando. Um kickoff marcado errado se corrige
# editando a data na aba Visão geral, não regredindo o status.
#
# `pausado` também fica de fora: não está na fila, e a saída dele é o
# retomar, que devolve ao status guardado.

STATUS_PISO_VOLTA = "ambientacao"


def status_anterior_manual(status_atual: str) -> Optional[str]:
    """A etapa imediatamente anterior, ou None se não houver.

    Devolve None em `ambientacao` (o piso) e em `pausado` (fora da fila).
    """
    if status_atual not in STATUS_ORDEM or status_atual == STATUS_PISO_VOLTA:
        return None
    indice = STATUS_ORDEM.index(status_atual)
    return STATUS_ORDEM[indice - 1] if indice > 0 else None


def transicao_volta_valida(status_atual: str, status_novo: str) -> bool:
    return status_anterior_manual(status_atual) == status_novo


def aplicar_volta(status_atual: str) -> str:
    """A etapa anterior — ou erro se o projeto já estiver no piso."""
    anterior = status_anterior_manual(status_atual)
    if anterior is None:
        if status_atual == "pausado":
            raise RegraDeNegocioError(
                "Um projeto pausado não volta etapa: use o botão de retomar."
            )
        if status_atual == STATUS_PISO_VOLTA:
            raise RegraDeNegocioError(
                "Ambientação é a primeira etapa a que se pode voltar. Para "
                "corrigir um kickoff marcado errado, edite a data na aba "
                "Visão geral."
            )
        raise RegraDeNegocioError(f"'{status_atual}' já é a primeira etapa do projeto")
    return anterior


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

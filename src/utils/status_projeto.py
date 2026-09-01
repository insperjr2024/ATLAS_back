"""A máquina de estados do ciclo de vida do projeto (§4).

    Vendido → Ambientação → Em andamento → Validação em bancas
            → Envio do TEP → Período de ajustes → Finalizado
    (+ Pausado, um estado à parte, acessível de qualquer etapa ativa)

🤖 **Uma exceção, e só uma: Ambientação → Em andamento acontece sozinha**
quando os dias úteis de ambientação acabam (§5.3). É a única etapa com data
de fim calculável — as outras dependem de alguém decidir que o trabalho
terminou. A regra mora em `utils/ambientacao.py` e quem a aplica é
`use_cases/projeto/encerrar_ambientacao.py`; nada aqui precisa saber dela,
porque de Ambientação para Em andamento já era destino válido.

✋ Fora essa, toda transição é manual, escolhida de uma lista — não "um passo por vez":
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

#: ⭐ TODOS os status que uma linha de `projeto` pode ter — a fila do ciclo
#: mais Pausado, que é estado à parte e por isso não está em `STATUS_ORDEM`.
#:
#: Espelha o Enum da coluna `projeto.status`. É a lista que o filtro de status
#: do Monitoramento valida contra: sem ela, um `?status=em_progresso` (que não
#: existe) devolveria zero projeto e a tela pareceria vazia de verdade, em vez
#: de acusar o parâmetro errado.
STATUS_VALIDOS = tuple(STATUS_ORDEM) + ("pausado",)

STATUS_PAUSAVEIS = {"ambientacao", "em_andamento", "validacao_bancas", "envio_tep", "periodo_ajustes"}

#: Como cada etapa se CHAMA para quem lê. Espelha `ROTULO_STATUS` em
#: `lib/projetos.ts` — as duas pontas têm que dizer a mesma palavra.
#:
#: ⚠ A chave é o valor da coluna, o rótulo é o nome na tela, e os dois
#: divergem em `validacao_bancas` → "Aguardando bancas". Mensagem de erro que
#: entrega a chave crua manda a pessoa procurar na tela uma etapa chamada
#: "validacao_bancas", que não existe em lugar nenhum da interface.
ROTULO_STATUS = {
    "vendido": "Vendido",
    "ambientacao": "Ambientação",
    "em_andamento": "Em andamento",
    "validacao_bancas": "Aguardando bancas",
    "envio_tep": "Envio do TEP",
    "periodo_ajustes": "Período de ajustes",
    "finalizado": "Finalizado",
    "pausado": "Pausado",
}


def rotulo(status: Optional[str]) -> str:
    """O nome de tela de uma etapa; a chave crua se ela for desconhecida."""
    return ROTULO_STATUS.get(status or "", status or "—")


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

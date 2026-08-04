"""⭐ A contagem de dias por escopo — a regra crítica do §5.4.

Em cima de `dias_uteis.py`, que responde "o que é um dia útil". Aqui a
pergunta é outra: **quantos dos dias vendidos deste escopo já correram?**

As quatro regras do briefing, e onde cada uma mora no código:

1. *"Os dias são contados por escopo e só correm enquanto aquele escopo está
   ativo"* → sem `data_inicio`, a contagem devolve zero e para por aí.
2. *"Quando um escopo é entregue, a contagem pausa"* → o fim da janela vira
   `data_entrega_real` e congela; mover o relógio não muda mais nada.
3. *"O período de ajustes entre escopos não é contabilizado"* → cai fora
   sozinho: o escopo entregue congelou, o próximo ainda não começou.
4. *"Em paralelo, cada escopo conta os seus próprios dias ao mesmo tempo"* →
   cada escopo é uma chamada independente. Não existe estado global de "qual
   escopo está correndo", e é exatamente isso que faz o paralelo funcionar.

Além dessas, as janelas de ⏸ Pausado do projeto inteiro são descontadas de
todos os escopos que estavam correndo durante elas.

Como o `dias_uteis.py`, tudo aqui é função pura: quem chama carrega o banco
uma vez e passa os dados. `referencia` é injetável para os testes não
precisarem congelar o relógio.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from src.utils.dias_uteis import contar_dias_uteis

# Janela de pausa, SEMIABERTA: [inicio, fim).
#
# O dia em que se pausou não conta como trabalhado; o dia em que se retomou
# conta. Com essa convenção, duas janelas coladas nunca perdem nem dobram um
# dia — e é o que faz o número congelar no instante exato da pausa.
JanelaPausa = Tuple[date, date]


@dataclass(frozen=True)
class ContagemEscopo:
    dias_vendidos: int
    consumidos: int
    #: Pode ser NEGATIVO — é o "estourou em N dias" da aba Atrasos. Quem clampa
    #: para a barra de progresso é o front, não o cálculo.
    restantes: int
    estourou: bool
    em_contagem: bool
    data_inicio: Optional[date]
    fim_da_janela: Optional[date]


def derivar_janelas_pausa(historico: Iterable, referencia: Optional[date] = None) -> List[JanelaPausa]:
    """As janelas de ⏸ Pausado, lidas de `projeto_status_historico`.

    O `UpdateStatusUseCase` sempre grava uma linha ao pausar e ao retomar,
    então a varredura é direta: abre em `status_novo == "pausado"`, fecha na
    próxima linha com `status_anterior == "pausado"`.

    ⭐ Se a última janela ficou aberta (o projeto está pausado AGORA), ela
    fecha em `referencia + 1 dia`, **não** em `referencia`. Fechar na própria
    referência deixaria o dia de hoje escapar da pausa e o contador
    continuaria andando com o projeto parado — um dia a mais a cada dia.

    As janelas saem disjuntas e ordenadas (a guarda de "já tem uma aberta"
    garante isso), então quem consome não precisa de passo de merge.
    """
    referencia = referencia or date.today()
    janelas: List[JanelaPausa] = []
    abertura: Optional[date] = None

    for linha in historico:
        momento = linha.alterado_em
        dia = momento.date() if hasattr(momento, "date") else momento

        if linha.status_novo == "pausado" and abertura is None:
            abertura = dia
        elif linha.status_anterior == "pausado" and abertura is not None:
            janelas.append((abertura, dia))
            abertura = None

    if abertura is not None:
        janelas.append((abertura, referencia + timedelta(days=1)))

    return janelas


def calcular_contagem_escopo(
    data_inicio: Optional[date],
    data_entrega_real: Optional[date],
    dias_uteis_vendidos: int,
    dias_nao_letivos: Iterable[date],
    janelas_pausa: Iterable[JanelaPausa] = (),
    referencia: Optional[date] = None,
) -> ContagemEscopo:
    """Os dias consumidos e restantes de UM escopo."""
    # Regra 1: sem data de início, o escopo não começou a correr. Nem o
    # "próximo escopo" que ainda espera a reunião inicial, nem um escopo
    # cadastrado na venda e nunca iniciado.
    if data_inicio is None:
        return ContagemEscopo(
            dias_vendidos=dias_uteis_vendidos,
            consumidos=0,
            restantes=dias_uteis_vendidos,
            estourou=False,
            em_contagem=False,
            data_inicio=None,
            fim_da_janela=None,
        )

    referencia = referencia or date.today()

    # Regra 2: a entrega congela o fim da janela. É a única linha que faz o
    # "escopo entregue pausa a contagem" — depois dela, o relógio é irrelevante.
    fim = data_entrega_real or referencia

    bruto = contar_dias_uteis(data_inicio, fim, dias_nao_letivos)

    # As pausas descontam apenas a parte que cai DENTRO da janela do escopo.
    # Sem essa interseção, uma pausa ocorrida durante a ambientação (antes do
    # escopo começar) roubaria dias que ele nunca chegou a consumir.
    descontado = 0
    for pausa_inicio, pausa_fim in janelas_pausa:
        descontado += contar_dias_uteis(
            max(pausa_inicio, data_inicio),
            # -1 dia fecha a semiaberta no intervalo fechado que
            # `contar_dias_uteis` espera. Interseção vazia vira intervalo
            # invertido, e `contar_dias_uteis` já devolve 0 nesse caso.
            min(pausa_fim - timedelta(days=1), fim),
            dias_nao_letivos,
        )

    consumidos = max(0, bruto - descontado)

    return ContagemEscopo(
        dias_vendidos=dias_uteis_vendidos,
        consumidos=consumidos,
        restantes=dias_uteis_vendidos - consumidos,
        estourou=consumidos > dias_uteis_vendidos,
        em_contagem=data_entrega_real is None,
        data_inicio=data_inicio,
        fim_da_janela=fim,
    )


def calcular_contagem_projeto(
    escopos: Iterable,
    historico: Iterable,
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
) -> Dict[int, ContagemEscopo]:
    """A contagem de todos os escopos de um projeto, por `projeto_escopo.id`.

    Deriva as janelas de pausa **uma vez** e aplica a mesma lista a todos os
    escopos — é o que mantém a regra 4 (paralelo) coerente: dois escopos
    correndo ao mesmo tempo descontam a mesma pausa, cada um na sua janela.
    """
    referencia = referencia or date.today()
    janelas = derivar_janelas_pausa(historico, referencia)

    return {
        escopo.id: calcular_contagem_escopo(
            data_inicio=escopo.data_inicio,
            data_entrega_real=escopo.data_entrega_real,
            dias_uteis_vendidos=escopo.dias_uteis_vendidos,
            dias_nao_letivos=dias_nao_letivos,
            janelas_pausa=janelas,
            referencia=referencia,
        )
        for escopo in escopos
    }

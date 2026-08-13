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
from src.utils.janela_escopo import (
    calcular_janela,
    dias_de_atraso,
    dias_de_correcao,
    marco_das_correcoes,
    primeira_realizacao,
)

# Janela de pausa, SEMIABERTA: [inicio, fim).
#
# O dia em que se pausou não conta como trabalhado; o dia em que se retomou
# conta. Com essa convenção, duas janelas coladas nunca perdem nem dobram um
# dia — e é o que faz o número congelar no instante exato da pausa.
JanelaPausa = Tuple[date, date]


@dataclass(frozen=True)
class ContagemEscopo:
    dias_vendidos: int
    #: Dias extras autorizados pela diretoria (§8). Somam com os vendidos para
    #: formar a janela, mas continuam sendo mostrados à parte — a tela diz
    #: *vendidos 20 · ajustados 10*, nunca "vendidos 30".
    dias_ajustados: int
    consumidos: int
    #: Pode ser NEGATIVO — é o "estourou em N dias" da aba Atrasos. Quem clampa
    #: para a barra de progresso é o front, não o cálculo.
    #:
    #: Medido contra *vendidos + ajustados*: quem ganhou 10 dias tem 10 dias a
    #: mais para gastar, senão a autorização não teria efeito nenhum.
    restantes: int
    estourou: bool
    em_contagem: bool
    data_inicio: Optional[date]
    #: ⚠ O fim da janela de CONTAGEM (a entrega, ou hoje enquanto ela não vem)
    #: — não confundir com `fim_janela_prevista`, que é o último dia em que o
    #: escopo caberia no prometido. Os dois divergem exatamente quando há
    #: atraso, e é dessa diferença que o atraso é feito.
    fim_da_janela: Optional[date]
    #: O último dia da JANELA DO ESCOPO: início + vendidos + ajustados dias
    #: úteis. É o que a faixa do calendário desenha e o limite em que a banca
    #: pode ser marcada (§9).
    fim_janela_prevista: Optional[date] = None
    #: §10 — derivado, nunca gravado. Zero enquanto a janela não estourou.
    atraso: int = 0
    #: §11 — dias úteis pintados depois de a BANCA ser realizada: as CORREÇÕES
    #: que ela apontou. Não consomem dias e não são atraso.
    #:
    #: ⚠️ Não confundir com `dias_ajustados`, que são dias de trabalho vendido
    #: acrescentados à JANELA por decisão da diretoria. Correção não aumenta
    #: janela e não se pede a ninguém.
    correcoes: int = 0


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
    dias_uteis_ajustados: int = 0,
    etapas: Iterable = (),
    banca_realizado_em=None,
) -> ContagemEscopo:
    """Os dias consumidos, restantes, em atraso e em correções de UM escopo.

    `etapas` e `banca_realizado_em` são opcionais porque nem todo chamador
    precisa das duas métricas novas: a barra de progresso quer consumidos, e
    quem monta a Visão geral quer as cinco. Sem etapas, as correções são zero —
    o que é a resposta certa, não um valor faltando.
    """
    # Regra 1: sem data de início, o escopo não começou a correr. Nem o
    # "próximo escopo" que ainda espera a reunião inicial, nem um escopo
    # cadastrado na venda e nunca iniciado.
    if data_inicio is None:
        return ContagemEscopo(
            dias_vendidos=dias_uteis_vendidos,
            dias_ajustados=dias_uteis_ajustados,
            consumidos=0,
            restantes=dias_uteis_vendidos + dias_uteis_ajustados,
            estourou=False,
            em_contagem=False,
            data_inicio=None,
            fim_da_janela=None,
            fim_janela_prevista=None,
            atraso=0,
            correcoes=0,
        )

    referencia = referencia or date.today()
    # Materializada uma vez: daqui para baixo a lista é percorrida três vezes
    # (desconto, janela e atraso), e um gerador se esgotaria na primeira.
    janelas_pausa = list(janelas_pausa)

    # ⭐ Regra 2: a contagem para quando o escopo entra em CORREÇÕES — o que
    # acontece na banca REALIZADA, não na entrega.
    #
    # ⚠ Isto era `data_entrega_real or referencia`, e o efeito era uma tela que
    # se contradizia: um escopo com banca feita 1 dia depois da janela e entrega
    # ainda não registrada mostrava "22/12 (+10)" ao lado de "Atraso: 1 dia".
    # Os dois números mediam o mesmo estouro com réguas diferentes — o consumo
    # corria até hoje, o atraso parava na banca.
    #
    # A régua certa é a da banca, e é o §11 que diz: os dias depois dela são
    # CORREÇÃO, e correção "não consome dias e não é atraso". Contar o tempo de
    # arrumar o que a banca apontou como se fosse trabalho vendido inflava o
    # estouro de todo escopo que ainda não teve a entrega registrada — e ele
    # crescia sozinho, um dia por dia, sem ninguém trabalhar.
    #
    # `marco_das_correcoes` já resolve a precedência (banca realizada, senão a
    # entrega) e é a mesma função que as correções usam logo abaixo: uma régua
    # só para os dois lados da mesma fronteira.
    inicio_das_correcoes = marco_das_correcoes(banca_realizado_em, data_entrega_real)
    fim = inicio_das_correcoes or referencia

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

    # A janela do escopo (§5): vendidos + ajustados. É contra ela que "estourou"
    # é medido, e é ela que o atraso mede por fora.
    #
    # ⭐ As mesmas pausas que descontam do consumido acima empurram o fim da
    # janela: as duas contas precisam enxergar o mesmo calendário, senão o
    # escopo congela o consumo mas continua estourando o prazo.
    janela = calcular_janela(
        data_inicio,
        dias_uteis_vendidos,
        dias_uteis_ajustados,
        dias_nao_letivos,
        referencia,
        janelas_pausa=janelas_pausa,
    )
    total = dias_uteis_vendidos + dias_uteis_ajustados

    return ContagemEscopo(
        dias_vendidos=dias_uteis_vendidos,
        dias_ajustados=dias_uteis_ajustados,
        consumidos=consumidos,
        restantes=total - consumidos,
        estourou=consumidos > total,
        # Acompanha a Regra 2: o relógio para no mesmo ponto em que `fim` para.
        # Era `data_entrega_real is None`, o que passou a mentir quando a
        # contagem virou a banca — dizia "ainda correndo" sobre um número que
        # já estava congelado.
        em_contagem=inicio_das_correcoes is None,
        data_inicio=data_inicio,
        fim_da_janela=fim,
        fim_janela_prevista=janela.fim,
        # ⚠ A MESMA régua de `consumidos`, e não só a banca.
        #
        # `consumidos` para em `inicio_das_correcoes` — que é a banca realizada
        # OU, na falta dela, a entrega registrada. O atraso olhava só a banca:
        # num escopo entregue sem banca realizada, o consumo congelava e o
        # atraso seguia crescendo um dia por dia. Os dois números saíam do mesmo
        # payload medindo o mesmo estouro e discordavam, e era o atraso que
        # aparecia na aba de Atrasos.
        atraso=dias_de_atraso(
            janela, inicio_das_correcoes, dias_nao_letivos, referencia, janelas_pausa
        ),
        correcoes=dias_de_correcao(
            etapas, marco_das_correcoes(banca_realizado_em, data_entrega_real), dias_nao_letivos
        ),
    )


def _sessoes_da_banca(banca, sessoes_por_banca) -> list:
    """As tentativas daquela banca, ou vazio quando o chamador não as carregou.

    Vazio é seguro: `primeira_realizacao` cai em `banca.realizado_em`, que é o
    comportamento correto para banca de uma tentativa só — a maioria.
    """
    if banca is None:
        return []
    return (sessoes_por_banca or {}).get(banca.id, [])


def calcular_contagem_projeto(
    escopos: Iterable,
    historico: Iterable,
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
    etapas_por_escopo: Optional[Dict[int, list]] = None,
    bancas_por_escopo: Optional[Dict[int, object]] = None,
    sessoes_por_banca: Optional[Dict[int, list]] = None,
) -> Dict[int, ContagemEscopo]:
    """A contagem de todos os escopos de um projeto, por `projeto_escopo.id`.

    Deriva as janelas de pausa **uma vez** e aplica a mesma lista a todos os
    escopos — é o que mantém a regra 4 (paralelo) coerente: dois escopos
    correndo ao mesmo tempo descontam a mesma pausa, cada um na sua janela.

    `etapas_por_escopo` e `bancas_por_escopo` são opcionais para quem só quer a
    barra de progresso não precisar carregar as duas tabelas: sem elas o
    as correções e o atraso saem zerados, e quem os exibe é quem os carrega.
    """
    referencia = referencia or date.today()
    janelas = derivar_janelas_pausa(historico, referencia)
    etapas_por_escopo = etapas_por_escopo or {}
    bancas_por_escopo = bancas_por_escopo or {}
    sessoes_por_banca = sessoes_por_banca or {}

    return {
        escopo.id: calcular_contagem_escopo(
            data_inicio=escopo.data_inicio,
            data_entrega_real=escopo.data_entrega_real,
            dias_uteis_vendidos=escopo.dias_uteis_vendidos,
            dias_uteis_ajustados=escopo.dias_uteis_ajustados,
            dias_nao_letivos=dias_nao_letivos,
            janelas_pausa=janelas,
            referencia=referencia,
            etapas=etapas_por_escopo.get(escopo.id, ()),
            # ⭐ A PRIMEIRA tentativa, não a corrente: remarcar uma banca
            # reprovada zera `banca.realizado_em`, e ler só essa coluna faria o
            # retrabalho pós-banca voltar a consumir trabalho vendido.
            banca_realizado_em=primeira_realizacao(
                bancas_por_escopo.get(escopo.id),
                _sessoes_da_banca(bancas_por_escopo.get(escopo.id), sessoes_por_banca),
            ),
        )
        for escopo in escopos
    }

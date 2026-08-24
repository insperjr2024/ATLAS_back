"""⭐ A janela do escopo — o conceito central da reformulação do cronograma.

Cada escopo vendido tem **três números que nunca se misturam**:

    vendidos (imutável)  ·  ajustados (autorizados)  ·  atraso (derivado)

- **Vendidos** é o registro comercial. Nunca sobrescrito: o sistema continua
  mostrando *vendidos 20 · ajustados 10*, nunca "vendidos 30". Sobrescrever
  apagaria a diferença entre vender 30 e estourar 20.
- **Ajustados** são dias extras que a diretoria autorizou, e só nos 3 primeiros
  dias úteis da janela.
- **Atraso** não tem coluna e não tem autorização: é o que passou de
  *vendidos + ajustados*. É consequência, nunca permissão.

A **janela** vai da reunião inicial (`projeto_escopo.data_inicio`) até
*vendidos + ajustados* dias úteis depois dela. É ela que o calendário desenha
como faixa do escopo, e é dentro dela que etapas e banca devem caber — mas só
a banca é bloqueada (§15: pintar além da janela avisa, não impede).

Em cima de `dias_uteis.py`, que responde "o que é um dia útil". Como lá, tudo
aqui é **função pura**: quem chama carrega o banco uma vez e passa os dados, e
`referencia` é injetável para o teste não precisar congelar o relógio.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Set, Tuple, Union

from src.utils.ambientacao import fim_da_ambientacao
from src.utils.dias_uteis import (
    DOMINGO,
    SABADO,
    contar_dias_uteis,
    dias_uteis_de_atraso,
    listar_dias_uteis,
    normalizar,
    somar_dias_uteis,
)

#: §8: o prazo para PEDIR dias de ajuste tem **duas réguas**, e qual delas vale
#: depende da posição do escopo na lista *Escopos vendidos* do projeto:
#:
#: - o **primeiro escopo** vale até o ÚLTIMO DIA DA AMBIENTAÇÃO — o "kickoff".
#:   É nela que a equipe conhece o projeto e descobre que os dias vendidos não
#:   fecham, então é ali que a conversa com a diretoria tem que caber, antes de
#:   a largada abrir a janela. Ver `prazo_pelo_kickoff`.
#: - os **demais escopos** entram num projeto que já rodou a ambientação (ela é
#:   do projeto, e acontece uma vez só): para eles continuam valendo estes 3
#:   dias úteis, contados da reunião inicial do próprio escopo, que é o dia 1
#:   (§20.2).
#:
#: ⚠ Isto mudou em 2026-08-23. Antes os 3 dias úteis valiam para todo escopo, e
#: a ambientação era uma EXCEÇÃO que apenas antecipava o pedido; hoje ela é a
#: régua do primeiro escopo, e o prazo dele fecha junto com ela.
PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS = 3

#: §13: remarcar uma banca que acontece dentro desta folga exige diretoria,
#: mesmo dentro da janela — os avaliadores já estão escalados.
FOLGA_LIVRE_REMARCACAO_DIAS_UTEIS = 5

_UM_DIA = timedelta(days=1)

#: Janela de ⏸ Pausado, SEMIABERTA `[inicio, fim)` — a mesma convenção de
#: `contagem_dias.JanelaPausa`. Fica repetida aqui como tipo local só para não
#: criar import circular: `contagem_dias` já importa deste módulo.
JanelaPausa = Tuple[date, date]


def _em_pausa(dia: date, janelas_pausa: Iterable[JanelaPausa]) -> bool:
    return any(inicio <= dia < fim for inicio, fim in janelas_pausa)


def _somar_dias_uteis_fora_da_pausa(
    inicio: date,
    quantidade: int,
    dias_nao_letivos: Iterable[date],
    janelas_pausa: Iterable[JanelaPausa] = (),
) -> date:
    """`somar_dias_uteis`, mas dia de projeto ⏸ Pausado não gasta janela.

    ⭐ Sem isso a janela ficava dessincronizada do consumo: `contagem_dias` já
    desconta a pausa dos dias consumidos, então dez dias parados congelavam o
    contador mas **não** empurravam o fim da janela. O escopo ganhava atraso
    que não existia e a banca continuava barrada pela data original — punição
    por uma parada que a própria diretoria decretou.

    Sem pausa nenhuma delega para `somar_dias_uteis`, que é o caminho de quase
    todo mundo e tem o teto de segurança contra calendário carregado errado.
    """
    pausas = list(janelas_pausa)
    if not pausas:
        return somar_dias_uteis(inicio, quantidade, dias_nao_letivos)
    if quantidade <= 0:
        return inicio

    nao_letivos = normalizar(dias_nao_letivos)
    contados = 0
    atual = inicio
    limite = inicio + timedelta(days=365 * 5)
    while atual <= limite:
        if (
            atual.weekday() not in (SABADO, DOMINGO)
            and atual not in nao_letivos
            and not _em_pausa(atual, pausas)
        ):
            contados += 1
            if contados == quantidade:
                return atual
        atual += timedelta(days=1)
    raise ValueError(
        f"Não foi possível somar {quantidade} dias úteis a partir de {inicio}: "
        "o calendário não letivo (ou as pausas do projeto) cobrem um intervalo "
        "grande demais."
    )


@dataclass(frozen=True)
class JanelaEscopo:
    """A janela de um escopo, com tudo que se deriva dela numa leitura só."""

    data_inicio: Optional[date]
    dias_vendidos: int
    dias_ajustados: int
    #: O último dia da janela. `None` enquanto o escopo não tem reunião inicial
    #: — §20.4: escopo sem ela não tem janela, não consome dias e não pode ter
    #: banca marcada.
    fim: Optional[date]
    #: Último dia em que ainda cabe PEDIR dias de ajuste.
    prazo_pedido_ajuste: Optional[date]
    #: O prazo ainda está aberto na data de referência.
    pedido_ajuste_aberto: bool

    @property
    def aberta(self) -> bool:
        """A janela existe (o escopo teve reunião inicial)."""
        return self.fim is not None

    @property
    def dias_totais(self) -> int:
        return self.dias_vendidos + self.dias_ajustados


def primeiro_escopo_id(escopos: Iterable) -> Optional[int]:
    """⭐ Qual escopo é o PRIMEIRO do projeto — a régua que escolhe o prazo.

    "Primeiro" é a posição na lista *Escopos vendidos* do cadastro, a mesma que
    as setinhas reordenam: `ordem`, com `id` desempatando quem nunca foi
    reordenado (todo mundo nasce com `ordem` 0). É a mesma ordenação de
    `ProjetoEscopoRepository.get_by_projeto`, escrita aqui como função pura
    porque quem decide o prazo nem sempre tem a lista vindo de lá — a fila da
    diretoria carrega os escopos de todos os projetos de uma vez.

    ⚠ Escopo **cancelado continua contando**: a lista é a que está na tela, e
    quem quiser passar a vez reordena. Um filtro invisível aqui mudaria o prazo
    de um escopo sem nada ter mudado na tela de quem o lê.
    """
    escopos = list(escopos)
    if not escopos:
        return None
    return min(escopos, key=lambda e: (getattr(e, "ordem", 0) or 0, e.id)).id


def prazo_pelo_kickoff(
    status_projeto: Optional[str],
    inicio_da_ambientacao: Optional[date],
    dias_ambientacao: int,
    dias_nao_letivos_globais: Iterable[date],
) -> Optional[date]:
    """O último dia da ambientação, quando é ELE o prazo do pedido (§8).

    Serve só o PRIMEIRO escopo — quem chama já sabe disso e passa `None` para
    os demais (`primeiro_escopo_id`). Para o primeiro, o prazo fecha junto com
    a ambientação: é ela que existe para a equipe conhecer o projeto, e é lá
    que se descobre que os dias vendidos não fecham. Depois dela a largada já
    aconteceu, o time está produzindo, e o que passar da janela é atraso.

    `None` = este escopo cai na régua dos 3 dias úteis da reunião inicial, e
    são dois os motivos:

    - **o projeto não tem ambientação** (sem kickoff, ou zero dias): não existe
      "último dia" de coisa nenhuma para servir de prazo;
    - **o projeto ainda está Vendido**: antes da ambientação não há equipe em
      campo para descobrir que os dias não fecham, e o próprio kickoff ainda
      pode mudar de lugar. O STATUS decide a entrada e a DATA segura a saída —
      a mesma convenção de `ambientacao_em_curso`, e o motivo pelo qual um
      status atrasado (a virada automática que ainda não rodou) não reabre o
      prazo.

    ⚠ Dias não letivos **globais** (`frente_id` nulo), como em
    `EncerrarAmbientacaoUseCase`: a ambientação é do projeto inteiro, e um
    recesso de uma frente só não pode esticá-la para as outras.
    """
    if status_projeto == "vendido":
        return None
    return fim_da_ambientacao(
        inicio_da_ambientacao, dias_ambientacao, dias_nao_letivos_globais
    )


def calcular_janela(
    data_inicio: Optional[date],
    dias_uteis_vendidos: int,
    dias_uteis_ajustados: int,
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
    janelas_pausa: Iterable[JanelaPausa] = (),
    prazo_do_kickoff: Optional[date] = None,
) -> JanelaEscopo:
    """A janela do escopo e o prazo de pedido, numa estrutura só.

    Devolve uma janela FECHADA (sem `fim`) quando não há reunião inicial, em
    vez de levantar: escopo cadastrado na venda e ainda não iniciado é estado
    normal, e quem chama não deveria precisar de um `if` antes de perguntar.

    Calendário carregado errado (o ano inteiro como não letivo) faz
    `somar_dias_uteis` levantar `ValueError`; aqui isso vira janela sem fim,
    pelo mesmo motivo que a faixa de ambientação some em `get_cronograma` — a
    tela toda não pode cair por causa de um calendário ruim.

    `janelas_pausa` desloca o fim **e** o prazo do pedido: enquanto o projeto
    está ⏸ Pausado ninguém deveria estar trabalhando, então nem a janela corre
    nem os 3 dias úteis para perceber que os dias vendidos não fecham.

    ⭐ `prazo_do_kickoff` (o último dia da ambientação, vindo de
    `prazo_pelo_kickoff`) SUBSTITUI os 3 dias úteis quando informado — é o
    prazo do primeiro escopo. Repare que ele vale **mesmo sem reunião
    inicial**: o pedido do primeiro escopo nasce justamente antes da largada, e
    é por isso que a janela fechada abaixo ainda devolve prazo.
    """
    referencia = referencia or date.today()

    if data_inicio is None:
        # Sem reunião inicial não há JANELA — mas pode haver PRAZO, e é o caso
        # normal do primeiro escopo durante a ambientação.
        return JanelaEscopo(
            data_inicio=None,
            dias_vendidos=dias_uteis_vendidos,
            dias_ajustados=dias_uteis_ajustados,
            fim=None,
            prazo_pedido_ajuste=prazo_do_kickoff,
            pedido_ajuste_aberto=(
                prazo_do_kickoff is not None and referencia <= prazo_do_kickoff
            ),
        )

    total = dias_uteis_vendidos + dias_uteis_ajustados
    try:
        fim = _somar_dias_uteis_fora_da_pausa(
            data_inicio, total, dias_nao_letivos, janelas_pausa
        )
    except ValueError:
        fim = None

    if prazo_do_kickoff is not None:
        prazo = prazo_do_kickoff
    else:
        try:
            prazo = _somar_dias_uteis_fora_da_pausa(
                data_inicio, PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS, dias_nao_letivos, janelas_pausa
            )
        except ValueError:
            # Calendário impossível: some o prazo, não a tela. As duas contas
            # são independentes de propósito — a do fim caminha *vendidos +
            # ajustados* dias e é a que estoura primeiro num calendário ruim,
            # e não há motivo para ela levar o prazo junto.
            prazo = None

    return JanelaEscopo(
        data_inicio=data_inicio,
        dias_vendidos=dias_uteis_vendidos,
        dias_ajustados=dias_uteis_ajustados,
        fim=fim,
        prazo_pedido_ajuste=prazo,
        # ⭐ `<=`: o próprio dia do prazo ainda vale. Vale a data do PEDIDO,
        # não a da decisão (§20.1) — pedir no último dia e a diretoria
        # responder três dias depois continua sendo ajuste.
        pedido_ajuste_aberto=prazo is not None and referencia <= prazo,
    )


def dentro_da_janela(dia: Union[date, datetime, None], janela: JanelaEscopo) -> bool:
    """O dia cabe na janela do escopo? É a régua do §9 para a banca.

    Sem janela, nada cabe — e é isso que impede marcar banca de escopo que
    ainda não teve reunião inicial (§20.4).
    """
    if dia is None or not janela.aberta:
        return False
    alvo = dia.date() if isinstance(dia, datetime) else dia
    return janela.data_inicio <= alvo <= janela.fim


def dias_de_atraso(
    janela: JanelaEscopo,
    banca_realizado_em: Union[date, datetime, None],
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
    janelas_pausa: Iterable[JanelaPausa] = (),
) -> int:
    """§10: dias úteis entre o fim da janela e o dia em que a banca ACONTECEU.

    Enquanto a banca não acontece, o atraso corrente corre até hoje — é o
    número que cresce sozinho na tela e cobra ação.

    Banca realizada dentro da janela dá zero, porque `dias_uteis_de_atraso` já
    devolve 0 quando o prazo ainda não venceu. Escopo sem janela também dá
    zero: sem reunião inicial não há de onde atrasar.

    Dia de projeto ⏸ Pausado não é atraso, pela mesma razão que não consome
    janela: a parada foi decisão de quem cobra o atraso.
    """
    if not janela.aberta:
        return 0

    referencia = referencia or date.today()
    if banca_realizado_em is None:
        fim = referencia
    else:
        fim = (
            banca_realizado_em.date()
            if isinstance(banca_realizado_em, datetime)
            else banca_realizado_em
        )

    return atraso_sem_pausa(janela.fim, fim, dias_nao_letivos, janelas_pausa)



def atraso_sem_pausa(
    prazo: date,
    referencia: date,
    dias_nao_letivos: Iterable[date],
    janelas_pausa: Iterable[JanelaPausa] = (),
) -> int:
    """Dias úteis entre `prazo` e `referencia`, tirando os de projeto ⏸ Pausado.

    ⭐ **Extraída porque tem dois donos.** A conta vivia dentro de
    `dias_de_atraso` (a régua da JANELA do escopo) e a régua da BANCA — o pilar
    do §7.4, em `atraso_monitoramento` — não tinha como aplicá-la. O resultado
    era a mesma tela discordando de si mesma sobre um projeto parado: o card de
    escopos descontava a pausa e o de projetos não, e o número maior era o
    errado.

    Dia de pausa não é atraso pela mesma razão que não consome janela: a parada
    foi decisão de quem cobra o atraso.
    """
    bruto = dias_uteis_de_atraso(prazo, referencia, dias_nao_letivos)
    pausas = list(janelas_pausa)
    if not bruto or not pausas:
        return bruto

    parados = [
        dia
        for dia in listar_dias_uteis(prazo + _UM_DIA, referencia, dias_nao_letivos)
        if _em_pausa(dia, pausas)
    ]
    return max(0, bruto - len(parados))

def primeira_realizacao(banca, sessoes=()) -> Union[date, datetime, None]:
    """⭐ A PRIMEIRA vez que a banca aconteceu — em qualquer tentativa (§9).

    ⚠ **Não é `banca.realizado_em`.** Aquela coluna descreve a tentativa
    CORRENTE, e remarcar uma banca reprovada a zera (`_campos_da_remarcacao`).
    Quem lê só ela conclui que a banca nunca aconteceu, e aí:

    - o escopo volta a "em contagem" e os dias do RETRABALHO passam a consumir
      trabalho vendido, um por dia, sem ninguém trabalhar no que foi vendido;
    - o atraso cresce junto, cobrando do time dias que são correção da banca;
    - a coluna Correções zera, e o retrabalho entre as duas bancas fica sem
      lugar nenhum na tela.

    O mesmo vale, mais discretamente, quando as duas tentativas já
    aconteceram: usar a data da 2ª faz os dias ENTRE elas contarem como
    trabalho vendido, quando são exatamente o retrabalho que a 1ª apontou.

    A régua certa é a primeira: dali em diante o que se pinta é correção,
    independentemente de quantas bancas vieram depois.
    """
    realizadas = [s.realizado_em for s in sessoes if getattr(s, "realizado_em", None)]
    if realizadas:
        return min(realizadas)
    # Banca anterior a `banca_sessao`, ou sem sessão registrada.
    return getattr(banca, "realizado_em", None)


def marco_das_correcoes(
    banca_realizado_em: Union[date, datetime, None],
    data_entrega_real: Optional[date],
) -> Optional[date]:
    """A data a partir da qual o escopo está EM CORREÇÕES.

    ⚠️ **Correção não é "dia de ajuste".** São dois conceitos que a plataforma
    já confundiu por usarem a mesma palavra:

    - **dias de ajuste** (`dias_uteis_ajustados`) aumentam a JANELA do escopo.
      São dias de trabalho vendido que faltaram, pedidos à diretoria nos 3
      primeiros dias úteis depois da largada;
    - **correções** são o tempo gasto DEPOIS da banca arrumando o que ela
      apontou. Não aumentam janela nenhuma, não se pedem a ninguém, e nascem
      fora da janela por definição.

    ⭐ **A banca realizada manda.** Dali em diante, tudo que se mexe no
    cronograma daquele escopo é correção — é justamente entre a banca e a
    entrega ao cliente que as correções apontadas pela avaliação acontecem.

    A entrega é o fallback: escopo antigo, entregue antes de existir registro de
    realização, ainda precisa contar as correções de algum lugar. `None` = o
    escopo ainda está no trabalho vendido.
    """
    if banca_realizado_em is not None:
        return (
            banca_realizado_em.date()
            if isinstance(banca_realizado_em, datetime)
            else banca_realizado_em
        )
    return data_entrega_real


def dias_de_correcao(
    etapas: Iterable,
    inicio_das_correcoes: Optional[date],
    dias_nao_letivos: Iterable[date],
) -> int:
    """§11: dias úteis pintados DEPOIS que o escopo entrou em correções.

    Não consomem dias do escopo e não são atraso — é métrica própria, que diz
    que aquele escopo precisou de correções e quantos dias elas levaram.

    ⚠ Conta **dias distintos**, não a soma das etapas: duas etapas que rodam no
    mesmo dia são um dia de correção, não dois. É o mesmo motivo pelo qual a
    faixa do escopo cede a célula para a etapa em vez de somar as duas.

    Sem banca realizada (nem entrega) não há correção: o escopo ainda está no
    trabalho vendido, e tudo que é pintado é trabalho normal.
    """
    if inicio_das_correcoes is None:
        return 0

    dias: Set[date] = set()
    for etapa in etapas:
        if etapa.data_fim <= inicio_das_correcoes:
            continue
        # Só o trecho posterior ao marco: etapa que o atravessa conta a metade
        # de depois, não ela inteira.
        inicio = max(etapa.data_inicio, inicio_das_correcoes + _UM_DIA)
        dias.update(listar_dias_uteis(inicio, etapa.data_fim, dias_nao_letivos))

    return len(dias)


def dias_parados(
    kickoff: Optional[date],
    datas_marcadas: Iterable[date],
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
) -> int:
    """§16: dias úteis EM BRANCO — sem nenhuma marcação no cronograma.

    Do kickoff até hoje (ou até o fim do projeto, quando quem chama passa a
    referência dele). Etapa, reunião, banca e entrega contam como marcação;
    dia não útil não conta como parado, porque ninguém deveria estar
    trabalhando nele.

    É a métrica do Monitoramento — não da Visão geral. Ela responde "este
    projeto está andando?", que é pergunta de quem acompanha o portfólio, não
    de quem está dentro do projeto.

    Sem kickoff devolve zero: o projeto ainda não começou, e contar daí seria
    cobrar parada de quem não largou.
    """
    if kickoff is None:
        return 0

    referencia = referencia or date.today()
    uteis = listar_dias_uteis(kickoff, referencia, dias_nao_letivos)
    if not uteis:
        return 0

    marcados = {
        d.date() if isinstance(d, datetime) else d for d in datas_marcadas if d is not None
    }
    return len([dia for dia in uteis if dia not in marcados])


def dias_uteis_ate_a_banca(
    data_hora: Union[date, datetime, None],
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
) -> Optional[int]:
    """Quantos dias úteis faltam para a banca acontecer (§20.3).

    É o que decide o gate do §13: remarcar banca que acontece dentro dos
    próximos 5 dias úteis exige diretoria, mesmo dentro da janela, porque os
    avaliadores já reservaram a agenda.

    `None` para banca sem data — não há o que contar, e o gate não se aplica.
    Banca no passado devolve 0.
    """
    if data_hora is None:
        return None

    referencia = referencia or date.today()
    alvo = data_hora.date() if isinstance(data_hora, datetime) else data_hora
    if alvo <= referencia:
        return 0
    # Intervalo aberto em hoje: a banca de amanhã está a 1 dia útil, não 2.
    return contar_dias_uteis(referencia + _UM_DIA, alvo, dias_nao_letivos)

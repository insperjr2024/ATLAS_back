"""O cálculo de atraso do §7.4, num módulo só.

Três lugares precisam responder "este projeto está atrasado?" — o placar da
gestão (§7.1), a aba Atrasos por projeto e a mesma aba por coordenador. Se
cada um implementasse à sua maneira, divergiriam no primeiro caso de borda.

**Dias de atraso são ÚTEIS**, pelo calendário do Insper — igual ao resto do
sistema. O texto do §7.4 dizia "corridos", mas a diretoria confirmou em
2026-08-04 que a régua é dias úteis: cobrar fim de semana, feriado e semana de
provas seria cobrar tempo em que o time não tinha como trabalhar. Uma banca que
venceu na sexta e não aconteceu até segunda atrasou 1 dia, não 3.

Consequência prática: quem chama precisa passar os dias não letivos. Não há
mais régua diferente entre esta aba e a de Execução — se aparecer código
falando em "corridos", está desatualizado.

⭐ **O único pilar é a banca.** "Um escopo está atrasado quando passa da data
da sua banca sem que ela tenha acontecido" — o marco sob controle do time.

⚠ Desde 2026-08-12 é literalmente o único: o atraso da ENTREGA ao cliente saiu
dos insights por decisão da diretoria. Ele media a agenda do cliente, não o
trabalho do time, e inflava o alerta de projetos cuja banca tinha acontecido no
prazo. `projeto_escopo.tipo_atraso_entrega` e a rota que o classifica continuam
existindo; o que sumiu foi o motivo derivado dele.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

from src.utils.banca_status import ATRASADA, calcular_status_banca
from src.utils.janela_escopo import atraso_sem_pausa


@dataclass
class MotivoAtraso:
    #: Hoje só existe `"banca"`. `entrega_interna`/`entrega_externa` saíram em
    #: 2026-08-12 (ver o comentário no lugar do antigo Pilar 2); o campo
    #: continua sendo string, e não um literal, porque as notas de justificativa
    #: já gravadas com os tipos antigos seguem no banco e precisam casar.
    tipo: str
    descricao: str
    dias: int
    projeto_escopo_id: Optional[int] = None
    escopo_nome: str = ""
    #: A data que venceu. "48 dias" diz o tamanho do buraco; a data diz QUANDO
    #: ele abriu, que é o que permite cruzar com o que mais aconteceu naquela
    #: semana e cobrar o coordenador com contexto.
    data_referencia: Optional[date] = None


@dataclass
class AtrasoProjeto:
    projeto_id: int
    motivos: List[MotivoAtraso] = field(default_factory=list)

    @property
    def atrasado(self) -> bool:
        return bool(self.motivos)

    @property
    def dias_totais(self) -> int:
        return sum(m.dias for m in self.motivos)

    @property
    def atrasado_por_banca(self) -> bool:
        """O que conta para o placar da gestão — só o marco do time."""
        return any(m.tipo == "banca" for m in self.motivos)


def calcular_atraso_projeto(
    projeto_id: int,
    escopos,
    bancas_por_escopo: Dict[int, object],
    nomes_escopo: Dict[int, str],
    referencia: Optional[date] = None,
    dias_nao_letivos: Optional[Iterable[date]] = None,
    janelas_pausa: Iterable[tuple] = (),
) -> AtrasoProjeto:
    """§7.4: quais bancas deste projeto já deviam ter acontecido e não aconteceram.

    ⭐ **Quatro recortes, e cada um responde a uma pergunta que a diretoria não
    tem como cobrar.** Um escopo só gera atraso de banca quando:

    1. não está **cancelado** — não existe mais trabalho a cobrar;
    2. não está **entregue** — o escopo acabou; uma banca não registrada de um
       escopo já entregue é pendência de cadastro, não atraso de execução, e
       antes disto crescia um dia útil por dia para sempre;
    3. **teve reunião inicial** (§20.4) — sem ela a janela nem abriu, e a data
       da banca é um rascunho: cobrar dela é cobrar de um escopo que não
       começou;
    4. a data da banca **já passou** — `<`, não `<=`.

    ⚠ **O 4 é o que tirava o placar da gestão do ar.** A referência era
    `datetime.max.time()` (23:59 de hoje), então uma banca marcada para hoje às
    16h já contava como atrasada às 8h da manhã, com "0 dias" — e o MESMO
    projeto aparecia em "bancas próximas" da Visão geral. A mesma banca era
    agenda da semana e motivo de atraso. O dia da banca é dela; o atraso começa
    no dia seguinte.

    ⭐ **A pausa é descontada.** `janelas_pausa` chega opcional para não quebrar
    quem já chamava, mas quem monitora deve passar: ⏸ Pausado é decisão da
    própria diretoria, e cobrar atraso pelos dias em que ela mandou parar é
    cobrar de si mesma. É a mesma régua que `janela_escopo.dias_de_atraso` já
    aplicava do outro lado — sem ela, as duas metades da tela discordavam sobre
    o mesmo projeto parado.

    ⚠ **Dias ÚTEIS, e não corridos como o §7.4 escreve.** A diretoria trocou a
    régua em 2026-08-04: cobrar fim de semana, feriado e semana de provas seria
    cobrar tempo em que o time não tinha como trabalhar.
    """
    referencia = referencia or date.today()
    nao_letivos = dias_nao_letivos or []
    resultado = AtrasoProjeto(projeto_id=projeto_id)
    # ⚠ Meia-noite de HOJE, não 23:59. É o que faz a banca marcada para hoje
    # ainda não estar atrasada — ver o item 4 do docstring.
    inicio_do_dia = datetime.combine(referencia, datetime.min.time())

    for escopo in escopos:
        if escopo.status == "cancelado":
            continue
        # O escopo acabou: o que falta é registro, não trabalho.
        if escopo.status == "entregue" or getattr(escopo, "data_entrega_real", None):
            continue
        # §20.4: sem reunião inicial não há janela, e a data da banca é rascunho.
        if not getattr(escopo, "data_inicio", None):
            continue

        nome = nomes_escopo.get(escopo.id, "escopo")
        banca = bancas_por_escopo.get(escopo.id)
        if not banca or not banca.data_hora:
            continue

        status = calcular_status_banca(banca.data_hora, banca.realizado_em, inicio_do_dia)
        if status != ATRASADA:
            continue

        dias = atraso_sem_pausa(
            banca.data_hora.date(), referencia, nao_letivos, janelas_pausa
        )
        resultado.motivos.append(
            MotivoAtraso(
                tipo="banca",
                descricao=f"banca de {nome} venceu há {dias} dias úteis sem acontecer",
                dias=dias,
                projeto_escopo_id=escopo.id,
                escopo_nome=nome,
                data_referencia=banca.data_hora.date(),
            )
        )

    # ⚠ **Aqui havia um "Pilar 2": o atraso da ENTREGA ao cliente.**
    #
    # Removido a pedido da diretoria (2026-08-12). Ele media a agenda do
    # cliente e não o trabalho do time: um escopo com banca feita no prazo
    # aparecia com "8 dias de atraso" porque a apresentação ainda não tinha
    # sido marcada, e o número crescia sozinho.
    #
    # `projeto_escopo.tipo_atraso_entrega` e a rota que o classifica continuam
    # existindo — o dado não foi apagado, só deixou de virar alerta.
    return resultado


def justificativa_cobrindo(motivo, justificativas):
    """§7.4: qual nota da diretoria já responde por ESTE motivo — ou `None`.

    ⭐ **Função de módulo, e não método, porque tem dois donos.** A aba Atrasos
    a usa para pintar o selo "justificado"; a fila de Aprovações, para decidir
    se ainda precisa cobrar. Enquanto morou só na primeira, a segunda usava um
    atalho — um set de `projeto_id` — e as duas telas discordavam: uma nota de
    junho sobre um escopo entregue fazia um atraso de agosto sumir da fila,
    mas continuar vermelho na aba ao lado.

    O aviso é POR MOTIVO (escopo + tipo), não por projeto: o mesmo escopo pode
    estar atrasado em banca E entrega ao mesmo tempo, e uma nota só cobre as
    duas se for geral. Ordem de especificidade, da mais ampla à mais estreita:
      1. nota geral do projeto (sem escopo) — cobre qualquer motivo;
      2. nota do escopo sem tipo — cobre os motivos DESTE escopo;
      3. nota do escopo com tipo — cobre só ESTE motivo.

    Uma nota só conta para o atraso ATUAL: se o atraso deste motivo começou
    depois da nota, ela era de uma rodada anterior (já resolvida).

    Devolve a mais RECENTE que cobre — "o que a diretoria disse por último".
    """

    def cobre(j) -> bool:
        if j.projeto_escopo_id is not None and j.projeto_escopo_id != motivo.projeto_escopo_id:
            return False
        if j.tipo is not None and j.tipo != motivo.tipo:
            return False
        if motivo.data_referencia is None:
            return True
        return j.registrado_em.date() >= motivo.data_referencia

    candidatas = [j for j in justificativas if cobre(j)]
    if not candidatas:
        return None
    return max(candidatas, key=lambda j: j.registrado_em)

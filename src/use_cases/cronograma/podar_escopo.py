"""Mover a reunião inicial PODA o cronograma do escopo (§5.4).

**Por que podar, e não zerar.** A data da reunião inicial é a origem da
janela do escopo: etapas pintadas, data da banca e entrega planejada foram
desenhadas *a partir* dela. Mudar a origem move a janela — mas mover a janela
não invalida tudo o que estava dentro dela.

Esta versão apaga só o que **não cabe mais**:

- etapa inteiramente fora da janela nova some;
- etapa que cruza uma das bordas é **aparada** até a borda, e o pedaço que
  ficou dentro sobrevive;
- etapa inteiramente dentro não é tocada;
- a data da banca só cai se ficou fora da janela nova.

Antes daqui, mudar a largada apagava o cronograma inteiro. Era previsível,
mas caro: um escopo de seis etapas que andava dois dias perdia as seis, e o
coordenador redesenhava à mão um cronograma que continuava válido. A régua
passou a ser a janela nova — quem estava dentro dela continua dentro.

**Duas coisas barram a poda inteira:**

- **banca já realizada** — desmarcá-la destruiria presença, votos e o resultado
  que liberou a entrega ao cliente (§5.5), e depois dela o que se pinta é
  correção, que nasce fora da janela por definição (`_exigir_dentro_da_janela`
  abre exceção justamente aí). Podar apagaria o retrabalho;
- **escopo já entregue** — a janela está congelada (§5.4) e reabrir o início
  mexeria em dias já contados.

Nos dois casos a resposta é recusar a mudança, não podar pela metade.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_repository import CronogramaEtapaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.utils.contagem_dias import derivar_janelas_pausa
from src.utils.exceptions import RegraDeNegocioError
from src.utils.janela_escopo import JanelaEscopo, calcular_janela, dentro_da_janela


def exigir_poda_permitida(db: Session, projeto_escopo_id: int) -> None:
    """As travas que impedem podar. Levanta `RegraDeNegocioError` explicando.

    Separada da poda de propósito: quem só quer saber "posso mexer nesta
    data?" — a tela, antes de oferecer a mudança — chama isto sem apagar nada.
    """
    escopo = ProjetoEscopoRepository(db).get_by_id(projeto_escopo_id)
    if not escopo:
        raise RegraDeNegocioError("Escopo não encontrado")

    if escopo.data_entrega_real:
        raise RegraDeNegocioError(
            "Este escopo já foi entregue ao cliente, e a janela dele está fechada. "
            "Mudar a reunião inicial mexeria em dias já contados — não dá para desfazer "
            "uma entrega mudando a data da largada."
        )

    banca = BancaRepository(db).get_by_projeto_escopo(projeto_escopo_id)
    if banca and banca.realizado_em:
        raise RegraDeNegocioError(
            "A banca deste escopo já aconteceu. Mudar a reunião inicial reposiciona a "
            "janela, e o que fica fora dela é apagado — inclusive as correções pintadas "
            "depois da banca, que nascem fora da janela. Se a data da reunião está "
            "errada, registre a correção no histórico do projeto."
        )


@dataclass
class Poda:
    """O plano da poda: o que sai, o que encolhe e o que continua igual.

    Plano e execução são separados porque o mesmo cálculo tem dois usos: a
    tela pergunta "o que eu perco se mudar para o dia 12?" antes de decidir, e
    o `execute` aplica depois. Fossem duas contas, elas divergiriam.
    """

    janela: JanelaEscopo
    #: Etapas que não têm um único dia dentro da janela nova.
    apagar: List = field(default_factory=list)
    #: `(etapa, novo_inicio, novo_fim)` — cruza uma borda e é encurtada até ela.
    aparar: List[Tuple] = field(default_factory=list)
    #: A banca a desmarcar, quando a data dela caiu fora da janela nova.
    banca_fora: Optional[object] = None
    #: A entrega planejada ficou ANTES da largada nova — data impossível.
    limpar_entrega_planejada: bool = False

    @property
    def mexe_em_alguma_coisa(self) -> bool:
        return bool(
            self.apagar or self.aparar or self.banca_fora or self.limpar_entrega_planejada
        )


def _janela_da_nova_largada(db: Session, escopo, nova_largada: Optional[date]) -> JanelaEscopo:
    """A janela que o escopo passa a ter com a largada nova.

    Os **dias ajustados são mantidos**. Eles são dias de trabalho vendido que
    faltaram, autorizados para ESTE escopo — não para aquele dia específico.
    Zerá-los aqui encolheria a janela nova e mandaria para a poda etapas que a
    diretoria já tinha autorizado; quem perdesse os dias teria de pedir de novo
    um prazo que, na largada nova, provavelmente já venceu.
    """
    dias_nao_letivos = [d.data for d in DiaNaoLetivoRepository(db).get_do_escopo(escopo)]
    janelas_pausa = derivar_janelas_pausa(
        ProjetoStatusHistoricoRepository(db).get_by_projeto(escopo.projeto_id)
    )
    return calcular_janela(
        nova_largada,
        escopo.dias_uteis_vendidos,
        escopo.dias_uteis_ajustados,
        dias_nao_letivos,
        janelas_pausa=janelas_pausa,
    )


def planejar_poda(db: Session, projeto_escopo_id: int, nova_largada: Optional[date]) -> Poda:
    """O que a largada nova faz com o cronograma — sem gravar nada.

    `nova_largada` a `None` é o escopo que PERDE a reunião inicial (ela foi
    para outro escopo): sem largada não há janela, nada cabe, e a poda vira o
    reset inteiro de antes.

    **Calendário impossível não poda.** Se o não letivo carregado cobre um
    intervalo grande demais, `calcular_janela` devolve janela sem fim — e aí
    não dá para dizer o que está dentro. Apagar por dúvida seria o pior
    desfecho, então a poda fica vazia e o cronograma segue como está.
    """
    escopo = ProjetoEscopoRepository(db).get_by_id(projeto_escopo_id)
    if not escopo:
        raise RegraDeNegocioError("Escopo não encontrado")

    janela = _janela_da_nova_largada(db, escopo, nova_largada)
    poda = Poda(janela=janela)

    if nova_largada is not None and not janela.aberta:
        return poda

    etapas = CronogramaEtapaRepository(db).get_by_escopo(projeto_escopo_id)
    for etapa in etapas:
        if (
            not janela.aberta
            or etapa.data_fim < janela.data_inicio
            or etapa.data_inicio > janela.fim
        ):
            poda.apagar.append(etapa)
            continue
        novo_inicio = max(etapa.data_inicio, janela.data_inicio)
        novo_fim = min(etapa.data_fim, janela.fim)
        if (novo_inicio, novo_fim) != (etapa.data_inicio, etapa.data_fim):
            poda.aparar.append((etapa, novo_inicio, novo_fim))

    banca = BancaRepository(db).get_by_projeto_escopo(projeto_escopo_id)
    if banca and banca.data_hora and not dentro_da_janela(banca.data_hora, janela):
        poda.banca_fora = banca

    # A entrega ao cliente vem DEPOIS da janela (§5.5: só depois da banca), então
    # passar do fim é normal e não se mexe. Cair antes da largada é que não
    # existe — seria entrega prometida para antes de o escopo começar.
    if escopo.data_entrega_planejada and (
        janela.data_inicio is None or escopo.data_entrega_planejada < janela.data_inicio
    ):
        poda.limpar_entrega_planejada = True

    return poda


def resumir_a_poda(db: Session, projeto_escopo_id: int, nova_largada: Optional[date]) -> dict:
    """O levantamento do estrago, sem podar — para a confirmação na tela.

    Perguntar "tem certeza?" sem dizer o tamanho do estrago não é
    confirmação, é formulário. E agora o estrago costuma ser pequeno: dizer
    "1 etapa apagada e 2 aparadas" é o que separa esta mudança da anterior,
    que apagava as seis sem dizer quantas eram.
    """
    return _resumir(planejar_poda(db, projeto_escopo_id, nova_largada))


def _resumir(poda: Poda) -> dict:
    return {
        "etapas_apagadas": len(poda.apagar),
        "etapas_aparadas": len(poda.aparar),
        "janela_ate": poda.janela.fim.isoformat() if poda.janela.fim else None,
        "banca_desmarcada": (
            poda.banca_fora.data_hora.isoformat() if poda.banca_fora else None
        ),
    }


def podar_cronograma_do_escopo(
    db: Session, projeto_escopo_id: int, nova_largada: Optional[date]
) -> dict:
    """Apaga o que não cabe mais na janela e apara o que cruza a borda.

    Devolve o que mudou, para a tela dizer à pessoa o que aconteceu — "1 etapa
    apagada e 2 aparadas" é diferente de "nada".

    **A DATA da banca é apagada; a banca não.** Onze tabelas referenciam
    `banca` — remarcações, candidaturas, avaliações, sessões, pedidos de
    exceção de choque —, e nenhuma delas tem cascata. Apagar a linha estourava
    a FK de `projeto_remarcacao_banca` no primeiro escopo real que tinha
    remarcação. Sem data, a banca volta ao estado "não marcada": continua sendo
    a banca daquele escopo, e o coordenador remarca dentro da janela nova.

    **Quem estava alocado continua alocado.** Tirar as pessoas seria uma
    segunda decisão, que ninguém tomou — e refazer a escala custa mais que
    ajustar uma data. Se a data nova não servir para alguém, essa pessoa se
    desaloca, que é o gesto que já existe.

    **`cronograma_oficializado_em` fica.** Oficializar é um carimbo
    informativo que nunca trancou a edição (ver `OficializarCronogramaUseCase`):
    a poda é mais uma edição do cronograma oficializado, não o fim dele.
    """
    poda = planejar_poda(db, projeto_escopo_id, nova_largada)
    resumo = _resumir(poda)

    for etapa in poda.apagar:
        db.delete(etapa)
    for etapa, novo_inicio, novo_fim in poda.aparar:
        etapa.data_inicio = novo_inicio
        etapa.data_fim = novo_fim
    if poda.banca_fora:
        poda.banca_fora.data_hora = None
    if poda.limpar_entrega_planejada:
        escopo = ProjetoEscopoRepository(db).get_by_id(projeto_escopo_id)
        if escopo:
            escopo.data_entrega_planejada = None

    db.flush()
    return resumo

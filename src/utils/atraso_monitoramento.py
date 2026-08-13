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
from src.utils.dias_uteis import dias_uteis_de_atraso


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
) -> AtrasoProjeto:
    referencia = referencia or date.today()
    nao_letivos = dias_nao_letivos or []
    resultado = AtrasoProjeto(projeto_id=projeto_id)
    # A `referencia` precisa atravessar para o cálculo do status, senão ele cai
    # no relógio real e o "está atrasada?" discorda da data que se pediu — é o
    # mesmo cuidado que `banca_status.dias_de_atraso` já tomava internamente e
    # que se perdia aqui, porque esta função chamava o status sem passá-la.
    fim_do_dia = datetime.combine(referencia, datetime.max.time())

    for escopo in escopos:
        if escopo.status == "cancelado":
            continue
        nome = nomes_escopo.get(escopo.id, "escopo")

        # Pilar 1 — a banca venceu e não aconteceu.
        banca = bancas_por_escopo.get(escopo.id)
        if banca and banca.data_hora:
            status = calcular_status_banca(banca.data_hora, banca.realizado_em, fim_do_dia)
            if status == ATRASADA:
                dias = dias_uteis_de_atraso(banca.data_hora.date(), referencia, nao_letivos)
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
        # Removido a pedido da diretoria (2026-08-12). Ele gerava os motivos
        # `entrega_interna`/`entrega_externa` a partir de
        # `data_entrega_planejada` vencida, e o efeito era um insight que media
        # a agenda do cliente e não o trabalho do time: um escopo com banca
        # feita no prazo aparecia com "8 dias de atraso" porque a apresentação
        # ao cliente ainda não tinha sido marcada, e o número crescia sozinho.
        #
        # O que ficou é o pilar que o §7.4 sempre chamou de pilar: **a banca**.
        # `projeto_escopo.tipo_atraso_entrega` e a rota que o classifica
        # continuam existindo — o dado não foi apagado, só deixou de virar
        # alerta.

    return resultado

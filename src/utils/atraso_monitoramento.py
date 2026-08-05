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

**O pilar é a banca.** "Um escopo está atrasado quando passa da data da sua
banca sem que ela tenha acontecido" — o marco sob controle do time. A entrega
ao cliente depende da agenda dele e é acompanhada à parte, com a distinção
interno/externo (`projeto_escopo.tipo_atraso_entrega`).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

from src.utils.banca_status import ATRASADA, calcular_status_banca
from src.utils.dias_uteis import dias_uteis_de_atraso


@dataclass
class MotivoAtraso:
    #: "banca" | "entrega_interna" | "entrega_externa"
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

        # Pilar 2 — a entrega planejada passou e não saiu. Acompanhada à
        # parte porque pode escorregar por agenda do cliente; a diretoria
        # classifica interno/externo em `tipo_atraso_entrega`.
        if (
            escopo.data_entrega_planejada
            and not escopo.data_entrega_real
            and escopo.data_entrega_planejada < referencia
        ):
            dias = dias_uteis_de_atraso(
                escopo.data_entrega_planejada, referencia, nao_letivos
            )
            externo = escopo.tipo_atraso_entrega == "externo"
            resultado.motivos.append(
                MotivoAtraso(
                    tipo="entrega_externa" if externo else "entrega_interna",
                    descricao=(
                        f"entrega de {nome} atrasada há {dias} dias úteis"
                        + (" (agenda do cliente)" if externo else "")
                    ),
                    dias=dias,
                    projeto_escopo_id=escopo.id,
                    escopo_nome=nome,
                    data_referencia=escopo.data_entrega_planejada,
                )
            )

    return resultado

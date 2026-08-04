"""O cálculo de atraso do §7.4, num módulo só.

Três lugares precisam responder "este projeto está atrasado?" — o placar da
gestão (§7.1), a aba Atrasos por projeto e a mesma aba por coordenador. Se
cada um implementasse à sua maneira, divergiriam no primeiro caso de borda.

⚠ **Dias de atraso são CORRIDOS, não úteis.** O §7.4 é explícito. É fácil
errar por hábito e chamar `contar_dias_uteis`, já que todo o resto do sistema
conta em dias úteis — este é o ponto onde a régua muda.

**O pilar é a banca.** "Um escopo está atrasado quando passa da data da sua
banca sem que ela tenha acontecido" — o marco sob controle do time. A entrega
ao cliente depende da agenda dele e é acompanhada à parte, com a distinção
interno/externo (`projeto_escopo.tipo_atraso_entrega`).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from src.utils.banca_status import ATRASADA, calcular_status_banca, dias_de_atraso


@dataclass
class MotivoAtraso:
    #: "banca" | "entrega_interna" | "entrega_externa"
    tipo: str
    descricao: str
    dias: int
    projeto_escopo_id: Optional[int] = None
    escopo_nome: str = ""


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
) -> AtrasoProjeto:
    referencia = referencia or date.today()
    resultado = AtrasoProjeto(projeto_id=projeto_id)

    for escopo in escopos:
        if escopo.status == "cancelado":
            continue
        nome = nomes_escopo.get(escopo.id, "escopo")

        # Pilar 1 — a banca venceu e não aconteceu.
        banca = bancas_por_escopo.get(escopo.id)
        if banca and banca.data_hora:
            status = calcular_status_banca(banca.data_hora, banca.realizado_em)
            if status == ATRASADA:
                dias = dias_de_atraso(banca.data_hora, banca.realizado_em, referencia)
                resultado.motivos.append(
                    MotivoAtraso(
                        tipo="banca",
                        descricao=f"banca de {nome} venceu há {dias} dias sem acontecer",
                        dias=dias,
                        projeto_escopo_id=escopo.id,
                        escopo_nome=nome,
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
            dias = (referencia - escopo.data_entrega_planejada).days
            externo = escopo.tipo_atraso_entrega == "externo"
            resultado.motivos.append(
                MotivoAtraso(
                    tipo="entrega_externa" if externo else "entrega_interna",
                    descricao=(
                        f"entrega de {nome} atrasada há {dias} dias"
                        + (" (agenda do cliente)" if externo else "")
                    ),
                    dias=dias,
                    projeto_escopo_id=escopo.id,
                    escopo_nome=nome,
                )
            )

    return resultado

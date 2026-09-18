from datetime import datetime
from typing import Dict, List, NamedTuple, Optional, Tuple

from src.models.projeto_membro_model import ProjetoMembroModel


class ParDesempenho(NamedTuple):
    avaliador_id: int
    avaliado_id: int
    form_type: str  # papel do AVALIADO — decide qual formulário abrir (consultor|coordenador)
    projeto_id: int


#: ⭐ Quando o par coordenador↔coordenador passou a existir (2026-09-16, a
#: pedido) — antes dessa data dois coordenadores num mesmo projeto eram
#: tratados como "o mesmo papel" e nenhum entrava na fila do outro.
#:
#: ⚠ **Não é retroativo** (2026-09-18, corrigido): aplicar a regra nova a um
#: lote que já tinha ABERTO (e às vezes já fechado) antes dela existir cobra
#: de quem respondeu uma avaliação que não estava na régua quando preencheu —
#: foi o que aconteceu com a Finalização da BLEND I (lote de 09/09, a regra só
#: nasceu em 16/09). `calcular_pares_lote` recebe a data de CRIAÇÃO do lote e
#: só inclui o par coordenador↔coordenador quando o lote nasceu depois desta
#: data; lotes anteriores mantêm o comportamento antigo, congelado.
DATA_COORDENADOR_AVALIA_COORDENADOR = datetime(2026, 9, 16)


def calcular_pares_lote(
    membros: List[ProjetoMembroModel], lote_criado_em: Optional[datetime] = None
) -> List[ParDesempenho]:
    """`membros` = `projeto_membro` ativos (saiu_em IS NULL) dos projetos
    cobertos por um lote. Regra 2.3: dentro do mesmo projeto, todo mundo
    avalia todo mundo, exceto a si mesmo. `form_type` é o papel de quem está
    sendo avaliado, porque é isso que decide qual formulário
    (consultor/coordenador) abrir.

    ⭐ 2026-09-16, a pedido: coordenador AVALIA outro coordenador quando o
    projeto tem mais de um simultâneo (`validacao_equipe.py` permite dois
    coordenadores num projeto grande desde 2026-08-20) — mas só em lotes
    nascidos depois disso (`lote_criado_em`, ver `DATA_COORDENADOR_
    AVALIA_COORDENADOR`). Sem a data (`None`), assume a regra atual — é o
    caso de quem só quer testar a fila em si, sem lote de verdade por trás.
    A única exclusão que sobra sempre é autoavaliação (`avaliado.usuario_id
    == avaliador.usuario_id`)."""
    coord_avalia_coord = (
        lote_criado_em is None or lote_criado_em >= DATA_COORDENADOR_AVALIA_COORDENADOR
    )

    por_projeto: Dict[int, List[ProjetoMembroModel]] = {}
    for membro in membros:
        por_projeto.setdefault(membro.projeto_id, []).append(membro)

    pares: List[ParDesempenho] = []
    for projeto_id, time in por_projeto.items():
        for avaliador in time:
            for avaliado in time:
                if avaliado.usuario_id == avaliador.usuario_id:
                    continue
                if (
                    not coord_avalia_coord
                    and avaliador.papel == "coordenador"
                    and avaliado.papel == "coordenador"
                ):
                    continue
                pares.append(
                    ParDesempenho(
                        avaliador_id=avaliador.usuario_id,
                        avaliado_id=avaliado.usuario_id,
                        form_type=avaliado.papel,
                        projeto_id=projeto_id,
                    )
                )
    return pares


def deduplicar_pares(pares: List[ParDesempenho]) -> Dict[Tuple[int, int], dict]:
    """Colapsa (avaliador, avaliado) repetido em 2+ projetos do mesmo lote
    numa entrada só, guardando todos os `projeto_id` — as pendências
    precisam mostrar de qual projeto é cada avaliação faltante (regra 2.7).
    `form_type` é sempre igual dentro do mesmo par (mesmo avaliado = mesmo
    papel), então basta guardar o primeiro."""
    agregados: Dict[Tuple[int, int], dict] = {}
    for par in pares:
        chave = (par.avaliador_id, par.avaliado_id)
        if chave not in agregados:
            agregados[chave] = {"form_type": par.form_type, "projeto_ids": []}
        agregados[chave]["projeto_ids"].append(par.projeto_id)
    return agregados

"""A chave de uma combinação de frentes — montar, ler e enumerar.

Existe para que ninguém concatene id de frente à mão. A chave é a lista
ORDENADA de ids unida por `-` (`"1"`, `"1-2"`, `"1-2-3-4"`), e ordenar é o que
a torna única: sem isso, uma banca de Direito + Business gravaria `"2-1"` e não
acharia a regra que outra pessoa gravou como `"1-2"` para a mesma banca.
"""

from itertools import combinations
from typing import Iterable, List


def chave(frente_ids: Iterable[int]) -> str:
    """A chave da combinação. Repetidos colapsam — a banca com dois escopos de
    Business é da mesma combinação que a com um."""
    return "-".join(str(i) for i in sorted(set(frente_ids)))


def ler(chave_combinacao: str) -> List[int]:
    """Os ids de volta. `""` devolve lista vazia — a banca legada, sem frente
    nenhuma vinculada, cai aqui e não deve estourar."""
    if not chave_combinacao:
        return []
    return [int(p) for p in chave_combinacao.split("-") if p]


def todas(frente_ids: Iterable[int]) -> List[List[int]]:
    """Todas as combinações possíveis, das individuais à que junta tudo.

    É o que a tela de Configurações lista no seletor. Com as 4 frentes de hoje
    são 15 (4 + 6 + 4 + 1); a contagem é 2ⁿ − 1, então uma frente nova dobra a
    lista. Ordenadas por tamanho e depois por id, para o seletor abrir nas
    individuais — que são as que se edita no dia a dia.
    """
    ids = sorted(set(frente_ids))
    resultado: List[List[int]] = []
    for tamanho in range(1, len(ids) + 1):
        resultado.extend([list(c) for c in combinations(ids, tamanho)])
    return resultado

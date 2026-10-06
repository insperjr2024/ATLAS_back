"""O status geral de um projeto a partir das cores dos pilares (Health Track §4).

**Ordem de checagem: vermelho, depois verde, e amarelo é o resto.** Assim
toda combinação de cores cai em exatamente um status, para quaisquer
números que a diretoria configure (§5). Com limites livres por cor daria
para configurar um buraco — a própria regra da spec tinha um: "1 vermelho e
0 amarelos" não se encaixava em cor nenhuma até o exemplo do §5 dizer que
um vermelho já basta para o projeto ficar vermelho.

Com a regra inicial (semeada na migration, nunca escrita aqui) o resultado é
o da spec:

    verde     até 1 amarelo e nenhum vermelho
    amarelo   2 amarelos e nenhum vermelho
    vermelho  3 ou mais amarelos, ou qualquer vermelho

**Calculado na leitura, nunca gravado — mas com duas réguas.** Todo ciclo
mostra o status pela regra vigente NA ÉPOCA (o que as pessoas viram e
decidiram) e pela regra ATUAL (o que deixa a evolução comparável). Os dois só
divergem depois que a diretoria muda a regra (§5). As versões da regra
moram em `health_track_regra`; aqui só se recebe a lista delas.
"""

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class RegraStatusGeral:
    #: Verde: no máximo isto de cada cor.
    verde_max_amarelos: int
    verde_max_vermelhos: int
    #: Vermelho: basta atingir UM dos dois mínimos.
    vermelho_min_amarelos: int
    vermelho_min_vermelhos: int


def calcular_status_geral(cores: Iterable[str], regra: RegraStatusGeral) -> str:
    """`cores`: a cor de cada pilar avaliado (uma por pilar)."""
    contagem = Counter(cores)
    amarelos, vermelhos = contagem["amarelo"], contagem["vermelho"]

    if amarelos >= regra.vermelho_min_amarelos or vermelhos >= regra.vermelho_min_vermelhos:
        return "vermelho"
    if amarelos <= regra.verde_max_amarelos and vermelhos <= regra.verde_max_vermelhos:
        return "verde"
    return "amarelo"


def para_regra(versao) -> RegraStatusGeral:
    """Uma linha de `health_track_regra` (ou qualquer objeto com os quatro
    campos) como regra de cálculo."""
    return RegraStatusGeral(
        verde_max_amarelos=versao.verde_max_amarelos,
        verde_max_vermelhos=versao.verde_max_vermelhos,
        vermelho_min_amarelos=versao.vermelho_min_amarelos,
        vermelho_min_vermelhos=versao.vermelho_min_vermelhos,
    )


class ReguasStatus:
    """As versões da regra, prontas para responder "qual valia em X".

    `versoes`: objetos com `vigente_desde` e os quatro parâmetros, em
    qualquer ordem.
    """

    def __init__(self, versoes: Sequence):
        ordenadas = sorted(versoes, key=lambda v: v.vigente_desde)
        self._inicios = [v.vigente_desde for v in ordenadas]
        self._regras = [para_regra(v) for v in ordenadas]

    def vigente_em(self, momento: datetime) -> Optional[RegraStatusGeral]:
        """A versão mais recente que já valia em `momento`. Nenhuma, se o
        momento for anterior à primeira — não acontece com a inicial da
        migration, que nasce no passado."""
        posicao = bisect_right(self._inicios, momento)
        return self._regras[posicao - 1] if posicao else None

    def atual(self) -> Optional[RegraStatusGeral]:
        return self._regras[-1] if self._regras else None


def status_geral(cores: Iterable[str], avaliado_em: datetime, reguas: ReguasStatus) -> Optional[dict]:
    """O status de um conjunto de cores pelas duas réguas."""
    na_epoca, atual = reguas.vigente_em(avaliado_em), reguas.atual()
    if na_epoca is None or atual is None:
        return None
    cores = list(cores)
    return {
        "na_epoca": calcular_status_geral(cores, na_epoca),
        "pela_regra_atual": calcular_status_geral(cores, atual),
    }


def status_geral_ou_nada(
    cores: Iterable[Optional[str]], avaliado_em: Optional[datetime], reguas: ReguasStatus
) -> Optional[dict]:
    """`None` se algum pilar ainda não tem cor: com pilar faltando, o status
    seria calculado com menos cores do que a regra espera — um projeto com 3
    pilares verdes e 3 em branco não está verde."""
    cores = list(cores)
    if not cores or avaliado_em is None or any(c is None for c in cores):
        return None
    return status_geral(cores, avaliado_em, reguas)


def faixa_amarela(regra: RegraStatusGeral) -> dict:
    """O que o amarelo cobre, nos termos do §5 ("mínimo/máximo de amarelos,
    máximo de vermelhos") — para a tela mostrar, não para editar.

    Quando os limites de vermelho são contíguos (`verde_max_vermelhos + 1 ==
    vermelho_min_vermelhos`, o caso da regra inicial), só amarelos acima do
    verde levam ao amarelo. Se houver folga entre eles, ter vermelhos nessa
    folga já basta — com qualquer número de amarelos, inclusive zero.
    """
    contiguos = regra.verde_max_vermelhos + 1 == regra.vermelho_min_vermelhos
    return {
        "min_amarelos": regra.verde_max_amarelos + 1 if contiguos else 0,
        "max_amarelos": regra.vermelho_min_amarelos - 1,
        "max_vermelhos": regra.vermelho_min_vermelhos - 1,
    }

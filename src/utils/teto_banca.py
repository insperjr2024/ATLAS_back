"""Quantas pessoas CABEM numa banca (§8) — o teto.

⭐ **Desde 2026-09-02 o número pode ser da COMBINAÇÃO de frentes.** Antes era
`configuracao.vagas_por_banca` e ponto: um teto para a plataforma inteira, o
mesmo na banca de Direito sozinha (que exige 2 pessoas) e na de Business +
Tech + Processos (que exige 9).

⚠ **Não confundir com o PISO** (`utils/piso_banca.py`), que é quantas a banca
EXIGE. Comparar `alocados < vagas` para dizer "abaixo do mínimo" acusa quase
toda banca; recusar inscrição pelo piso lotaria a banca cedo demais. São dois
números e cada porta usa o seu:

- teto → `create_candidatura` ("banca lotada"), o `vagas` do card e o limite
  do push automático;
- piso → o mínimo do registro da banca e o "faltam N" da tela.

Existe como função solta, e não dentro de cada chamador, pelo mesmo motivo do
piso: os três caminhos que perguntam concordam por construção.
"""

from typing import List

from sqlalchemy.orm import Session

from src.models.frente_model import FrenteModel


def calcular_vagas_banca(frentes_vinculadas: List[FrenteModel], db: Session) -> int:
    """O teto desta banca: o da combinação, ou o global quando ela não tem um.

    Banca legada (sem frente vinculada) não cai em combinação nenhuma e fica
    com o global — que é o que sempre valeu para ela.
    """
    # Importado aqui, e não no topo: `use_cases` importa `utils`, e a volta no
    # nível do módulo fecharia o ciclo (mesmo caso de `piso_banca`).
    from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

    return ResolverComposicaoUseCase(db).vagas_da_combinacao([f.id for f in frentes_vinculadas])

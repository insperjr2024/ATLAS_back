"""O mínimo de pessoas que uma banca exige (§8).

⭐ **Desde 2026-09-01 o número vem da COMBINAÇÃO de frentes**, resolvida por
`use_cases/configuracao/composicao_banca.py`. Antes era a soma do
`frente.piso_banca` de cada frente vinculada — o mesmo valor em toda banca, sem
teto por frente e com a liderança contando dentro do piso.

Duas consequências de ligar a matriz aqui, e não em cada chamador:

1. Os três caminhos que perguntam o piso (registrar a banca, desenhar o card e
   a alocação automática) passam a concordar por construção. Espalhar a leitura
   da matriz seria criar três respostas para a mesma pergunta.
2. A combinação que ninguém configurou continua devolvendo o que devolvia: o
   resolver cai no padrão derivado de `frente.piso_banca`. A única mudança de
   número numa base sem configuração nenhuma é a liderança, que virou vaga a
   mais.
"""

from typing import List

from sqlalchemy.orm import Session

from src.models.banca_model import BancaModel
from src.models.frente_model import FrenteModel


def calcular_piso_banca(
    banca: BancaModel, frentes_vinculadas: List[FrenteModel], db: Session
) -> int:
    """O mínimo desta banca.

    `piso_minimo_override` (só a diretoria define) vale sobre o cálculo — é a
    exceção manual, e ela continua ganhando de qualquer regra.
    """
    if banca.piso_minimo_override is not None:
        return banca.piso_minimo_override

    # Importado aqui, e não no topo: `use_cases` importa `utils`, e a volta no
    # nível do módulo fecharia o ciclo.
    from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

    regras = ResolverComposicaoUseCase(db).para([f.id for f in frentes_vinculadas])
    return sum(r.minimo_de_pessoas for r in regras)

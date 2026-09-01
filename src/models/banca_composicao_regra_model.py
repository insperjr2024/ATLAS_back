from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from src.database.database import Base


class BancaComposicaoRegraModel(Base):
    """A composição exigida de uma banca, por COMBINAÇÃO de frentes (§8).

    ⭐ **Uma linha por (combinação, frente).** Antes os números viviam em dois
    lugares e não sabiam nada de combinação: `frente.piso_banca` (um mínimo por
    frente, o mesmo em qualquer banca) e `configuracao.lideranca_minima_por_frente`
    (um número global). Uma banca de Business sozinha e uma de Business + Tech +
    Processos exigiam os mesmos 3 de Business — e o que a diretoria queria era
    afrouxar Business quando a banca já está cheia de outras frentes.

    ⚠ **`combinacao` é a lista ORDENADA de ids de frente, unida por `-`**:
    `"1"` é Business sozinho, `"1-2"` é Business + Direito, `"1-2-3-4"` são as
    quatro. Ordenar é o que faz a chave ser única: sem isso, `"2-1"` e `"1-2"`
    seriam duas regras para a mesma banca. Ver `utils/combinacao_frentes.py`,
    que é quem monta e lê essa chave — nada aqui deve concatenar id à mão.

    📐 **Guardar a combinação como texto, e não uma tabela de ligação.** A
    alternativa seria `regra` + `regra_frente`, com uma linha por frente da
    combinação — três tabelas para responder "qual regra vale para este
    conjunto de frentes?", que é uma pergunta de igualdade de conjunto e que o
    SQL resolve mal. Com a chave normalizada, é um `WHERE combinacao = ?`.

    ⚠ **A tabela guarda só o que foi configurado à mão.** Combinação sem linha
    nenhuma não é erro: vale o padrão derivado de `frente.piso_banca` (ver
    `use_cases/configuracao/composicao_banca.py`). É o que faz uma frente nova,
    cadastrada depois, já ter regra em todas as combinações sem migration.
    """

    __tablename__ = "banca_composicao_regra"
    __table_args__ = (
        UniqueConstraint(
            "combinacao", "frente_id", name="uq_banca_composicao_combinacao_frente"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    #: A combinação de frentes desta regra, normalizada: ids ordenados e
    #: unidos por `-`. Indexada porque toda leitura filtra por ela.
    combinacao = Column(String(120), nullable=False, index=True)
    #: A frente DENTRO da combinação a que estes quatro números se referem.
    frente_id = Column(Integer, ForeignKey("frente.id", ondelete="CASCADE"), nullable=False)

    #: Quantos membros desta frente a banca exige, no mínimo. Não conta a
    #: liderança: ela é vaga à parte (ver `min_lideranca`).
    min_membros = Column(Integer, nullable=False, default=1, server_default="1")
    #: Teto de membros desta frente. Segura a banca que encheu de uma frente
    #: só e não deixou vaga para as outras.
    max_membros = Column(Integer, nullable=False, default=99, server_default="99")
    #: Quantas lideranças desta frente a banca exige, no mínimo.
    #:
    #: ⚠ **Liderança é gerente da frente ou diretoria** — não coordenador. E
    #: ela é uma pessoa A MAIS do que `min_membros`, não uma das contadas
    #: (2026-09-01): antes o gerente de Business cabia dentro do piso 3, e
    #: agora a banca de Business pede 3 membros + 1 liderança = 4.
    min_lideranca = Column(Integer, nullable=False, default=1, server_default="1")
    #: Teto de lideranças desta frente — a banca é para avaliar, não para
    #: reunir a gestão inteira.
    max_lideranca = Column(Integer, nullable=False, default=99, server_default="99")

    #: ⭐ Quantas pessoas cabem NESTA banca (2026-09-02). Diferente das quatro
    #: colunas acima, é da COMBINAÇÃO e não da frente: fica repetido em todas
    #: as linhas dela, que são gravadas juntas (ver `definir` no repositório) e
    #: por isso não têm como divergir.
    #:
    #: ⚠ `NULL` = usa `configuracao.vagas_por_banca`, o teto global, que
    #: continua sendo o padrão de quem não configurou e da banca legada (sem
    #: frente vinculada, e portanto sem combinação).
    vagas = Column(Integer, nullable=True)

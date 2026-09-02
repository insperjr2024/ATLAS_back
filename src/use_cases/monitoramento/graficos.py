"""Gráficos montados pela diretoria a partir das tabelas do banco (§7).

⚠ SEGURANÇA — leia antes de acrescentar tabela aqui.

Nada que vem da requisição entra em SQL como texto. Tabela, coluna e operação
são procuradas neste catálogo; o que não estiver aqui é recusado antes de
qualquer consulta. Por isso a lista é escrita à mão e não gerada por reflexão
do banco: reflexão traria de tudo, inclusive o que nunca pode sair daqui.

Fora de propósito, e não é esquecimento:

- `usuario.senha_hash` e `usuario.senha_provisoria` — credencial
- `token_recuperacao` — token de troca de senha
- `notificacao.corpo`, `avaliacao.comentario_feedback`, `tarefa_comentario`,
  `banca.descricao_coordenador` — texto escrito sobre pessoas
- `desempenho_*` — avaliação de desempenho individual
- tabelas de ligação (`banca_escopo`, `projeto_frente`, `usuario_frente`) e
  `alembic_version` — não rendem gráfico nenhum
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from src.database.database import Base
from src.utils.exceptions import RegraDeNegocioError

Papel = Literal["dimensao", "data", "metrica", "relacao"]

#: Quando a dimensão é um FK, o id sozinho não diz nada no eixo do gráfico.
#: Estas são as tabelas de onde o nome é buscado para trocar o número.
NOMES_DE: Dict[str, tuple[str, str]] = {
    "frente_id": ("frente", "nome"),
    "escopo_id": ("escopo", "nome"),
    "semestre_id": ("semestre", "nome"),
    "coluna_id": ("tarefa_coluna", "nome"),
    "coordenador_id": ("usuario", "nome"),
    "usuario_id": ("usuario", "nome"),
    "avaliador_id": ("usuario", "nome"),
    "cargo_id": ("cargo", "nome"),
    "projeto_id": ("projeto", "nome"),
}

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


@dataclass
class Coluna:
    nome: str
    rotulo: str
    papel: Papel


@dataclass
class Relacao:
    """Dimensão que mora em OUTRA tabela, alcançada por junção.

    📐 É o que responde "quais frentes mais aparecem": frente não é coluna de
    `projeto`, está em `projeto_frente`. Sem isto, a pergunta mais óbvia da
    diretoria não tinha como ser feita.

    `caminho` é uma lista de passos (tabela_nova, coluna_nova, tabela_anterior,
    coluna_anterior), encadeados a partir da tabela base.
    """

    nome: str
    rotulo: str
    caminho: List[tuple]
    #: De onde sai o texto do eixo: (tabela, coluna).
    rotulo_de: tuple
    #: Filtros fixos, como (tabela, coluna, valor). Valor `None` vira IS NULL.
    filtros: List[tuple] = field(default_factory=list)
    #: ⭐ A frase que a tela mostra quando as fatias se sobrepõem.
    #:
    #: Escrita AQUI, uma por relação, e não montada no front: só neste ponto
    #: se sabe que "projeto em duas frentes" chama-se sinérgico e que a mesma
    #: situação em `usuario` é outra coisa. Uma frase genérica ("o mesmo
    #: registro conta em cada categoria") é verdadeira e não diz nada a quem
    #: está olhando barras de frente.
    nota: str = ""


@dataclass
class Fonte:
    tabela: str
    rotulo: str
    descricao: str
    colunas: List[Coluna] = field(default_factory=list)
    relacoes: List[Relacao] = field(default_factory=list)
    #: ⭐ Filtros que valem SEMPRE nesta tabela, como (coluna, valor); valor
    #: `None` vira IS NULL.
    #:
    #: ⚠ **Existem para o gráfico falar da mesma população que o resto do
    #: Monitoramento.** Sem eles, esta tela lia a tabela crua: "Projetos por
    #: frente" somava 63 projetos enquanto a Visão geral, ao lado, dizia 61 —
    #: os 2 arquivados. Dois números para a mesma pergunta na mesma aba, e
    #: nenhum dos dois errado sozinho, o que é o pior tipo de divergência.
    filtros_base: List[tuple] = field(default_factory=list)


def _d(nome: str, rotulo: str) -> Coluna:
    return Coluna(nome, rotulo, "dimensao")


def _data(nome: str, rotulo: str) -> Coluna:
    return Coluna(nome, rotulo, "data")


def _m(nome: str, rotulo: str) -> Coluna:
    return Coluna(nome, rotulo, "metrica")


def _r(nome, rotulo, caminho, rotulo_de, filtros=None, nota="") -> Relacao:
    return Relacao(nome, rotulo, caminho, rotulo_de, filtros or [], nota)


#: O catálogo, curado para a pergunta que a diretoria faz — não para o que o
#: banco tem. Combinação que não responde nada (projeto por dia da reunião,
#: membro por semestre de graduação, tarefa por projeto com 200 barras) fica
#: de fora: o valor desta tela está no que ela NÃO oferece.
FONTES: List[Fonte] = [
    Fonte(
        "projeto",
        "Projetos",
        "O portfólio: um por cliente vendido. Serve para ver onde a operação está parada e o que mais se vende.",
        [
            _d("status", "Status"),
            _data("criado_em", "Mês da venda"),
            _data("data_kickoff", "Mês do kickoff"),
            _data("data_entrega_cliente", "Mês da entrega ao cliente"),
            _m("dias_ambientacao", "Dias de ambientação"),
        ],
        [
            # ⚠ Um projeto de 2 frentes conta nas duas — é o certo para "qual
            # frente mais aparece", e por isso o total pode passar do número
            # de projetos.
            _r("frente", "Frente",
               [("projeto_frente", "projeto_id", "projeto", "id"),
                ("frente", "id", "projeto_frente", "frente_id")],
               ("frente", "nome"),
               nota="Projeto sinérgico entra na barra de cada frente dele, então a soma das "
                    "barras passa do total real de projetos."),
            # Escopo customizado ("Outro") tem `escopo_id` nulo e fica fora:
            # ele não pertence a nenhum tipo do catálogo.
            _r("tipo_escopo", "Tipo de escopo vendido",
               [("projeto_escopo", "projeto_id", "projeto", "id"),
                ("escopo", "id", "projeto_escopo", "escopo_id")],
               ("escopo", "nome"),
               nota="Projeto que vendeu mais de um tipo de escopo entra na barra de cada um, "
                    "então a soma das barras passa do total real de projetos."),
            _r("coordenador", "Coordenador",
               [("projeto_membro", "projeto_id", "projeto", "id"),
                ("usuario", "id", "projeto_membro", "usuario_id")],
               ("usuario", "nome"),
               [("projeto_membro", "papel", "coordenador"), ("projeto_membro", "saiu_em", None)],
               nota="Projeto com mais de um coordenador atual entra na barra de cada um, então "
                    "a soma das barras passa do total real de projetos."),
        ],
        # §12: projeto arquivado é histórico e não entra em KPI da gestão
        # atual. É a MESMA régua de `_projetos_visiveis` no monitoramento.
        [("arquivado_em", None)],
    ),
    Fonte(
        "projeto_escopo",
        "Escopos vendidos",
        "Cada entrega dentro de um projeto. É onde moram o prazo e os dias vendidos — a matéria-prima do atraso.",
        [
            _d("status", "Status"),
            _d("frente_id", "Frente"),
            _d("escopo_id", "Tipo de escopo"),
            _d("tipo_atraso_entrega", "Tipo de atraso"),
            _data("data_entrega_planejada", "Mês da entrega planejada"),
            _data("data_entrega_real", "Mês da entrega real"),
            _m("dias_uteis_vendidos", "Dias úteis vendidos"),
        ],
    ),
    Fonte(
        "banca",
        "Bancas",
        "As bancas de avaliação. Sem data de realização, a banca ainda não aconteceu.",
        [
            _d("resultado", "Resultado"),
            _d("coordenador_id", "Coordenador"),
            _d("escopo_id", "Tipo de escopo"),
            _data("data_hora", "Mês marcado"),
            _data("realizado_em", "Mês em que aconteceu"),
        ],
        [
            _r("frente", "Frente",
               [("banca_frente", "banca_id", "banca", "id"),
                ("frente", "id", "banca_frente", "frente_id")],
               ("frente", "nome"),
               nota="Banca de mais de uma frente entra na barra de cada uma, então a soma das "
                    "barras passa do total real de bancas."),
        ],
    ),
    Fonte(
        "candidatura",
        "Alocações em banca",
        "Quem foi escalado para cada banca, e se compareceu. É por aqui que se vê se o rodízio está justo.",
        [
            _d("usuario_id", "Membro"),
            _d("confirmado", "Compareceu"),
            _data("criado_em", "Mês da alocação"),
        ],
    ),
    Fonte(
        "avaliacao",
        "Avaliações de banca",
        "Os formulários preenchidos depois da banca. O texto do feedback não entra aqui.",
        [
            _d("status", "Status"),
            _d("tipo_avaliador", "Tipo de avaliador"),
            _d("avaliador_id", "Avaliador"),
            _data("submetida_em", "Mês do envio"),
        ],
    ),
    Fonte(
        "tarefa",
        "Tarefas",
        "O kanban dos projetos. Mostra onde o trabalho empilha e quem está carregando.",
        [
            _d("coluna_id", "Coluna do kanban"),
            _data("criado_em", "Mês de criação"),
        ],
        [
            _r("responsavel", "Responsável",
               [("tarefa_responsavel", "tarefa_id", "tarefa", "id"),
                ("usuario", "id", "tarefa_responsavel", "usuario_id")],
               ("usuario", "nome"),
               nota="Tarefa de mais de uma pessoa entra na barra de cada uma, então a soma "
                    "das barras passa do total real de tarefas."),
        ],
    ),
    Fonte(
        "usuario",
        "Membros",
        "As pessoas do núcleo. Só posição, frente e situação — nada de credencial.",
        [
            _d("posicao", "Posição"),
            _d("status", "Situação"),
        ],
        [
            _r("frente", "Frente",
               [("usuario_frente", "usuario_id", "usuario", "id"),
                ("frente", "id", "usuario_frente", "frente_id")],
               ("frente", "nome"),
               nota="Membro de mais de uma frente entra na barra de cada uma, então a soma das "
                    "barras passa do total real de membros."),
        ],
    ),
    Fonte(
        "solicitacao_troca",
        "Pedidos de troca",
        "Quem pediu para sair de uma banca. Volume alto é sinal de alocação em horário ruim.",
        [
            _d("status", "Status"),
            _data("criado_em", "Mês do pedido"),
        ],
    ),
]

FONTES_POR_TABELA = {f.tabela: f for f in FONTES}

OPERACOES = {"contagem", "soma", "media"}

#: Como agrupar uma coluna de data. Sem isso, cada dia vira uma barra.
#: Sem "por dia" de propósito: para a diretoria, um gráfico com 200 barras
#: diárias não responde nada que o mês não responda melhor.
GRANULARIDADES = {"mes": "%Y-%m", "ano": "%Y"}


def listar_fontes() -> List[dict]:
    return [
        {
            "tabela": f.tabela,
            "rotulo": f.rotulo,
            "descricao": f.descricao,
            "colunas": [
                {"nome": c.nome, "rotulo": c.rotulo, "papel": c.papel} for c in f.colunas
            ]
            + [
                # Relações entram na mesma lista para a tela não precisar saber
                # que existem dois jeitos de agrupar. O papel "relacao" só diz
                # que ali cabe contagem, não soma nem média.
                {"nome": r.nome, "rotulo": r.rotulo, "papel": "relacao"}
                for r in f.relacoes
            ],
        }
        for f in FONTES
    ]


class MontarGraficoUseCase:
    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        tabela: str,
        dimensao: str,
        operacao: str = "contagem",
        metrica: Optional[str] = None,
        granularidade: str = "mes",
        limite: int = 30,
    ) -> dict:
        fonte = FONTES_POR_TABELA.get(tabela)
        if not fonte:
            raise RegraDeNegocioError("Essa tabela não está disponível para gráfico.")

        if operacao not in OPERACOES:
            raise RegraDeNegocioError("Operação inválida.")

        relacao = next((r for r in fonte.relacoes if r.nome == dimensao), None)
        if relacao:
            if operacao != "contagem":
                raise RegraDeNegocioError(
                    f"Agrupando por {relacao.rotulo.lower()} só dá para contar registros."
                )
            return self._por_relacao(fonte, relacao)

        col_dim = next((c for c in fonte.colunas if c.nome == dimensao), None)
        if not col_dim or col_dim.papel == "metrica":
            raise RegraDeNegocioError("Essa coluna não pode ser usada para agrupar.")

        col_met = None
        if operacao != "contagem":
            col_met = next(
                (c for c in fonte.colunas if c.nome == metrica and c.papel == "metrica"), None
            )
            if not col_met:
                raise RegraDeNegocioError(
                    "Soma e média precisam de uma coluna numérica desta tabela."
                )

        # A partir daqui tudo vem do catálogo, nunca da requisição: os nomes já
        # foram trocados por objetos Column do SQLAlchemy.
        t = Base.metadata.tables[fonte.tabela]
        coluna = t.c[col_dim.nome]

        if col_dim.papel == "data":
            if granularidade not in GRANULARIDADES:
                raise RegraDeNegocioError("Granularidade inválida.")
            agrupador = func.date_format(coluna, GRANULARIDADES[granularidade])
        else:
            agrupador = coluna

        if operacao == "contagem":
            valor = func.count()
        elif operacao == "soma":
            valor = func.sum(t.c[col_met.nome])
        else:
            valor = func.avg(t.c[col_met.nome])

        consulta = select(agrupador.label("chave"), valor.label("valor")).select_from(t)
        consulta = self._aplicar_base(consulta, fonte)
        linhas = self.db.execute(consulta.group_by(agrupador).order_by(agrupador)).all()

        rotulos = self._rotulos(col_dim, [linha.chave for linha in linhas])
        dados = [
            {
                "rotulo": rotulos.get(linha.chave, "—" if linha.chave is None else str(linha.chave)),
                "valor": float(linha.valor) if linha.valor is not None else 0.0,
            }
            for linha in linhas
        ]

        # Corta as fatias menores em vez de desenhar 200 barras ilegíveis. Data
        # fica de fora: a linha do tempo tem que ficar inteira e em ordem.
        if col_dim.papel != "data":
            dados.sort(key=lambda d: d["valor"], reverse=True)
            dados = self._cortar(dados, limite)

        return {
            "titulo": self._titulo(fonte, col_dim, operacao, col_met),
            "dados": dados,
            # Aqui cada registro cai em UMA fatia só, então somar é o total de
            # verdade — diferente do caminho de relação, ver `_por_relacao`.
            "total": sum(d["valor"] for d in dados),
            "sobrepoe": False,
            "nota": "",
        }

    def _por_relacao(self, fonte: Fonte, relacao: Relacao) -> dict:
        """Agrupa por coluna de outra tabela, juntando o caminho declarado.

        ⭐ Conta DISTINCT da tabela base. Sem isso, um projeto com 3 escopos da
        mesma frente apareceria como 3 projetos naquela frente — o gráfico
        contaria linhas de junção, não projetos.

        ⚠ **As fatias SE SOBREPÕEM, e a soma delas não é o total.** Um projeto
        de duas frentes conta 1 em cada — o que é o certo para "qual frente
        mais aparece" —, então somar as fatias conta esse projeto duas vezes.
        Por isso `total` vem de uma consulta própria na tabela base, e não de
        `sum(fatias)`: com 63 projetos e 5 sinérgicos, a soma dava 68 e o
        rodapé anunciava 68 projetos que não existem.

        `sobrepoe` sobe junto para a tela poder dizer isso e para recusar o
        gráfico de rosca — fatia de rosca é fração de um todo, e aqui as
        categorias não particionam nada.
        """
        base = Base.metadata.tables[fonte.tabela]
        origem = base
        for tabela_nova, col_nova, tabela_ant, col_ant in relacao.caminho:
            t_nova = Base.metadata.tables[tabela_nova]
            t_ant = Base.metadata.tables[tabela_ant]
            condicao = t_nova.c[col_nova] == t_ant.c[col_ant]
            # ⚠ Os filtros da relação entram no ON, nunca no WHERE. Num LEFT
            # JOIN, filtro no WHERE descarta a linha com NULL e o outer volta a
            # ser inner — o projeto sem coordenador sumiria do gráfico em vez
            # de aparecer em "—".
            for tabela_f, coluna_f, valor_f in relacao.filtros:
                if tabela_f != tabela_nova:
                    continue
                coluna_f_obj = Base.metadata.tables[tabela_f].c[coluna_f]
                condicao = and_(
                    condicao,
                    coluna_f_obj.is_(None) if valor_f is None else coluna_f_obj == valor_f,
                )
            # ⚠ OUTER, não INNER. Com inner, projeto sem nenhuma frente sumia
            # do gráfico sem aviso: as fatias somavam menos que o portfólio e
            # nada na tela dizia que faltava alguém. O `"—"` abaixo existia
            # desde sempre e nunca podia disparar.
            origem = origem.outerjoin(t_nova, condicao)

        t_rot, c_rot = relacao.rotulo_de
        agrupador = Base.metadata.tables[t_rot].c[c_rot]

        consulta = self._aplicar_base(
            select(agrupador.label("chave"), func.count(func.distinct(base.c.id)).label("valor"))
            .select_from(origem),
            fonte,
        ).group_by(agrupador)

        linhas = self.db.execute(consulta).all()
        dados = [
            {"rotulo": linha.chave if linha.chave is not None else "—", "valor": float(linha.valor)}
            for linha in linhas
        ]
        dados.sort(key=lambda d: d["valor"], reverse=True)
        dados = self._cortar(dados)

        total = float(
            self.db.execute(
                self._aplicar_base(select(func.count()).select_from(base), fonte)
            ).scalar()
            or 0
        )
        return {
            "titulo": f"{fonte.rotulo} por {relacao.rotulo.lower()}",
            "dados": dados,
            "total": total,
            "sobrepoe": sum(d["valor"] for d in dados) > total,
            "nota": relacao.nota,
        }

    def _aplicar_base(self, consulta, fonte: Fonte):
        """Os filtros que valem sempre nesta tabela (ver `Fonte.filtros_base`).

        Um lugar só, e usado nos TRÊS pontos que contam: as fatias por coluna,
        as fatias por relação e o total. Aplicado em dois e esquecido no
        terceiro, o rodapé voltaria a discordar das barras.
        """
        base = Base.metadata.tables[fonte.tabela]
        for coluna_nome, valor in fonte.filtros_base:
            coluna = base.c[coluna_nome]
            consulta = consulta.where(coluna.is_(None) if valor is None else coluna == valor)
        return consulta

    def _cortar(self, dados: List[dict], limite: int = 30) -> List[dict]:
        """Junta a cauda em "Outros (N)" em vez de desenhar 200 barras.

        Era só do caminho de coluna; a relação não cortava nada, então
        "Projetos por coordenador" num núcleo grande desenhava uma barra por
        pessoa. A regra é a mesma nos dois lados.
        """
        if len(dados) <= limite:
            return dados
        resto = dados[limite:]
        return dados[:limite] + [
            {"rotulo": f"Outros ({len(resto)})", "valor": sum(d["valor"] for d in resto)}
        ]

    def _rotulos(self, col: Coluna, chaves: list) -> Dict:
        """Troca id por nome, booleano por Sim/Não, número do dia por nome."""
        if col.nome == "dia_semana":
            return {
                k: DIAS_SEMANA[k] for k in chaves if isinstance(k, int) and 0 <= k < len(DIAS_SEMANA)
            }

        if col.nome in NOMES_DE:
            tabela_nome, coluna_nome = NOMES_DE[col.nome]
            alvo = Base.metadata.tables.get(tabela_nome)
            if alvo is None:
                return {}
            ids = [k for k in chaves if k is not None]
            if not ids:
                return {}
            linhas = self.db.execute(
                select(alvo.c.id, alvo.c[coluna_nome]).where(alvo.c.id.in_(ids))
            ).all()
            return {linha[0]: linha[1] for linha in linhas}

        # TINYINT(1) do MySQL volta como 0/1 e viraria "0" no eixo.
        if set(c for c in chaves if c is not None) <= {0, 1}:
            return {0: "Não", 1: "Sim"}

        return {}

    def _titulo(self, fonte: Fonte, dim: Coluna, operacao: str, met: Optional[Coluna]) -> str:
        if operacao == "contagem":
            return f"{fonte.rotulo} por {dim.rotulo.lower()}"
        verbo = "Soma de" if operacao == "soma" else "Média de"
        return f"{verbo} {met.rotulo.lower()} por {dim.rotulo.lower()}"

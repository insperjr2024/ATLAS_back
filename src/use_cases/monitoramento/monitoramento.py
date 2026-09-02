"""O monitoramento da diretoria e gerência (§7).

Nenhuma tabela nova: são consultas sobre o que F1–F8 construíram.

🔐 **Zero lógica de autorização própria.** Todo use case abre com
`aplicar_recorte_visao`, que já é exatamente o §7.5: "o gerente fica travado
na própria frente; a diretoria alterna entre frentes". O `?frente_id=` do
gerente no máximo restringe dentro das frentes dele — nunca amplia.

📅 **"Gestão atual" não é FK em lugar nenhum.** `projeto`, `banca` e
`projeto_escopo` não têm `semestre_id`. O idioma do repo é
`SemestreRepository.get_ativo()` + filtro de DATA nas métricas que têm data.
Projetos em si não são filtrados por semestre — o §12 diz que os que
atravessam a virada continuam ativos.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.middlewares.authorization import (
    aplicar_recorte_visao,
    eh_diretoria_de_projetos,
    frentes_do_usuario,
)
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.situacao_carga_repository import (
    SituacaoCargaRepository,
    faixa_mais_alta,
    resolver as resolver_situacao,
)
from src.repositories.cronograma_repository import CronogramaEtapaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase
from src.utils.calendario_variante import apenas_globais, datas_por_escopo
from src.utils.atraso_monitoramento import calcular_atraso_projeto, justificativa_cobrindo
from src.utils.banca_status import ABERTA, calcular_status_banca
from src.utils.condicoes_alerta import (
    AMBIENTACAO_SEM_BANCA,
    KICKOFF_PENDENTE,
    PROJETO_SEM_REUNIAO,
    TAREFA_VENCIDA,
    detectar_condicoes,
)
from src.utils.contagem_dias import (
    calcular_contagem_projeto,
    derivar_janelas_pausa,
    marco_das_correcoes,
)
from src.utils.dias_uteis import contar_dias_uteis, dias_uteis_de_atraso
from src.utils.janela_escopo import calcular_janela, dias_de_atraso, dias_parados
from src.utils.tarefa_status import (
    calcular_urgencia,
    dias_para_prazo,
    eh_vencida,
    esta_ativa,
    janela_semana,
)

STATUS_EM_EXECUCAO = ("ambientacao", "em_andamento", "validacao_bancas")
STATUS_PERTO_DO_FIM = ("envio_tep", "periodo_ajustes")

#: Até quantos projetos cada papel carrega sem ficar sobrecarregado.
#:
#: É o número que a diretoria descreveu: 2 projetos para um consultor, 4 para um
#: coordenador. Quem passa disso não *devolve* capacidade — um consultor com 3
#: projetos conta 0 vaga, nunca −1, porque a sobrecarga dele não tira do núcleo
#: a chance de vender para outra pessoa.
#:
#: ⚠ **Fixo aqui, e NÃO lido da escala de `situacao_carga`** — decisão do João
#: em 2026-08-06. Consequência a conhecer: a escala é editável em Configurações,
#: então ela pode passar a discordar destes números. Hoje já discorda no
#: coordenador (a escala marca "Carga alta" a partir de 3, não de 5), e nesse
#: caso a pílula de situação da tabela e o card de capacidade falam da mesma
#: pessoa de formas diferentes.
TETO_POR_PAPEL = {"consultor": 2, "coordenador": 4}

#: As etapas de um projeto EM CURSO, na ordem do ciclo de vida.
#:
#: A ordem é o dado, não enfeite: status é uma sequência, e a pizza da Visão
#: geral desenha as fatias nesta ordem para se ler como funil. Ordenar por
#: quantidade — como a lista que ela substituiu fazia — embaralha as etapas e
#: some com a leitura de onde o portfólio empaca.
#:
#: `finalizado` e `pausado` ficam de fora porque a pizza conta os ativos, e é o
#: que faz a soma das fatias bater com o número do meio.
ETAPAS_EM_CURSO = (
    "vendido",
    "ambientacao",
    "em_andamento",
    "validacao_bancas",
    "envio_tep",
    "periodo_ajustes",
)


class _BaseMonitoramento:
    """Carrega o recorte e os dados comuns uma vez só."""

    def __init__(self, db: Session):
        self.db = db
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.tarefa_repository = TarefaRepository(db)
        self.reuniao_repository = ReuniaoSemanalRepository(db)
        self.etapa_repository = CronogramaEtapaRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.coluna_repository = TarefaColunaRepository(db)
        self.situacao_repository = SituacaoCargaRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.usuario_frente_repository = UsuarioFrenteRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)
        #: O histórico de status revela as janelas de ⏸ Pausado, que entram no
        #: cálculo de atraso da janela do escopo (§10).
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def _calendario_de_janela(self) -> List[date]:
        """⭐ O calendário INTEIRO — para tudo que calcula JANELA DE ESCOPO.

        ⚠ Não use `_dias_nao_letivos(desde, ate)` aqui. Aquele recorta até a
        referência (hoje), e a janela de um escopo termina no FUTURO: um escopo
        que começou em 19/08 com 14 dias úteis fecha em 08/09, atravessando o
        feriado de 07/09 que o recorte não carregou. Sem o feriado, a janela era
        calculada um dia mais curta e uma banca feita no último dia aparecia
        como **1 dia de atraso** — exatamente o sintoma que apareceu em TX1.

        Carregar tudo é o que `get_escopos_projeto` já faz para a mesma conta, e
        é o que mantém o número do Monitoramento igual ao da tela do projeto —
        que é a razão de existir desta seção. O calendário é o acadêmico do
        semestre: dezenas de linhas, não milhares.

        Devolve os REGISTROS, e não as datas: o calendário base é do ESCOPO
        (frente + curso), e resolver isso exige os campos da linha. Quem varre
        a carteira passa os escopos de cada projeto por
        `_calendario_por_escopo` dentro do laço.
        """
        return self.dia_nao_letivo_repository.get_all()

    def _calendario_por_escopo(self, registros, escopos) -> dict:
        """`{escopo.id: [date, ...]}` — a base de contagem de cada escopo.

        ⭐ O calendário é do ESCOPO (`projeto_escopo.calendario` dentro da
        frente dele), não do projeto: num projeto sinérgico o escopo de
        Business não para na semana de avaliação da Tech.

        Função pura sobre `registros`, que o chamador já carregou uma vez — é o
        que o docstring de `_dias_nao_letivos` existe para proteger: uma query
        por projeto aqui derrubaria o laço da carteira inteira.
        """
        return datas_por_escopo(registros, escopos)

    def _calendario_global(self) -> List[date]:
        """Só os dias não letivos que valem para TODAS as frentes.

        É a régua da AMBIENTAÇÃO — a mesma de `encerrar_ambientacao` e de
        `get_projeto._fim_ambientacao`. A ambientação é do projeto inteiro:
        contar aqui um dia não letivo de uma frente só faria um projeto
        sinérgico terminá-la em datas diferentes conforme a frente que se
        olhasse, e o alerta discordaria da virada de status.
        """
        return [
            d.data for d in self.dia_nao_letivo_repository.get_all() if d.frente_id is None
        ]

    def _dias_nao_letivos(self, desde: Optional[date], ate: date) -> List:
        """O calendário do Insper no intervalo, carregado UMA vez.

        `dias_uteis.py` pede o conjunto pronto de propósito — consultar dentro
        do laço de projetos faria uma query por projeto.

        Como `_calendario_de_janela`, devolve os REGISTROS: a escolha entre os
        calendários de curso de uma frente é por projeto, e só quem está dentro
        do laço sabe de qual projeto se trata.
        """
        if desde is None or desde > ate:
            desde = ate
        return self.dia_nao_letivo_repository.get_por_intervalo(desde, ate)

    def _projetos_visiveis(
        self,
        current_user,
        frente_id: Optional[int],
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ) -> List[ProjetoModel]:
        # Projeto arquivado é histórico (§12) — não deve inflar nenhum KPI,
        # tabela ou cronograma do monitoramento da gestão atual.
        query = aplicar_recorte_visao(
            self.db.query(ProjetoModel), current_user, self.db, frente_id
        ).filter(ProjetoModel.arquivado_em.is_(None))
        # `escopo_id` é do CATÁLOGO (mesmo id do `?frente_id=` do filtro
        # irmão) — projeto com esse escopo vendido, custom ("Outro") fica de
        # fora, porque não tem `escopo_id` nenhum pra bater.
        if escopo_id is not None:
            query = query.filter(
                ProjetoModel.id.in_(
                    self.db.query(ProjetoEscopoModel.projeto_id).filter(
                        ProjetoEscopoModel.escopo_id == escopo_id
                    )
                )
            )
        # ⭐ O filtro de ETAPA do ciclo de vida (§4). Chega como LISTA porque o
        # seletor é de marcar vários: "Ambientação + Em andamento" é uma
        # pergunta só ("o que está tocando agora?"), e responder isso com duas
        # consultas obrigaria a tela a somar KPI de dois payloads — o placar de
        # gestão e os percentuais não somam assim (são médias sobre bases
        # diferentes), então a união tem que acontecer aqui, no banco.
        #
        # Lista vazia é tratada como "sem filtro" pelo `if`: `in_([])` devolve
        # zero projeto, e a tela ficaria vazia sem ninguém ter escolhido nada.
        # Quem valida os valores é a rota (`filtro_status`), não este método.
        if status:
            query = query.filter(ProjetoModel.status.in_(status))
        return query.all()

    def _encerra_por_coluna(self) -> Dict[int, bool]:
        """`coluna_id → encerra_tarefa`. "Vencida" e "ativa" dependem disto,
        e não mais de uma lista fixa de status: as colunas do kanban são
        configuráveis pela diretoria."""
        # `listar_todas`, não `listar(projeto_id)`: o monitoramento agrega
        # vários projetos de uma vez e cada um tem o seu conjunto de colunas.
        return {c.id: c.encerra_tarefa for c in self.coluna_repository.listar_todas()}

    def _contexto(self, projetos):
        ids = [p.id for p in projetos]
        escopos = self.escopo_repository.get_by_projetos(ids)
        catalogo = {e.id: e.nome for e in self.catalogo_repository.get_all()}
        return {
            "ids": ids,
            "escopos_por_projeto": _agrupar(escopos, "projeto_id"),
            # Escopo → banca. Uma banca que cobre vários escopos aparece em
            # todas as chaves dela: o atraso é cobrado por escopo.
            "bancas_por_escopo": (bancas_por_escopo := self.banca_repository.mapa_por_escopo(
                [e.id for e in escopos]
            )),
            # ⭐ As tentativas de cada banca. O atraso e a contagem param na
            # PRIMEIRA realização (§11) — sem isto, um escopo com 2ª banca
            # marcada volta a "em contagem" e o retrabalho vira atraso.
            "sessoes_por_banca": self.sessao_repository.get_by_bancas(
                [b.id for b in bancas_por_escopo.values()]
            ),
            "nomes_escopo": {
                e.id: e.nome_customizado or catalogo.get(e.escopo_id, "escopo") for e in escopos
            },
        }

    def _atrasos(self, projetos, ctx, referencia: date):
        """O atraso do §7.4, em dias ÚTEIS.

        O calendário é carregado UMA vez, cobrindo desde o marco mais antigo em
        jogo (a banca ou a entrega planejada mais velha) até hoje — consultar
        dentro do laço faria uma query por projeto.
        """
        candidatos = [
            b.data_hora.date() for b in ctx["bancas_por_escopo"].values() if b.data_hora
        ]
        candidatos += [
            e.data_entrega_planejada
            for escopos in ctx["escopos_por_projeto"].values()
            for e in escopos
            if e.data_entrega_planejada
        ]
        nao_letivos = self._dias_nao_letivos(min(candidatos, default=None), referencia)

        # ⚠ As janelas de ⏸ Pausado, por projeto. Faltavam aqui: o pilar da
        # banca cobrava os dias em que a própria diretoria mandou parar,
        # enquanto `_escopos_atrasados` — na MESMA tela — já os descontava. As
        # duas metades discordavam sobre o mesmo projeto parado.
        historico = _agrupar(
            self.historico_repository.get_by_projetos([p.id for p in projetos]), "projeto_id"
        )
        return {
            p.id: calcular_atraso_projeto(
                p.id,
                ctx["escopos_por_projeto"].get(p.id, []),
                ctx["bancas_por_escopo"],
                ctx["nomes_escopo"],
                referencia,
                [d.data for d in apenas_globais(nao_letivos)],
                janelas_pausa=derivar_janelas_pausa(historico.get(p.id, [])),
                dias_nao_letivos_por_escopo=self._calendario_por_escopo(
                    nao_letivos, ctx["escopos_por_projeto"].get(p.id, [])
                ),
            )
            for p in projetos
        }


#: Quantos meses a tendência de entregas cobre.
MESES_DE_TENDENCIA = 6


def _tendencia_mensal(entregas, hoje: date) -> List[dict]:
    """As entregas por MÊS nos últimos `MESES_DE_TENDENCIA`, do mais antigo ao
    mais novo.

    Mês, e não semana: entrega de escopo é evento raro — num núcleo com 50
    projetos saem poucas por semana, e a série semanal virava uma fileira de
    zeros com um pico solto. No mês o ritmo aparece.

    ⚠ O mês corrente entra **incompleto**, e é assim que tem de ser: a última
    barra é "o que saiu até agora", não uma previsão. Quem olha no dia 3 vê
    pouco porque de fato ainda é dia 3.

    A aritmética é feita em (ano, mês) e não somando dias: 6 × 30 dias não é
    meio ano, e somar `timedelta` a uma data de 31 escorrega de mês.
    """
    meses = []
    ano, mes = hoje.year, hoje.month
    for _ in range(MESES_DE_TENDENCIA):
        meses.append((ano, mes))
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    meses.reverse()

    por_mes = Counter((e["data"].year, e["data"].month) for e in entregas)
    return [
        {"inicio": date(a, m, 1), "total": por_mes.get((a, m), 0)} for a, m in meses
    ]


def _agrupar(itens, campo: str) -> Dict[int, list]:
    mapa = defaultdict(list)
    for item in itens:
        mapa[getattr(item, campo)].append(item)
    return mapa


class VisaoGeralUseCase(_BaseMonitoramento):
    def execute(
        self,
        current_user,
        frente_id: Optional[int] = None,
        referencia: Optional[date] = None,
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id, status)
        ctx = self._contexto(projetos)
        atrasos = self._atrasos(projetos, ctx, hoje)
        semestre = self.semestre_repository.get_ativo()

        # Um projeto finalizado não está atrasado, e um pausado está parado
        # por decisão de gestão — nenhum dos dois pode derrubar o placar nem
        # inflar o KPI de atrasados. `em_curso` é a base de todas as métricas
        # de atraso desta tela, para elas nunca se contradizerem entre si.
        em_curso = [p for p in projetos if p.status not in ("finalizado", "pausado")]
        # 🎯 Placar da gestão: % dos projetos em curso SEM banca atrasada. A
        # entrega ao cliente fica de fora de propósito — depende da agenda
        # dele, e o §7.1 manda separar.
        no_prazo = [p for p in em_curso if not atrasos[p.id].atrasado_por_banca]
        placar = round(len(no_prazo) / len(em_curso) * 100, 1) if em_curso else 100.0

        # ⚠ Este percentual NÃO é o complemento do placar acima, e os dois
        # aparecem lado a lado na tela. O placar conta só banca atrasada; este
        # conta QUALQUER motivo, inclusive entrega. A diferença são os projetos
        # atrasados só por entrega, que o §7.1 manda deixar de fora do placar
        # porque dependem da agenda do cliente.
        #
        # Medido no banco de demonstração: placar 47,4% e atrasados 68,4% —
        # `100 - placar` daria 52,6%, que não é nenhum dos dois. Por isso os
        # rótulos na tela precisam dizer o que cada um mede.
        atrasados = [p for p in em_curso if atrasos[p.id].atrasado]
        percentual_atrasados = (
            round(len(atrasados) / len(em_curso) * 100, 1) if em_curso else 0.0
        )

        return {
            "kpis": {
                "total": len(projetos),
                "em_execucao": sum(1 for p in projetos if p.status in STATUS_EM_EXECUCAO),
                "perto_de_finalizar": sum(1 for p in projetos if p.status in STATUS_PERTO_DO_FIM),
                "atrasados": len(atrasados),
                "pausados": sum(1 for p in projetos if p.status == "pausado"),
                "finalizados": sum(1 for p in projetos if p.status == "finalizado"),
            },
            "por_etapa": self._por_etapa(em_curso),
            "placar_gestao": {
                "percentual": placar,
                "no_prazo": len(no_prazo),
                "total_ativos": len(em_curso),
            },
            # Irmão do placar de propósito: mesma base `em_curso`, calculados
            # no mesmo lugar. Separados, um dia divergiriam.
            "atrasados_gestao": {
                "percentual": percentual_atrasados,
                "atrasados": len(atrasados),
                "total_ativos": len(em_curso),
            },
            "entregas": self._entregas(projetos, ctx, semestre, hoje),
            "bancas_proximas": self._bancas_proximas(projetos, ctx, hoje),
            "tempo_parado": self._tempo_parado(projetos, ctx, hoje),
            # ⚠ `em_curso`, não `projetos`: a lista recebia a base crua e cobrava
            # reunião semanal de projeto ⏸ Pausado e finalizado — os mesmos que
            # esta tela exclui de TODAS as outras métricas. O payload respondia
            # duas coisas sobre o mesmo projeto.
            "atencao_agora": self._atencao_agora(em_curso, ctx, atrasos, hoje),
            # §15/§16: os números da janela, por projeto e por frente.
            "janela": self._metricas_de_janela(em_curso, ctx, hoje),
        }

    def _metricas_de_janela(self, projetos, ctx, hoje: date):
        """§15/§16: dias ajustados, dias de atraso e **dias parados**.

        ⚠ **`dias_parados` aqui não é o `dias_parado` de `_tempo_parado`.** São
        perguntas diferentes e os dois aparecem na mesma tela:

        - `tempo_parado.dias_parado` — dias CORRIDOS desde a última tarefa
          mexida. Responde "faz quanto tempo ninguém toca nisso?".
        - `janela...dias_parados` — dias ÚTEIS EM BRANCO no cronograma, do
          kickoff até hoje. Responde "quanto deste projeto ficou sem nada
          planejado?" (§16).

        Um projeto pode ter 0 dias parados aqui e 20 lá: cronograma cheio, mas
        ninguém mexendo nas tarefas.
        """
        escopos = [e for lista in ctx["escopos_por_projeto"].values() for e in lista]
        etapas_por_escopo = _agrupar(
            self.etapa_repository.get_by_escopos([e.id for e in escopos]), "projeto_escopo_id"
        )
        reunioes_por_projeto = _agrupar(
            self.reuniao_repository.get_by_projetos_e_janela(
                ctx["ids"], date(hoje.year - 1, 1, 1), hoje
            ),
            "projeto_id",
        )
        # ⚠ Era `_dias_nao_letivos(kickoff mais antigo, hoje)`, e tinha o mesmo
        # defeito do `_escopos_atrasados`: este bloco chama `calcular_janela` e
        # `dias_de_atraso`, e a janela do escopo termina no FUTURO — o recorte
        # até hoje escondia os feriados que ela atravessa e encurtava a janela
        # em um dia por feriado. `dias_parados` abaixo só olha o passado e não
        # se importa, mas divide o mesmo calendário.
        nao_letivos = self._calendario_de_janela()
        # O recorte GLOBAL, a mesma regua da ambientacao e do `_dias_uteis_sem_tarefa`:
        # `dias_parados` e uma pergunta sobre o PROJETO inteiro, e um projeto sinergico
        # tem escopos em calendarios diferentes. O calendario de cada escopo entra so
        # em `por_escopo`, abaixo, onde a contagem e por escopo.
        globais = [d.data for d in apenas_globais(nao_letivos)]

        # ⚠ **Aqui havia uma TERCEIRA implementação da contagem**, montada à
        # mão com `calcular_janela` + `dias_de_atraso`, e ela divergia da
        # função canônica em três pontos ao mesmo tempo: não passava
        # `janelas_pausa` (dia de projeto parado contava como atraso), não
        # passava as sessões (banca reprovada e remarcada voltava a contar,
        # crescendo um dia por dia) e não pulava escopo cancelado.
        #
        # O efeito era visível: "21 · Reprovada, 2ª banca marcada — 13 em
        # atraso" nesta tela, e o MESMO projeto ausente da aba Atrasos, que já
        # usava a função certa. Agora as duas telas chamam
        # `calcular_contagem_projeto`, como `_escopos_atrasados` já fazia.
        historico_por_projeto = _agrupar(
            self.historico_repository.get_by_projetos(ctx["ids"]), "projeto_id"
        )

        linhas = []
        for projeto in projetos:
            do_projeto = ctx["escopos_por_projeto"].get(projeto.id, [])
            ajustados = sum(e.dias_uteis_ajustados for e in do_projeto)
            # O calendário de cada escopo, resolvido dentro do laço: escopos do
            # mesmo projeto podem ser de frentes (e de cursos) diferentes, e as
            # datas de prova de um não são as do outro.
            por_escopo = self._calendario_por_escopo(nao_letivos, do_projeto)
            contagens = calcular_contagem_projeto(
                do_projeto,
                historico_por_projeto.get(projeto.id, []),
                globais,
                referencia=hoje,
                bancas_por_escopo=ctx["bancas_por_escopo"],
                sessoes_por_banca=ctx["sessoes_por_banca"],
                dias_nao_letivos_por_escopo=por_escopo,
            )
            valem = [
                (e, c)
                for e, c in ((e, contagens.get(e.id)) for e in do_projeto)
                if c and e.status != "cancelado"
            ]
            atraso = max((c.atraso for _, c in valem), default=0)

            # ⭐ **O DENOMINADOR.** Sem ele, "12 dias além do vendido" não tem
            # tamanho: 12 sobre uma janela de 60 é um projeto apertado, 12
            # sobre uma de 10 é um projeto que dobrou. A tela mostrava os dois
            # como o mesmo "12" e não dava para priorizar entre eles.
            #
            # Soma dos escopos, não o pior: aqui a pergunta é quanto o projeto
            # INTEIRO vendeu. O `dias_de_atraso` ao lado continua sendo o pior
            # escopo, porque aquela pergunta é outra.
            vendidos = sum(c.dias_vendidos for _, c in valem)

            # ⭐ **QUAL escopo passou da janela**, não só quantos. "2 de 3" diz
            # que há problema mas não onde; com o nome, a linha da tabela vira
            # o endereço da conversa. O pior primeiro — é ele que dá o
            # `dias_de_atraso` da linha, então os dois falam do mesmo escopo.
            #
            # ⚠ "Além do vendido", nunca "atrasado": na aba Atrasos, atrasado é
            # banca vencida, e um escopo pode estar num estado sem estar no
            # outro. Misturar os dois já pôs "0 atrasados" e "19 em atraso" na
            # mesma tela.
            alem_do_vendido = sorted(
                ((e, c) for e, c in valem if c.estourou),
                key=lambda par: -par[1].atraso,
            )

            linhas.append(
                {
                    "projeto_id": projeto.id,
                    "projeto_nome": projeto.nome,
                    "dias_ajustados": ajustados,
                    "dias_vendidos": vendidos,
                    #: O nome do escopo que mais passou da janela. `None`
                    #: quando nenhum passou.
                    "escopo_alem_do_vendido": (
                        ctx["nomes_escopo"].get(alem_do_vendido[0][0].id, "escopo")
                        if alem_do_vendido
                        else None
                    ),
                    #: Quantos passaram, de quantos há. Um projeto de 4 escopos
                    #: com 1 além não é o mesmo que um com 4, e o nome do pior
                    #: sozinho não distingue.
                    "escopos_alem_do_vendido": len(alem_do_vendido),
                    "escopos": len(valem),
                    # O PIOR atraso entre os escopos, não a soma: escopos correm
                    # em paralelo, e somá-los inventaria um atraso que o projeto
                    # não teve.
                    "dias_de_atraso": atraso,
                    "dias_parados": dias_parados(
                        projeto.data_kickoff,
                        self._marcacoes(
                            projeto,
                            do_projeto,
                            etapas_por_escopo,
                            reunioes_por_projeto,
                            ctx["bancas_por_escopo"],
                        ),
                        globais,
                        referencia=hoje,
                    ),
                }
            )

        linhas.sort(key=lambda l: (-l["dias_de_atraso"], -l["dias_parados"]))
        return {
            "por_projeto": linhas,
            "totais": {
                "dias_ajustados": sum(l["dias_ajustados"] for l in linhas),
                "dias_de_atraso": sum(l["dias_de_atraso"] for l in linhas),
                "dias_parados": sum(l["dias_parados"] for l in linhas),
            },
        }

    def _marcacoes(
        self, projeto, escopos, etapas_por_escopo, reunioes_por_projeto, bancas_por_escopo
    ):
        """Todo dia que tem ALGUMA coisa marcada no cronograma (§16).

        Etapa, reunião, banca e entrega contam. O que sobra de dia útil entre
        o kickoff e hoje é o que o §16 chama de parado.

        ⚠ As bancas vêm do mapa já carregado pelo `_contexto`, não de uma
        consulta por escopo — este método roda dentro do laço de projetos.
        """
        dias = set()
        for escopo in escopos:
            for etapa in etapas_por_escopo.get(escopo.id, []):
                dia = etapa.data_inicio
                while dia <= etapa.data_fim:
                    dias.add(dia)
                    dia += timedelta(days=1)
            if escopo.data_entrega_real:
                dias.add(escopo.data_entrega_real)
            banca = bancas_por_escopo.get(escopo.id)
            if banca and banca.data_hora:
                dias.add(banca.data_hora.date())

        for reuniao in reunioes_por_projeto.get(projeto.id, []):
            dias.add(reuniao.data_reuniao)
        return dias

    def _por_etapa(self, em_curso):
        """A distribuição do portfólio pelas etapas do ciclo (§7.1).

        ⭐ **Recebe `em_curso`, e não todos os projetos.** A pizza mostra o total
        de ativos no meio, e é essa escolha que faz `sum(total)` bater com
        `placar_gestao.total_ativos` **por construção** — as duas saem da mesma
        lista, no mesmo lugar. Contar as fatias sobre `projetos` e o centro
        sobre `em_curso` daria um gráfico onde as partes não somam o todo, que é
        o jeito mais fácil de um gráfico mentir sem ninguém notar.

        Cada etapa traz os projetos dela porque a fatia é clicável: só a
        contagem não sustenta o "quais são esses 7?".

        Etapa vazia entra com `total: 0` em vez de sumir — some da legenda faria
        parecer que a etapa não existe, quando o que se quer saber é justamente
        que ela está vazia.
        """
        agrupados = defaultdict(list)
        for p in em_curso:
            agrupados[p.status].append({"id": p.id, "nome": p.nome})

        return [
            {
                "status": etapa,
                "total": len(agrupados[etapa]),
                "projetos": sorted(agrupados[etapa], key=lambda x: x["nome"]),
            }
            for etapa in ETAPAS_EM_CURSO
        ]

    def _entregas(self, projetos, ctx, semestre, hoje):
        """Contador + lista + tendência mensal (§7.1) — o contraponto positivo.

        ⚠ **O contador e a tendência medem populações DIFERENTES, de propósito.**
        `total_escopos` conta só a gestão atual, que é o assunto do card. A
        tendência abre 6 meses e **ignora o semestre**: a gestão 2026.2 começou
        em julho, então uma janela de meio ano recortada por ela viria com
        quatro meses zerados — um gráfico que não responde nada.

        Como as duas leituras convivem no mesmo card, somar as barras NÃO dá o
        número do título.

        A lista `recentes` e a contagem `projetos_finalizados` saíram em
        2026-08-06: o card virou só o gráfico e nenhuma das duas tinha mais
        quem as lesse.
        """
        # ⚠ `<= hoje`: entrega é fato consumado, e a coluna aceita data
        # futura (é assim que se registra uma entrega combinada). Sem o corte,
        # o card anunciava "8 escopos entregues na gestão" contando 3 que ainda
        # vão acontecer — e a última barra da tendência subia sozinha.
        todas = [
            {"data": e.data_entrega_real}
            for escopos in ctx["escopos_por_projeto"].values()
            for e in escopos
            if e.data_entrega_real and e.data_entrega_real <= hoje
        ]
        na_gestao = [
            r for r in todas if not semestre or semestre.inicio <= r["data"] <= semestre.fim
        ]

        return {
            "total_escopos": len(na_gestao),
            "tendencia": _tendencia_mensal(todas, hoje),
        }

    def _bancas_proximas(self, projetos, ctx, hoje):
        limite = hoje + timedelta(days=7)
        nomes_projeto = {p.id: p.nome for p in projetos}
        escopo_para_projeto = {
            e.id: pid for pid, escopos in ctx["escopos_por_projeto"].items() for e in escopos
        }
        # Agrupado por BANCA, não por escopo: a que cobre dois escopos é uma
        # linha só na agenda ("Alfa · Análise + Contratual"), senão a mesma
        # data apareceria duas vezes como se fossem dois compromissos.
        por_banca = {}
        for escopo_id, banca in ctx["bancas_por_escopo"].items():
            if not banca.data_hora:
                continue
            dia = banca.data_hora.date()
            if not (hoje <= dia <= limite):
                continue
            if calcular_status_banca(banca.data_hora, banca.realizado_em) != ABERTA:
                continue
            projeto_id = escopo_para_projeto.get(escopo_id)
            item = por_banca.setdefault(
                banca.id,
                {
                    # O id da banca vai para a tela: sem ele o card só consegue
                    # levar ao projeto, e o pedido é abrir A BANCA.
                    "banca_id": banca.id,
                    "projeto_id": projeto_id,
                    "projeto_nome": nomes_projeto.get(projeto_id, ""),
                    "escopos": [],
                    "data_hora": banca.data_hora,
                },
            )
            item["escopos"].append(ctx["nomes_escopo"].get(escopo_id, ""))

        proximas = [
            {
                "banca_id": item["banca_id"],
                "projeto_id": item["projeto_id"],
                "projeto_nome": item["projeto_nome"],
                "escopo": " + ".join(sorted(item["escopos"])),
                "data_hora": item["data_hora"],
            }
            for item in por_banca.values()
        ]
        proximas.sort(key=lambda b: b["data_hora"])
        return proximas

    def _tempo_parado(self, projetos, ctx, hoje):
        """😴 O VÃO ENTRE ESCOPOS: da entrega ao cliente de um até a reunião
        inicial do seguinte — o intervalo em que os projetos costumam morrer.

        ⭐ **É um vão por PAR de escopos, não um por projeto.** Um projeto de
        três escopos tem dois vãos, e eles podem ser muito diferentes.

        ⚠ Três defeitos que esta versão corrige:

        1. **Media sempre até HOJE.** Mesmo com o escopo seguinte já iniciado, a
           conta ia da última entrega ao relógio — então o vão que de fato
           aconteceu (entrega 10/07 → reunião inicial 15/07 = 5 dias) nunca
           aparecia, e o número só existia enquanto ninguém resolvia.
        2. **Dava número NEGATIVO.** `(hoje - entrega)` com entrega registrada
           para o futuro devolvia -16, e o card exibia "-16 dias parado". Uma
           entrega que ainda não aconteceu não abre vão nenhum.
        3. **Sumia quando havia qualquer escopo em curso**, o que escondia o
           vão de projetos que rodam escopos em sequência — justamente os que
           a métrica existe para vigiar.

        Vão ABERTO (o seguinte ainda não teve reunião inicial) continua correndo
        até hoje: é o alerta. Vão FECHADO fica com o tamanho que teve.

        Dias CORRIDOS, não úteis — é tempo de calendário parado, não esforço
        (ver a distinção no docstring de `_metricas_de_janela`).
        """
        vaos = []
        for p in projetos:
            if p.status in ("finalizado", "pausado"):
                continue
            escopos = [
                e for e in ctx["escopos_por_projeto"].get(p.id, []) if e.status != "cancelado"
            ]
            # A métrica é sobre a SEQUÊNCIA de escopos: com um só não há vão.
            if len(escopos) < 2:
                continue

            # Quem ainda nem começou é o que mantém um vão aberto.
            esperando = [e for e in escopos if not e.data_inicio]

            for entregue in escopos:
                entrega = entregue.data_entrega_real
                # Entrega no futuro ainda não aconteceu — era daqui que saía o
                # número negativo.
                if not entrega or entrega > hoje:
                    continue

                # O próximo a começar DEPOIS desta entrega. Ordenar por
                # `data_inicio` e não por `ordem`: a ordem é de exibição e vem
                # zerada na maioria dos projetos, então ela não diz a sequência
                # real em que os escopos rodaram.
                seguintes = [
                    e for e in escopos if e.data_inicio and e.data_inicio >= entrega
                ]
                proximo = min(seguintes, key=lambda e: e.data_inicio) if seguintes else None

                if proximo:
                    dias = (proximo.data_inicio - entrega).days
                    seguinte_nome = ctx["nomes_escopo"].get(proximo.id, "")
                elif esperando:
                    dias = (hoje - entrega).days
                    seguinte_nome = None
                else:
                    # Todos os escopos já rodaram: não há próximo a esperar.
                    continue

                # Zero dia não é vão: o próximo escopo começou no mesmo dia da
                # entrega, que é a passagem de bastão perfeita. Listá-la num
                # card de tempo PARADO seria reportar o caso bem-sucedido.
                if dias == 0:
                    continue

                vaos.append(
                    {
                        "projeto_id": p.id,
                        "projeto_nome": p.nome,
                        "escopo_entregue": ctx["nomes_escopo"].get(entregue.id, ""),
                        #: `None` = o vão está ABERTO, ninguém começou o próximo.
                        "escopo_seguinte": seguinte_nome,
                        "aberto": proximo is None,
                        "dias_parado": dias,
                    }
                )

        # Vão aberto primeiro — é o que ainda dá para resolver; depois o maior.
        vaos.sort(key=lambda x: (not x["aberto"], -x["dias_parado"]))
        return vaos

    def _atencao_agora(self, projetos, ctx, atrasos, hoje):
        """§7.1: o motivo precisa ser EXPLÍCITO, nunca um rótulo genérico.

        A DETECÇÃO (kickoff pendente, sem reunião, tarefa vencida) mora em
        `utils/condicoes_alerta.py`, compartilhada com a central de
        notificações do §6.6 — as duas telas respondem à mesma pergunta e
        divergiriam no primeiro caso de borda se cada uma tivesse a sua régua.

        O que fica aqui é a APRESENTAÇÃO desta aba, que é diferente da do
        sino: as tarefas vencidas vêm somadas num item por projeto (a diretoria
        quer o tamanho do problema, não a lista) e os motivos de atraso do
        §7.4 entram junto, vindos de `atraso_monitoramento`.
        """
        itens = []
        inicio_semana, fim_semana_ = janela_semana(hoje)
        reunioes = self.reuniao_repository.get_by_projetos_e_janela(
            ctx["ids"], inicio_semana, fim_semana_
        )
        _tarefas = self.tarefa_repository.get_by_projetos(ctx["ids"])
        condicoes = detectar_condicoes(
            projetos,
            escopos_por_projeto=ctx["escopos_por_projeto"],
            bancas_por_escopo=ctx["bancas_por_escopo"],
            # ⚠ Havia aqui um `sessoes_por_banca=ctx["sessoes_por_banca"]` que
            # `detectar_condicoes` nunca aceitou — a Visão geral inteira caía
            # com TypeError 500, e o outro chamador (o sino, em
            # `listar_notificacoes`) seguia funcionando por não passá-lo.
            #
            # As sessões não fazem falta aqui: as condições desta função olham
            # se a banca TEM data (`banca_nao_marcada`) e se ela é hoje —
            # perguntas que a tentativa corrente responde. Quem precisa da
            # PRIMEIRA realização é a contagem de dias, não o alerta.
            nomes_escopo=ctx["nomes_escopo"],
            tarefas_por_projeto=_agrupar(_tarefas, "projeto_id"),
            encerra_por_coluna=self._encerra_por_coluna(),
            projetos_com_reuniao={r.projeto_id for r in reunioes},
            responsaveis_por_tarefa=self.tarefa_repository.responsaveis_por_tarefa(
                t.id for t in _tarefas
            ),
            # O fim da ambientação cai no FUTURO para quem acabou de dar
            # kickoff, então é o calendário inteiro (global) — o recorte
            # `_dias_nao_letivos(…, hoje)` pararia antes do feriado que fecha a
            # janela, e o alerta nasceria um dia cedo.
            dias_nao_letivos=self._calendario_global(),
            hoje=hoje,
        )
        por_projeto = _agrupar(condicoes, "projeto_id")

        def item(projeto, tipo, motivo, dias=None):
            return {
                "projeto_id": projeto.id,
                "projeto_nome": projeto.nome,
                # ⭐ O TIPO vai junto do texto para a tela poder filtrar. O
                # `motivo` é frase escrita para humano ("3 tarefa(s)
                # vencida(s)") e muda de redação; agrupar por ela seria
                # agrupar por string livre, que quebra na primeira reescrita.
                "tipo": tipo,
                "motivo": motivo,
                "dias": dias,
            }

        for p in projetos:
            if p.status == "finalizado":
                continue
            do_projeto = por_projeto.get(p.id, [])
            tipos = {c.tipo for c in do_projeto}

            if KICKOFF_PENDENTE in tipos:
                itens.append(item(p, "kickoff", "kickoff não marcado"))

            # §5.3: o prazo de cravar a banca é o fim da ambientação. Entra
            # como `"banca"` — o tipo que a tela já agrupa — e não colide com o
            # atraso logo abaixo: aquele só existe quando a banca TEM data e ela
            # passou; este, só enquanto não tem data nenhuma.
            if AMBIENTACAO_SEM_BANCA in tipos:
                itens.append(item(p, "banca", "banca não marcada — a ambientação já terminou"))

            # `motivo.tipo` já é "banca" | "entrega_interna" | "entrega_externa"
            # — reaproveitado em vez de reclassificar pela descrição.
            for motivo in atrasos[p.id].motivos:
                itens.append(item(p, motivo.tipo, motivo.descricao, motivo.dias))

            if PROJETO_SEM_REUNIAO in tipos:
                itens.append(item(p, "reuniao", "sem reunião registrada esta semana"))

            vencidas = [c for c in do_projeto if c.tipo == TAREFA_VENCIDA]
            if vencidas:
                itens.append(
                    item(
                        p,
                        "tarefa",
                        f"{len(vencidas)} tarefa(s) vencida(s)",
                        max(c.dias for c in vencidas),
                    )
                )

        itens.sort(key=lambda i: (i["dias"] is None, -(i["dias"] or 0)))
        return itens


class ExecucaoUseCase(_BaseMonitoramento):
    """§7.2 — quem está distribuindo tarefa e fazendo reunião, sem abrir cada projeto.

    ⏱ **Aqui os dias são ÚTEIS**, pelo calendário do Insper — e desde
    2026-08-04 o §7.4 (banca e entrega, em `atraso_monitoramento.py`) usa a
    mesma régua, confirmada com a diretoria. Mede-se quanto tempo de TRABALHO
    passou: fim de semana, feriado e semana de provas não são tempo que o time
    deixou passar. Não há mais duas réguas no sistema.

    ⭐ "Ativa" e "vencida" vêm da COLUNA do kanban (`encerra_tarefa`), não de
    uma lista fixa de status — as colunas são configuráveis pela diretoria.

    📅 `referencia` permite olhar uma SEMANA PASSADA, mas nem tudo volta no
    tempo junto:

    - **voltam**: `distribuiu_na_semana`, reuniões, `vencidas`, `atraso_maximo`
      e `dias_uteis_sem_tarefa` — todos derivam de data e são recalculáveis;
    - **volta com perda**: `ultima_movimentacao` corta em `<= fim da semana`,
      mas subestima. `tarefa.movida_em` guarda só o carimbo da ÚLTIMA mudança;
      tarefa que se moveu naquela semana e se moveu de novo depois teve o
      registro antigo sobrescrito;
    - **não voltam**: `total` e `ativas`, que dependem da coluna em que a
      tarefa está AGORA. Sem histórico de movimentação entre colunas, não há
      como saber onde ela estava naquela semana. A tela marca esses com "hoje".
    """

    def execute(
        self,
        current_user,
        frente_id: Optional[int] = None,
        referencia: Optional[date] = None,
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id, status)
        ids = [p.id for p in projetos]
        inicio, fim = janela_semana(hoje)

        todas_tarefas = self.tarefa_repository.get_by_projetos(ids)
        tarefas_por_projeto = _agrupar(todas_tarefas, "projeto_id")
        encerra = self._encerra_por_coluna()
        reunioes = self.reuniao_repository.get_by_projetos_e_janela(ids, inicio, fim)
        reunioes_por_projeto = _agrupar(reunioes, "projeto_id")

        # O calendário precisa cobrir desde o prazo mais antigo em aberto (ou o
        # kickoff mais antigo) até hoje — é o intervalo máximo que qualquer
        # contagem desta aba vai varrer.
        candidatos = [t.prazo for t in todas_tarefas if t.prazo]
        candidatos += [p.data_kickoff for p in projetos if p.data_kickoff]
        nao_letivos = self._dias_nao_letivos(min(candidatos, default=None), hoje)

        tarefas = []
        for p in projetos:
            # ⚠ O recorte GLOBAL, e não o de um escopo. "3 dias úteis sem
            # tarefa" é pergunta sobre o PROJETO inteiro, e um projeto
            # sinérgico tem escopos em calendários diferentes — escolher o de
            # um deles faria o mesmo projeto ficar saudável ou parado conforme
            # o escopo que se olhasse. É a mesma régua da ambientação.
            do_calendario = [d.data for d in apenas_globais(nao_letivos)]
            todas_do_projeto = tarefas_por_projeto.get(p.id, [])
            # ⚠ Tudo que responde "como estava naquela semana" olha só as
            # tarefas que JÁ EXISTIAM até o fim dela. Sem esse corte, olhar 12
            # semanas atrás usava tarefas criadas semanas DEPOIS: o marco de
            # "sem tarefa nova" caía no futuro da referência, o cálculo batia
            # no `marco >= hoje` e devolvia 0 — a tela mostrava todos os
            # projetos saudáveis justamente nas semanas mais antigas, o oposto
            # da realidade. `sem_tarefas` sofria do mesmo: dava o mesmo número
            # em qualquer semana.
            #
            # `criado_em` é imutável, então este recorte é exato — diferente do
            # `movida_em`, que é sobrescrito e só permite aproximar.
            do_projeto = [
                t for t in todas_do_projeto if t.criado_em and t.criado_em.date() <= fim
            ]
            # ⚠ A janela é FECHADA nos dois lados. Só com `>= inicio` o campo
            # mentia assim que a tela ganhasse navegação: voltando 8 semanas,
            # qualquer projeto que recebeu tarefa depois daquela segunda —
            # inclusive meses depois — apareceria como "distribuiu". Não dava
            # para perceber antes da navegação existir, porque a semana sempre
            # terminava em hoje e não havia tarefa criada no futuro.
            criadas_na_semana = [
                t for t in do_projeto if t.criado_em and inicio <= t.criado_em.date() <= fim
            ]
            # Só o que já tinha acontecido até o fim da semana exibida. Sem o
            # corte, olhar 3 semanas atrás mostrava uma data POSTERIOR à janela
            # do cabeçalho — "semana de 06/07 a 12/07, última movimentação
            # 05/08" —, o que lia como tela quebrada.
            #
            # ⚠ O número fica SUBESTIMADO, e não há como evitar: `movida_em`
            # guarda só o carimbo da última mudança, não o histórico. Tarefa
            # que se moveu naquela semana e se moveu de novo depois teve o
            # registro antigo sobrescrito. Erra para menos, nunca para mais —
            # mostra menos atividade do que houve, jamais atividade que não
            # existiu.
            movimentacoes = [
                t.movida_em for t in do_projeto if t.movida_em and t.movida_em.date() <= fim
            ]
            # "Vencida" e "ativa" saem da COLUNA do kanban, não de um status na
            # tarefa: as colunas são configuráveis pela diretoria, e o campo
            # `status` deixou de existir no modelo.
            vencidas = [
                t for t in do_projeto if eh_vencida(t.prazo, encerra.get(t.coluna_id, False), hoje)
            ]
            ativas = [t for t in do_projeto if esta_ativa(encerra.get(t.coluna_id, False))]
            marco, tipo_marco = self._marco_sem_tarefa(p, do_projeto, fim)

            tarefas.append(
                {
                    "projeto_id": p.id,
                    "projeto_nome": p.nome,
                    "status": p.status,
                    "distribuiu_na_semana": len(criadas_na_semana) > 0,
                    "total": len(do_projeto),
                    "ativas": len(ativas),
                    "vencidas": len(vencidas),
                    # ⚠ `sem_tarefas` e `sem_tarefas_ativas` são situações
                    # DIFERENTES e a diretoria age diferente em cada uma: a
                    # primeira é um projeto que nunca foi destrinchado em
                    # tarefa; a segunda é um projeto que zerou o quadro e não
                    # recebeu o próximo lote. Um booleano só não distinguia.
                    "sem_tarefas": len(do_projeto) == 0,
                    "sem_tarefas_ativas": len(do_projeto) > 0 and len(ativas) == 0,
                    "dias_uteis_sem_tarefa": self._dias_uteis_sem_tarefa(
                        marco, hoje, do_calendario
                    ),
                    # De onde a contagem acima parte. Sem isto o front não tem
                    # como escrever o motivo sem adivinhar — ver
                    # `_marco_sem_tarefa`.
                    "marco_sem_tarefa": tipo_marco,
                    "data_marco_sem_tarefa": marco,
                    # O pior atraso do quadro, em dias úteis. Serve para
                    # ordenar: 1 tarefa parada há 10 dias úteis pesa mais que
                    # 5 que venceram ontem.
                    "atraso_maximo_dias_uteis": max(
                        (dias_uteis_de_atraso(t.prazo, hoje, do_calendario) for t in vencidas),
                        default=0,
                    ),
                    "ultima_movimentacao": max(movimentacoes) if movimentacoes else None,
                }
            )

        reunioes_resposta = [
            {
                "projeto_id": p.id,
                "projeto_nome": p.nome,
                "realizou": p.id in reunioes_por_projeto,
                "dias": sorted(r.data_reuniao for r in reunioes_por_projeto.get(p.id, [])),
                "dia_padrao": p.dia_reuniao_padrao,
            }
            for p in projetos
        ]

        # Quem decide se a semana é a atual é o servidor, não o navegador: o
        # front teria de recalcular a segunda-feira a partir do relógio local,
        # e uma máquina com fuso ou data errada mostraria a semana errada como
        # se fosse a de hoje.
        semana_de_hoje = janela_semana(date.today())[0]
        # Em semanas inteiras: a janela sempre começa numa segunda, então a
        # diferença é múltipla de 7 e a divisão é exata.
        semanas_atras = (semana_de_hoje - inicio).days // 7

        return {
            "semana": {
                "inicio": inicio,
                "fim": fim,
                "eh_atual": semanas_atras == 0,
                "eh_passada": semanas_atras > 0,
                #: 0 = semana atual, 1 = semana passada, 2 = duas atrás...
                "semanas_atras": semanas_atras,
            },
            "resumo_tarefas": {
                "projetos": len(tarefas),
                "sem_tarefas": sum(1 for t in tarefas if t["sem_tarefas"]),
                "sem_tarefas_ativas": sum(1 for t in tarefas if t["sem_tarefas_ativas"]),
                "sem_distribuir_na_semana": sum(
                    1 for t in tarefas if not t["distribuiu_na_semana"]
                ),
                "com_vencidas": sum(1 for t in tarefas if t["vencidas"] > 0),
            },
            "tarefas": tarefas,
            "reunioes": reunioes_resposta,
        }

    def _marco_sem_tarefa(
        self, projeto, tarefas, ate: date
    ) -> Tuple[Optional[date], Optional[str]]:
        """De ONDE parte a contagem de "sem tarefa nova", e o que esse ponto é.

        Devolve `(data, tipo)`, ambos lidos do banco:

        - com tarefas no projeto, o marco é a criação da mais recente
          (`tarefa.criado_em`) e o tipo é `"ultima_tarefa"`;
        - sem tarefa nenhuma, cai no `projeto.data_kickoff` e o tipo é
          `"kickoff"` — antes dele não há o que cobrar, porque o §5.2 diz que a
          execução só começa aí;
        - `(None, None)` quando o projeto ainda não tem kickoff.

        `ate` é o fim da semana que se está olhando. **Kickoff posterior a ela
        não conta**: naquela semana o projeto ainda nem tinha começado, e usá-lo
        devolveria um marco no futuro da janela — o cálculo cairia no
        `marco >= hoje` e diria "0 dias sem tarefa" para um projeto que sequer
        existia. Quem chama já entrega `tarefas` recortadas pelo mesmo limite.

        O TIPO vai para a resposta de propósito. O front precisa escrever
        "desde o kickoff" ou "desde a última tarefa criada", e não tem como
        saber qual dos dois olhando só o número de dias. Antes ele deduzia pelo
        `sem_tarefas`, o que funcionava por coincidência — no dia em que o
        filtro daquela lista mudasse, o texto passaria a mentir em silêncio,
        com um número plausível e o rótulo errado.
        """
        criacoes = [t.criado_em.date() for t in tarefas if t.criado_em]
        if criacoes:
            return max(criacoes), "ultima_tarefa"
        if projeto.data_kickoff and projeto.data_kickoff <= ate:
            return projeto.data_kickoff, "kickoff"
        return None, None

    def _dias_uteis_sem_tarefa(
        self, marco: Optional[date], hoje: date, nao_letivos
    ) -> Optional[int]:
        """Há quantos dias ÚTEIS o projeto não recebe uma tarefa nova.

        `None` quando não há marco (projeto sem kickoff): ele já aparece no
        "Atenção agora" com o motivo certo ("kickoff não marcado") e contar
        dias aqui seria cobrar duas vezes a mesma coisa.
        """
        if marco is None:
            return None
        if marco >= hoje:
            return 0
        return contar_dias_uteis(marco + timedelta(days=1), hoje, nao_letivos)


class AlocacaoUseCase(_BaseMonitoramento):
    """§7.3 — carga por pessoa. Coordenador costuma ser gargalo.

    ⚠ **Carga é medida em PROJETOS ATIVOS, não em horas.** A checagem por grade
    horária que o §7.3 menciona depende da F13, que não entrou nesta fatia.
    A resposta já teve um `grade_horaria_disponivel: False` para sinalizar isso,
    mas era constante e ninguém lia — o aviso saiu da tela em 2026-08-06 e o
    campo foi junto. A pendência é esta linha, não um campo morto no JSON.
    """

    def _capacidade(self, coordenadores, consultores):
        """Quantos projetos ainda cabem, por frente e por papel.

        A conta é `max(0, teto − projetos da pessoa)`, somada. ⭐ **O `max(0)` é
        o ponto:** um consultor com 3 projetos contribui 0, nunca −1. Ele está
        sobrecarregado, mas isso não tira do núcleo a chance de vender um projeto
        para outra pessoa — capacidade negativa de um não cancela a vaga livre do
        colega.

        **Dois números, um por papel, e não um só.** Converter em "projetos
        vendáveis" exigiria assumir o tamanho da equipe (medi 1 coordenador e ~2
        consultores por projeto), e essa suposição some no número final: quem
        lesse "8 projetos" não saberia que os consultores já estão no limite e
        que o 8 veio só dos coordenadores.

        As linhas são as MESMAS que alimentam as tabelas logo abaixo — passadas
        por parâmetro, não recalculadas. Recontar aqui abriria a porta para o
        card dizer um número e a tabela mostrar outro.
        """
        frentes = {f.id: f.nome for f in self.frente_repository.get_all()}
        por_usuario = defaultdict(list)
        for vinculo in self.usuario_frente_repository.get_all():
            por_usuario[vinculo.usuario_id].append(vinculo.frente_id)

        # `None` é a chave de quem não tem frente cadastrada. Ele entra como uma
        # linha "Sem frente" em vez de sumir: some faria a soma das frentes não
        # bater com o total, sem nada na tela explicando a diferença.
        vagas = defaultdict(lambda: {"consultor": 0, "coordenador": 0, "pessoas": set()})

        def acumular(linhas, papel):
            teto = TETO_POR_PAPEL[papel]
            for l in linhas:
                livre = max(0, teto - l["total"])
                for frente_id in por_usuario.get(l["usuario_id"]) or [None]:
                    vagas[frente_id][papel] += livre
                    vagas[frente_id]["pessoas"].add(l["usuario_id"])

        acumular(consultores, "consultor")
        acumular(coordenadores, "coordenador")

        linhas = [
            {
                "frente_id": fid,
                "frente_nome": frentes.get(fid, "Sem frente") if fid else "Sem frente",
                "consultor": v["consultor"],
                "coordenador": v["coordenador"],
                "pessoas": len(v["pessoas"]),
            }
            for fid, v in vagas.items()
        ]
        # Mais capacidade primeiro: a pergunta é "onde ainda dá para vender".
        #
        # "Sem frente" vai SEMPRE por último, mesmo tendo a maior capacidade:
        # ela junta quem ainda não foi vinculado a frente nenhuma, gente com a
        # agenda vazia e por isso com o teto inteiro livre. Deixá-la no topo
        # diria que a maior oportunidade do núcleo está fora de qualquer
        # frente, que é o oposto do que a tela quer responder. (Ela já foi
        # maior: até 2026-08-31 a diretoria caía aqui, com 8 vagas que não
        # existiam — hoje os três cargos ficam fora das tabelas.)
        linhas.sort(
            key=lambda x: (
                x["frente_id"] is None,
                -(x["consultor"] + x["coordenador"]),
                x["frente_nome"],
            )
        )

        # ⚠ O total NÃO é a soma das linhas. Quem está em duas frentes aparece
        # nas duas, e somar contaria a vaga dela duas vezes. Aqui a conta corre
        # sobre as pessoas, uma vez cada.
        return {
            "por_frente": linhas,
            "total": {
                "consultor": sum(
                    max(0, TETO_POR_PAPEL["consultor"] - l["total"]) for l in consultores
                ),
                "coordenador": sum(
                    max(0, TETO_POR_PAPEL["coordenador"] - l["total"]) for l in coordenadores
                ),
            },
            "teto": dict(TETO_POR_PAPEL),
        }

    def execute(
        self,
        current_user,
        frente_id: Optional[int] = None,
        referencia: Optional[date] = None,
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ):
        # ⭐ **O filtro (de frente ou de escopo) escolhe QUEM APARECE, não como
        # a carga é medida.** São duas listas de propósito:
        #
        #   `do_recorte` — os projetos do filtro pedido. Define a população: só
        #                  quem trabalha nele entra na tabela. (Exceção: para o
        #                  GERENTE a população sai do vínculo de frente, não dos
        #                  projetos — ver `entra`, mais abaixo.)
        #   `projetos`   — tudo que a pessoa logada enxerga, sem filtro. É
        #                  sobre isto que a carga de cada um é contada.
        #
        # Medir a carga dentro do recorte inflava a capacidade: Caio tem 3
        # projetos e está cheio, mas filtrando por Business só 1 deles aparecia
        # e ele "ganhava" 2 vagas que não existem. Medido em 2026-08-06: 21
        # pessoas nessa situação, e a capacidade total do núcleo SUBIA de 23
        # para 31 ao estreitar o filtro — um número que só pode cair.
        #
        # Capacidade e sobrecarga são propriedades da PESSOA. Quem carrega 3
        # projetos está cheio venha de onde vier o terceiro.
        # ⚠ `status` entra aqui pelo MESMO motivo que frente e escopo: ele
        # também estreita a população. Filtrar "Em andamento" e medir a carga
        # só nesses projetos daria a alguém que coordena um Em andamento e dois
        # Aguardando bancas duas vagas livres que não existem — o mesmo bug de
        # capacidade inflada que o filtro de frente causava.
        sem_filtro = frente_id is None and escopo_id is None and not status
        do_recorte = self._projetos_visiveis(current_user, frente_id, escopo_id, status)
        projetos = (
            do_recorte if sem_filtro else self._projetos_visiveis(current_user, None, None)
        )
        ids = [p.id for p in projetos]
        # O projeto vai inteiro (id, nome e etapa), não só o nome: o gráfico de
        # barras filtra a carga por etapa, e o front só consegue fazer isso sem
        # uma requisição por troca de filtro se o status vier junto. O id abre
        # o caminho para o chip da tabela linkar para o projeto.
        por_id = {p.id: {"id": p.id, "nome": p.nome, "status": p.status} for p in projetos}
        # Só projetos ATIVOS contam como carga — quem coordenou algo
        # finalizado não está ocupado por isso, e quem está num projeto
        # pausado (2026-08-19) também não: pausado é "parado", ninguém
        # trabalha nele enquanto durar, e contar a vaga como ocupada
        # impediria a pessoa de entrar em outro projeto de verdade.
        ativos = {p.id for p in projetos if p.status not in ("finalizado", "pausado")}

        membros = self.membro_repository.get_by_projetos(ids, apenas_atuais=True)
        usuarios = {u.id: u for u in self.usuario_repository.get_all() if u.status == "ativo"}

        carga: Dict[int, Dict[str, list]] = defaultdict(lambda: {"coordenador": [], "consultor": []})
        for m in membros:
            if m.projeto_id in ativos:
                carga[m.usuario_id][m.papel].append(por_id[m.projeto_id])

        # A situação de cada pessoa sai de uma ESCALA por papel, definida pela
        # diretoria em Configurações — não de um limiar no código.
        #
        # Um número único não dizia o que ela precisa dizer: "2 projetos é o
        # ideal para um consultor, 3 já é demais" são três estados, não um
        # corte. E o ponto de saturação muda por frente e por gestão.
        escalas = {
            papel: self.situacao_repository.garantir_padrao(papel)
            for papel in ("coordenador", "consultor")
        }
        # Quem está com demanda alta é quem cai na faixa mais alta do seu papel.
        # A pergunta é respondida pela POSIÇÃO na escala, não pelo nome nem pela
        # cor: nome e cor são livres, então decidir por eles deixaria o destaque
        # à mercê de alguém escrever "Carga alta" com essa grafia ou lembrar de
        # pintar de vermelho. Como cada papel tem sempre três faixas, esta
        # existe por construção e o card nunca fica vazio por configuração.
        topo = {papel: faixa_mais_alta(escala) for papel, escala in escalas.items()}

        def linha(usuario, papel):
            projetos_da_pessoa = sorted(
                carga.get(usuario.id, {}).get(papel, []), key=lambda p: p["nome"]
            )
            total = len(projetos_da_pessoa)
            situacao = resolver_situacao(escalas[papel], total)
            return {
                "usuario_id": usuario.id,
                "nome": usuario.nome,
                "posicao": usuario.posicao,
                "total": total,
                "projetos": projetos_da_pessoa,
                # A situação vem resolvida do backend: a regra é dele, e a tela
                # reimplementá-la seria convite para divergirem.
                "situacao": {"nome": situacao.nome, "tom": situacao.tom}
                if situacao
                else None,
                "demanda_alta": situacao is not None and situacao is topo[papel],
            }

        # ⚠ Quem aparece na tabela tem que ser quem a pessoa logada ENXERGA —
        # e, para o GERENTE, isso é a FRENTE dele, não os projetos dele.
        #
        # Listar quem está nos projetos visíveis errava a pergunta nos dois
        # sentidos: escondia o consultor da frente que ainda não entrou em
        # projeto nenhum — justamente quem tem a vaga livre que esta aba
        # existe para achar — e trazia o consultor de OUTRA frente que passou
        # por um projeto sinérgico dele, alguém que ele não aloca. A régua
        # passou a ser o vínculo de `usuario_frente`, a mesma que o §7.5 usa
        # para decidir quais projetos o gerente enxerga.
        #
        # A diretoria continua vendo o núcleo inteiro; coordenador e consultor
        # continuam vendo quem está nos projetos deles.
        ve_tudo = eh_diretoria_de_projetos(current_user) and sem_filtro
        na_visao = set(carga.keys())

        frentes_por_usuario: Dict[int, set] = defaultdict(set)
        for vinculo in self.usuario_frente_repository.get_all():
            frentes_por_usuario[vinculo.usuario_id].add(vinculo.frente_id)

        # As frentes que definem a população quando quem olha é gerente.
        #
        # O `?frente_id=` só RESTRINGE dentro das dele — mesma regra que
        # `aplicar_recorte_visao` aplica aos projetos (§7.5): pedir a frente de
        # outro gerente não amplia nada, cai de volta nas próprias.
        minhas_frentes: Optional[set] = None
        if getattr(current_user, "posicao", None) == "gerente":
            todas = set(frentes_do_usuario(current_user, self.db))
            minhas_frentes = {frente_id} if frente_id in todas else todas

        # Com filtro (de frente, escopo ou status), a POPULAÇÃO é quem trabalha
        # nele. A carga de cada um continua vindo de todos os projetos dela
        # (ver o topo deste método) — filtro escolhe quem aparece, não como
        # se mede.
        #
        # ⚠ O `in ativos` faz o filtro de status por `finalizado` ou `pausado`
        # devolver tabela VAZIA, e está certo: nenhum dos dois gera carga (ver
        # `ativos` acima). Quem só coordena projeto pausado tem as vagas
        # LIVRES — listá-lo aqui com carga 0 diria o contrário do card.
        ids_recorte = {p.id for p in do_recorte}
        no_recorte: Dict[str, set] = defaultdict(set)
        for m in membros:
            if m.projeto_id in ids_recorte and m.projeto_id in ativos:
                no_recorte[m.papel].add(m.usuario_id)

        def entra(usuario, papel) -> bool:
            if minhas_frentes is not None:
                if not (frentes_por_usuario.get(usuario.id, set()) & minhas_frentes):
                    return False
                # Escopo e status continuam estreitando a população: os dois
                # perguntam "quem trabalha NESTE recorte", e a resposta não
                # pode incluir quem não está em projeto nenhum. O filtro de
                # frente é a única exceção — ele já foi respondido acima, pelo
                # vínculo da pessoa, e não pelos projetos dela.
                if escopo_id is not None or status:
                    return usuario.id in no_recorte[papel]
                return True
            if not sem_filtro:
                return usuario.id in no_recorte[papel]
            if carga.get(usuario.id, {}).get(papel):
                return True
            if usuario.id in na_visao:
                return False  # já alocado, mas no outro papel
            return ve_tudo

        # ⚠ A DIRETORIA não entra em tabela nenhuma (decisão do João em
        # 2026-08-31): os três cargos não pegam projeto, então listá-los só
        # inflava a capacidade com vagas que ninguém vai ocupar — eram eles
        # que sustentavam quase toda a linha "Sem frente" do card.
        # O coordenador comercial (de vendas) fica de fora: tem a posição, mas
        # não conduz execução de projeto. Contá-lo aqui o mostrava como
        # "0 projetos, disponível" e dava ao núcleo uma vaga de coordenação que
        # ninguém vai ocupar. O gerente não tem essa marca.
        coordenadores = [
            linha(u, "coordenador")
            for u in usuarios.values()
            if entra(u, "coordenador")
            and u.posicao in ("coordenador", "gerente")
            and not getattr(u, "coordenador_vendas", False)
        ]
        consultores = [
            linha(u, "consultor")
            for u in usuarios.values()
            if entra(u, "consultor") and u.posicao == "consultor"
        ]
        # As duas tabelas respondem a MESMA pergunta: "quem pega o próximo
        # projeto?". Por isso ordenam igual — menos carregado primeiro, com os
        # disponíveis (0 projetos) no topo.
        #
        # Coordenadores ordenavam ao contrário, do mais carregado, para
        # responder "quem é o gargalo?" — o §7.3 destaca que coordenador
        # costuma ser gargalo. A diretoria pediu a inversão em 2026-08-05, e
        # essa leitura NÃO se perdeu: ela passou para o card de quem está em
        # situação de alerta, acima das tabelas, que é onde o sobrecarregado
        # aparece agora. Sem esse card, inverter aqui esconderia o gargalo.
        #
        # O nome é o desempate, senão pessoas com a mesma carga trocam de
        # lugar a cada refresh (a ordem vinha do dicionário de usuários).
        coordenadores.sort(key=lambda x: (x["total"], x["nome"]))
        consultores.sort(key=lambda x: (x["total"], x["nome"]))

        return {
            "coordenadores": coordenadores,
            "consultores": consultores,
            "capacidade": self._capacidade(coordenadores, consultores),
            # Quem caiu na faixa mais alta do seu papel, separado por papel.
            #
            # Este bloco é o que devolve a leitura de "quem é o gargalo" (§7.3),
            # perdida quando as duas tabelas passaram a ordenar do menos
            # carregado para o mais.
            "demanda_alta": {
                "coordenadores": [c for c in coordenadores if c["demanda_alta"]],
                "consultores": [c for c in consultores if c["demanda_alta"]],
            },
        }


class AtrasosUseCase(_BaseMonitoramento):
    """§7.4 — por projeto e por coordenador, com motivo explícito."""

    def execute(
        self,
        current_user,
        frente_id: Optional[int] = None,
        referencia: Optional[date] = None,
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ):
        hoje = referencia or date.today()
        # ⭐ **Só projeto EM CURSO.** `_projetos_visiveis` só tira arquivado, e a
        # aba iterava a lista crua — um projeto finalizado com banca antiga
        # nunca marcada como realizada aparecia na fila de cobrança da
        # diretoria, entrava no resumo e na conta do coordenador, e não
        # aparecia em nenhuma das outras três telas, que já recortavam assim.
        # Era o "aparecem projetos que não deveriam aparecer": o caso mais
        # visível era um projeto FINALIZADO, com escopo entregue e banca
        # aprovada, cobrado por 4 dias de atraso.
        #
        # ⚠ Este recorte vem DEPOIS do filtro de status e vence dele: pedir
        # `?status=finalizado` aqui devolve vazio de propósito. Esta aba é a
        # fila de cobrança, e não há o que cobrar de quem já terminou ou está
        # ⏸ Pausado por decisão de gestão.
        projetos = [
            p
            for p in self._projetos_visiveis(current_user, frente_id, escopo_id, status)
            if p.status not in ("finalizado", "pausado")
        ]
        ctx = self._contexto(projetos)
        atrasos = self._atrasos(projetos, ctx, hoje)
        justificativas_por_projeto = _agrupar(
            self.justificativa_repository.get_by_projetos([p.id for p in projetos]), "projeto_id"
        )

        por_projeto = []
        for p in projetos:
            atraso = atrasos[p.id]
            if not atraso.atrasado:
                continue
            justificativas = justificativas_por_projeto.get(p.id, [])
            por_projeto.append(
                {
                    "projeto_id": p.id,
                    "projeto_nome": p.nome,
                    "status": p.status,
                    "dias_totais": atraso.dias_totais,
                    # ⭐ O PIOR motivo isolado, que é o número que a tela mostra
                    # em destaque desde 2026-08-06.
                    #
                    # Soma e pior caso respondem coisas diferentes: três escopos
                    # com 4 dias cada somam 12 sem que nada esteja parado há 12
                    # dias. Para "qual é o pior buraco que temos", o pior caso é
                    # a resposta; a soma serve para medir volume acumulado, e
                    # continua no payload porque a tabela por coordenador usa.
                    "pior_motivo": max((m.dias for m in atraso.motivos), default=0),
                    "motivos": [self._motivo_dict(m, justificativas) for m in atraso.motivos],
                }
            )
        # ⚠ Ordena pelo PIOR MOTIVO, que é o número em destaque na tela. Ordenar
        # pela soma enquanto a tela mostra o pior caso deixaria a lista parecendo
        # embaralhada — o primeiro item teria um número menor que o segundo, sem
        # nada explicando por quê. A soma é o desempate.
        por_projeto.sort(key=lambda x: (-x["pior_motivo"], -x["dias_totais"]))

        # Por coordenador: o objetivo do §7.4 é identificar PADRÃO recorrente,
        # não julgar um caso isolado — por isso conta projetos e dias juntos.
        nomes_projeto = {p.id: p.nome for p in projetos}
        membros = self.membro_repository.get_by_projetos([p.id for p in projetos], apenas_atuais=True)
        usuarios = {u.id: u for u in self.usuario_repository.get_all()}
        por_coordenador: Dict[int, dict] = {}
        for m in membros:
            if m.papel != "coordenador":
                continue
            usuario = usuarios.get(m.usuario_id)
            entrada = por_coordenador.setdefault(
                m.usuario_id,
                {
                    "usuario_id": m.usuario_id,
                    "nome": usuario.nome if usuario else f"Usuário {m.usuario_id}",
                    "projetos": 0,
                    "atrasados": 0,
                    # ⭐ O pior caso substituiu o acumulado na tela: "40 dias
                    # somados" não diz se são quatro atrasos de 10 ou um de 40,
                    # e a ação é diferente em cada caso.
                    #
                    # Vem com o CONTEXTO junto — de qual projeto e por qual
                    # motivo. Um número solto obrigaria a procurar na tabela de
                    # cima qual dos projetos dele é o tal.
                    "pior_dias": 0,
                    "pior_projeto": "",
                    "pior_motivo": "",
                },
            )
            entrada["projetos"] += 1
            atraso = atrasos.get(m.projeto_id)
            if atraso and atraso.atrasado:
                entrada["atrasados"] += 1
                pior = max(atraso.motivos, key=lambda x: x.dias, default=None)
                if pior and pior.dias > entrada["pior_dias"]:
                    entrada["pior_dias"] = pior.dias
                    entrada["pior_projeto"] = nomes_projeto.get(m.projeto_id, "")
                    entrada["pior_motivo"] = pior.descricao

        # Ordena pelo pior caso — o número que a tabela mostra —, com o número
        # de atrasados como desempate. Ordenar pelo acumulado, que saiu da tela,
        # deixaria a lista sem critério visível.
        por_coordenador_lista = sorted(
            por_coordenador.values(), key=lambda x: (-x["pior_dias"], -x["atrasados"])
        )

        # 🎯 Os três números da faixa do topo, calculados AQUI e não na tela: a
        # divisão banca/entrega decide a leitura do §7.4 ("o pilar é a banca"),
        # e o front recontar isso a partir das descrições seria reimplementar a
        # classificação que o backend já faz.
        motivos = [m for p in por_projeto for m in p["motivos"]]
        return {
            "por_projeto": por_projeto,
            "por_coordenador": por_coordenador_lista,
            "escopos_atrasados": self._escopos_atrasados(projetos, ctx, hoje),
            # ⚠ `com_externo` e `pior_externo` saíram daqui em 2026-08-12,
            # junto com o motivo de entrega que os alimentava: sem
            # `entrega_externa` eles seriam dois zeros permanentes na faixa do
            # topo, dizendo "nenhum projeto travado no cliente" sobre uma
            # pergunta que a plataforma deixou de fazer.
            "resumo": {
                "projetos": len(por_projeto),
                "pior_caso": max((m["dias"] for m in motivos), default=0),
            },
        }

    def _escopos_atrasados(self, projetos, ctx, referencia: date) -> List[dict]:
        """⭐ §10: os escopos que passaram da JANELA, com o porquê escrito.

        ⚠ **Não são os `motivos` de `por_projeto`.** Aqueles perguntam "o que
        venceu e não aconteceu?" — banca não realizada, entrega que não saiu — e
        fecham quando o fato acontece. Este pergunta outra coisa: "o trabalho
        passou do tempo que foi vendido?". Um escopo pode estourar a janela com
        a banca já realizada e a entrega em dia, e aí nenhum dos três motivos
        dispara e o projeto nem aparece na lista de atrasos.

        É a mesma conta da coluna "Atraso" do card "Escopos vendidos", via
        `calcular_contagem_projeto` — a MESMA função que a tela do projeto usa,
        e não uma reimplementação: o número que a diretoria lê aqui tem de ser
        o mesmo que o coordenador vê lá, inclusive no desconto das pausas.
        """
        historico_por_projeto = _agrupar(
            self.historico_repository.get_by_projetos(ctx["ids"]), "projeto_id"
        )
        justificativas_por_escopo = self._notas_de_escopo(ctx["ids"])
        nomes_usuario = {u.id: u.nome for u in self.usuario_repository.get_all()}

        # Calendário inteiro: a janela termina no futuro (ver
        # `_calendario_de_janela`).
        nao_letivos = self._calendario_de_janela()

        linhas = []
        for projeto in projetos:
            do_projeto = ctx["escopos_por_projeto"].get(projeto.id, [])
            if not do_projeto:
                continue
            contagens = calcular_contagem_projeto(
                do_projeto,
                historico_por_projeto.get(projeto.id, []),
                [d.data for d in apenas_globais(nao_letivos)],
                referencia=referencia,
                dias_nao_letivos_por_escopo=self._calendario_por_escopo(
                    nao_letivos, do_projeto
                ),
                bancas_por_escopo=ctx["bancas_por_escopo"],
                # ⚠ **Faltava, e era o erro mais caro da tela.** Sem as
                # sessões, `primeira_realizacao` cai no fallback
                # `banca.realizado_em` — que `_campos_da_remarcacao` ZERA
                # quando uma banca reprovada é remarcada. Para o Monitoramento
                # a banca nunca tinha acontecido, a contagem seguia correndo
                # até hoje, e o retrabalho entre a 1ª e a 2ª banca (§11) virava
                # atraso. O docstring acima promete que este número é o MESMO
                # que o coordenador vê na tela do projeto; sem esta linha ele
                # não era: 1 dia lá, 44 aqui.
                sessoes_por_banca=ctx["sessoes_por_banca"],
            )
            for escopo in do_projeto:
                contagem = contagens.get(escopo.id)
                if escopo.status == "cancelado" or not contagem or contagem.atraso <= 0:
                    continue
                nota = justificativas_por_escopo.get(escopo.id)
                linhas.append(
                    {
                        "projeto_id": projeto.id,
                        "projeto_nome": projeto.nome,
                        "projeto_escopo_id": escopo.id,
                        "escopo_nome": ctx["nomes_escopo"].get(escopo.id, "escopo"),
                        "dias": contagem.atraso,
                        "dias_vendidos": escopo.dias_uteis_vendidos,
                        "dias_ajustados": escopo.dias_uteis_ajustados,
                        # `None` = ninguém explicou ainda, e é isso que a tela
                        # mostra como pendência em vez de inventar um motivo.
                        "justificativa": nota.texto if nota else None,
                        "justificativa_id": nota.id if nota else None,
                        "registrado_por": (
                            nomes_usuario.get(nota.registrado_por) if nota else None
                        ),
                        "registrado_em": nota.registrado_em if nota else None,
                    }
                )

        # Sem justificativa primeiro, e dentro de cada grupo o pior atraso no
        # topo: a lista é uma fila de trabalho da diretoria, e o que falta
        # explicação é o que ela precisa cobrar.
        linhas.sort(key=lambda x: (x["justificativa"] is not None, -x["dias"]))
        return linhas

    def _notas_de_escopo(self, projeto_ids) -> Dict[int, object]:
        """A nota MAIS RECENTE de atraso de janela, por escopo.

        As anteriores continuam no Histórico do projeto — aqui vale a última,
        que é a que descreve o atraso como ele está hoje.
        """
        mais_recente: Dict[int, object] = {}
        for j in self.justificativa_repository.get_by_projetos(projeto_ids):
            if j.tipo != "escopo" or j.projeto_escopo_id is None:
                continue
            atual = mais_recente.get(j.projeto_escopo_id)
            if atual is None or j.registrado_em > atual.registrado_em:
                mais_recente[j.projeto_escopo_id] = j
        return mais_recente

    def _motivo_dict(self, motivo, justificativas) -> dict:
        cobrindo = self._justificativa_cobrindo(motivo, justificativas)
        return {
            "tipo": motivo.tipo,
            "descricao": motivo.descricao,
            "dias": motivo.dias,
            "escopo": motivo.escopo_nome,
            "projeto_escopo_id": motivo.projeto_escopo_id,
            "data_referencia": motivo.data_referencia,
            "justificado": cobrindo is not None,
            # §7.4: o selo "justificado" do front tem que levar pra nota de
            # verdade no histórico — sem o id, ele só conseguia dizer
            # "alguém respondeu", não *onde* está a resposta.
            "justificativa_id": cobrindo.id if cobrindo else None,
        }

    def _justificativa_cobrindo(self, motivo, justificativas):
        """Delega para `justificativa_cobrindo` (utils/atraso_monitoramento).

        A régua saiu daqui quando a fila de Aprovações precisou da MESMA
        pergunta e respondeu com um atalho por projeto — duas telas com contas
        diferentes sobre o mesmo atraso.
        """
        return justificativa_cobrindo(motivo, justificativas)


class TarefasGeraisUseCase(_BaseMonitoramento):
    """Todas as tarefas de todos os projetos visíveis, num board só.

    🔒 Só a diretoria (o router usa `require_diretor_projetos`, não `require_gestao`):
    é uma visão de leitura mesmo, sem arrastar — clicar num card leva pro
    board de verdade do projeto, onde a ação existe de fato.

    🧩 Cada projeto tem seu próprio conjunto de colunas (§ colunas por
    projeto). "Um board só" não tem de onde tirar uma lista de colunas
    única, então as colunas do board macro são a UNIÃO dos nomes de coluna
    dos projetos visíveis (normalizados por espaço/maiúscula) — se todos
    usam o padrão de 5, o board fica idêntico ao de um projeto só; se algum
    projeto renomeou ou criou uma coluna própria, ela aparece como coluna
    extra, sem quebrar as outras.
    """

    def execute(
        self,
        current_user,
        frente_id: Optional[int] = None,
        referencia: Optional[date] = None,
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id, status)
        ids = [p.id for p in projetos]
        nomes_projeto = {p.id: p.nome for p in projetos}
        clientes_projeto = {p.id: p.cliente for p in projetos}

        tarefas = self.tarefa_repository.get_by_projetos(ids)
        responsaveis_por_tarefa = self.tarefa_repository.responsaveis_por_tarefa(
            t.id for t in tarefas
        )
        # Só as colunas DOS PROJETOS VISÍVEIS — `listar_todas` traz o núcleo
        # inteiro, e um gerente não pode ver colunas de projeto que ele nem
        # enxerga (mesmo vazias, sem tarefa nenhuma).
        colunas_visiveis = [c for c in self.coluna_repository.listar_todas() if c.projeto_id in ids]
        colunas_por_id = {c.id: c for c in colunas_visiveis}
        usuarios = {u.id: u for u in self.usuario_repository.get_all()}

        def nome_usuario(uid: int) -> str:
            u = usuarios.get(uid)
            return u.nome if u else f"Usuário {uid}"

        grupos: Dict[str, dict] = {}
        for c in sorted(colunas_visiveis, key=lambda c: (c.ordem, c.id)):
            chave = c.nome.strip().lower()
            if chave not in grupos:
                grupos[chave] = {"chave": chave, "nome": c.nome, "cor": c.cor, "ordem": c.ordem}
        colunas_ordenadas = sorted(grupos.values(), key=lambda g: g["ordem"])

        itens = []
        for t in tarefas:
            coluna = colunas_por_id.get(t.coluna_id)
            if not coluna:
                continue
            resp_ids = responsaveis_por_tarefa.get(t.id, [])
            itens.append(
                {
                    "id": t.id,
                    "titulo": t.titulo,
                    "projeto_id": t.projeto_id,
                    "projeto_nome": nomes_projeto.get(t.projeto_id, ""),
                    "cliente": clientes_projeto.get(t.projeto_id, ""),
                    "responsavel_ids": resp_ids,
                    "responsavel_nomes": [nome_usuario(uid) for uid in resp_ids],
                    "prazo": t.prazo,
                    "grupo_coluna": coluna.nome.strip().lower(),
                    "coluna_nome": coluna.nome,
                    "vencida": eh_vencida(t.prazo, coluna.encerra_tarefa, hoje),
                    "urgencia": calcular_urgencia(t.prazo, coluna.encerra_tarefa, hoje),
                    "dias_para_prazo": dias_para_prazo(t.prazo, hoje),
                }
            )

        return {"colunas": colunas_ordenadas, "tarefas": itens}


class CronogramasGeraisUseCase(_BaseMonitoramento):
    """Todos os cronogramas dos projetos visíveis, um mini-calendário por
    projeto (§7) — a mesma ideia do board macro de tarefas, mas para
    cronograma.

    🔒 Só a diretoria, mesma trava de `TarefasGeraisUseCase` acima.

    Reaproveita `GetCronogramaUseCase` projeto a projeto — zero lógica de
    dias úteis nova aqui, só agregação e ordenação. É mais caro que os
    outros use cases do módulo (N consultas completas de cronograma em vez
    de uma agregada), mas evita ter DOIS lugares calculando "quantos dias
    restam de um escopo" que podem divergir.
    """

    def execute(
        self,
        current_user,
        frente_id: Optional[int] = None,
        referencia: Optional[date] = None,
        escopo_id: Optional[int] = None,
        status: Optional[List[str]] = None,
    ):
        referencia = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id, status)

        itens = []
        for projeto in projetos:
            cronograma = GetCronogramaUseCase(self.db).execute(projeto.id, referencia)
            if not cronograma:
                continue
            itens.append(
                {
                    "projeto_id": projeto.id,
                    "projeto_nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "cronograma": cronograma,
                    "escopo_critico": self._escopo_critico(cronograma["escopos"]),
                }
            )

        # Quem tem escopo em contagem entra primeiro, do mais perto de
        # estourar (restantes menor, inclusive negativo) pro mais folgado;
        # projeto sem nenhum escopo em andamento vai para o fim da fila.
        itens.sort(
            key=lambda it: (
                it["escopo_critico"] is None,
                it["escopo_critico"]["restantes"] if it["escopo_critico"] else 0,
            )
        )
        return {"projetos": itens}

    def _escopo_critico(self, escopos: list) -> Optional[dict]:
        em_andamento = [e for e in escopos if e["em_contagem"]]
        if not em_andamento:
            return None
        escolhido = min(em_andamento, key=lambda e: e["restantes"])
        return {
            "id": escolhido["id"],
            "nome": escolhido["nome"],
            "restantes": escolhido["restantes"],
            "estourou": escolhido["estourou"],
            "data_entrega_planejada": escolhido["data_entrega_planejada"],
        }

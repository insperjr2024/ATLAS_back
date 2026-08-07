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

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
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
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase
from src.utils.atraso_monitoramento import calcular_atraso_projeto
from src.utils.banca_status import ABERTA, calcular_status_banca
from src.utils.condicoes_alerta import (
    KICKOFF_PENDENTE,
    PROJETO_SEM_REUNIAO,
    TAREFA_VENCIDA,
    detectar_condicoes,
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

    def _dias_nao_letivos(self, desde: Optional[date], ate: date) -> List[date]:
        """O calendário do Insper no intervalo, carregado UMA vez.

        `dias_uteis.py` pede o conjunto pronto de propósito — consultar dentro
        do laço de projetos faria uma query por projeto.
        """
        if desde is None or desde > ate:
            desde = ate
        return [d.data for d in self.dia_nao_letivo_repository.get_por_intervalo(desde, ate)]

    def _projetos_visiveis(
        self, current_user, frente_id: Optional[int], escopo_id: Optional[int] = None
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
            "bancas_por_escopo": self.banca_repository.mapa_por_escopo([e.id for e in escopos]),
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
        return {
            p.id: calcular_atraso_projeto(
                p.id,
                ctx["escopos_por_projeto"].get(p.id, []),
                ctx["bancas_por_escopo"],
                ctx["nomes_escopo"],
                referencia,
                nao_letivos,
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
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id)
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
            "atencao_agora": self._atencao_agora(projetos, ctx, atrasos, hoje),
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
        mais_antigo = min(
            (p.data_kickoff for p in projetos if p.data_kickoff), default=hoje
        )
        nao_letivos = self._dias_nao_letivos(mais_antigo, hoje)

        linhas = []
        for projeto in projetos:
            do_projeto = ctx["escopos_por_projeto"].get(projeto.id, [])
            ajustados = sum(e.dias_uteis_ajustados for e in do_projeto)
            atraso = 0
            for escopo in do_projeto:
                janela = calcular_janela(
                    escopo.data_inicio,
                    escopo.dias_uteis_vendidos,
                    escopo.dias_uteis_ajustados,
                    nao_letivos,
                    referencia=hoje,
                )
                banca = ctx["bancas_por_escopo"].get(escopo.id)
                atraso = max(
                    atraso,
                    dias_de_atraso(
                        janela,
                        getattr(banca, "realizado_em", None),
                        nao_letivos,
                        referencia=hoje,
                    ),
                )

            linhas.append(
                {
                    "projeto_id": projeto.id,
                    "projeto_nome": projeto.nome,
                    "dias_ajustados": ajustados,
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
                        nao_letivos,
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
        todas = [
            {"data": e.data_entrega_real}
            for escopos in ctx["escopos_por_projeto"].values()
            for e in escopos
            if e.data_entrega_real
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
        """😴 Escopo entregue e o próximo sem `data_inicio` — o vão em que os
        projetos costumam morrer (§7.1)."""
        parados = []
        for p in projetos:
            if p.status in ("finalizado", "pausado"):
                continue
            escopos = ctx["escopos_por_projeto"].get(p.id, [])
            entregues = [e for e in escopos if e.data_entrega_real]
            esperando = [e for e in escopos if not e.data_inicio and e.status != "cancelado"]
            # ⚠ Só está PARADO quem não tem nada rodando. Um projeto com 3
            # escopos sequenciais (um entregue, um em curso, um na fila)
            # aparecia como parado — mas ele está trabalhando.
            em_curso_agora = [
                e for e in escopos if e.data_inicio and not e.data_entrega_real
            ]
            if not entregues or not esperando or em_curso_agora:
                continue
            ultima = max(e.data_entrega_real for e in entregues)
            parados.append(
                {
                    "projeto_id": p.id,
                    "projeto_nome": p.nome,
                    "escopo_entregue": ctx["nomes_escopo"].get(
                        max(entregues, key=lambda e: e.data_entrega_real).id, ""
                    ),
                    "dias_parado": (hoje - ultima).days,
                }
            )
        parados.sort(key=lambda x: x["dias_parado"], reverse=True)
        return parados

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
        condicoes = detectar_condicoes(
            projetos,
            escopos_por_projeto=ctx["escopos_por_projeto"],
            bancas_por_escopo=ctx["bancas_por_escopo"],
            nomes_escopo=ctx["nomes_escopo"],
            tarefas_por_projeto=_agrupar(
                self.tarefa_repository.get_by_projetos(ctx["ids"]), "projeto_id"
            ),
            encerra_por_coluna=self._encerra_por_coluna(),
            projetos_com_reuniao={r.projeto_id for r in reunioes},
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
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id)
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
                        marco, hoje, nao_letivos
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
                        (dias_uteis_de_atraso(t.prazo, hoje, nao_letivos) for t in vencidas),
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
        # "Sem frente" vai SEMPRE por último, mesmo tendo a maior capacidade —
        # hoje ela junta os dois diretores, que não têm projeto e por isso somam
        # 8 vagas. Deixá-la no topo diria que a maior oportunidade do núcleo está
        # fora de qualquer frente, que é o oposto do que a tela quer responder.
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
    ):
        # ⭐ **O filtro (de frente ou de escopo) escolhe QUEM APARECE, não como
        # a carga é medida.** São duas listas de propósito:
        #
        #   `do_recorte` — os projetos do filtro pedido. Define a população: só
        #                  quem trabalha nele entra na tabela.
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
        sem_filtro = frente_id is None and escopo_id is None
        do_recorte = self._projetos_visiveis(current_user, frente_id, escopo_id)
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
        # finalizado não está ocupado por isso.
        ativos = {p.id for p in projetos if p.status not in ("finalizado",)}

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

        # ⚠ Quem aparece na tabela tem que ser quem a pessoa logada ENXERGA.
        # Listar todos os usuários ativos da empresa, mas contar carga só dos
        # projetos visíveis, faz um gerente ver "12 consultores disponíveis"
        # quando 10 deles estão lotados em frentes que ele não vê — pior que
        # não mostrar nada. Um gerente vê quem está nos projetos dele; a
        # diretoria, que enxerga tudo, vê o núcleo inteiro.
        ve_tudo = getattr(current_user, "posicao", None) == "diretor" and sem_filtro
        na_visao = set(carga.keys())

        # Com filtro (de frente ou de escopo), a POPULAÇÃO é quem trabalha
        # nele. A carga de cada um continua vindo de todos os projetos dela
        # (ver o topo deste método) — filtro escolhe quem aparece, não como
        # se mede.
        ids_recorte = {p.id for p in do_recorte}
        no_recorte: Dict[str, set] = defaultdict(set)
        for m in membros:
            if m.projeto_id in ids_recorte and m.projeto_id in ativos:
                no_recorte[m.papel].add(m.usuario_id)

        def entra(usuario, papel) -> bool:
            if not sem_filtro:
                return usuario.id in no_recorte[papel]
            if carga.get(usuario.id, {}).get(papel):
                return True
            if usuario.id in na_visao:
                return False  # já alocado, mas no outro papel
            return ve_tudo

        coordenadores = [
            linha(u, "coordenador")
            for u in usuarios.values()
            if entra(u, "coordenador") and u.posicao in ("coordenador", "gerente", "diretor")
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
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id)
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
            "resumo": {
                "projetos": len(por_projeto),
                "pior_caso": max((m["dias"] for m in motivos), default=0),
                # 🤝 Entrega travada do lado do CLIENTE.
                #
                # O §7.4 tira isso do que se cobra do time — a agenda não é
                # dele. Mas continua sendo o caso mais delicado do portfólio:
                # é o cliente esperando, e quem resolve é a diretoria falando
                # com ele, não o coordenador trabalhando mais.
                #
                "com_externo": sum(
                    1
                    for p in por_projeto
                    if any(m["tipo"] == "entrega_externa" for m in p["motivos"])
                ),
                "pior_externo": max(
                    (m["dias"] for m in motivos if m["tipo"] == "entrega_externa"), default=0
                ),
            },
        }

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
        """§7.4: o projeto continua vermelho mesmo depois de justificado —
        "o alerta é automático" não muda por causa da nota. O aviso é só pra
        dizer que a diretoria já perguntou e já registrou o porquê, então não
        cobra de novo o que já foi respondido.

        O aviso é POR MOTIVO (escopo + tipo), não por projeto: o mesmo escopo
        pode estar atrasado em banca E entrega ao mesmo tempo, e uma nota só
        cobre as duas se for uma nota geral (sem escopo/tipo escolhidos).
        Ordem de especificidade, da mais ampla pra mais estreita:
          1. nota geral do projeto (sem escopo) — cobre qualquer motivo;
          2. nota do escopo sem tipo — cobre os motivos DESTE escopo;
          3. nota do escopo com tipo — cobre só ESTE motivo.

        Uma nota só conta pro atraso ATUAL: se o atraso deste motivo começou
        depois da nota, ela era de uma rodada anterior (já resolvida) e não
        cobre a de agora.

        Devolve a nota mais RECENTE que cobre — se houver mais de uma, é a
        que reflete melhor "o que a diretoria disse por último" sobre isto.
        """
        def cobre(j) -> bool:
            if j.projeto_escopo_id is not None and j.projeto_escopo_id != motivo.projeto_escopo_id:
                return False
            if j.tipo is not None and j.tipo != motivo.tipo:
                return False
            if motivo.data_referencia is None:
                return True
            return j.registrado_em.date() >= motivo.data_referencia

        candidatas = [j for j in justificativas if cobre(j)]
        if not candidatas:
            return None
        return max(candidatas, key=lambda j: j.registrado_em)


class TarefasGeraisUseCase(_BaseMonitoramento):
    """Todas as tarefas de todos os projetos visíveis, num board só.

    🔒 Só a diretoria (o router usa `require_diretor`, não `require_gestao`):
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
    ):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id)
        ids = [p.id for p in projetos]
        nomes_projeto = {p.id: p.nome for p in projetos}
        clientes_projeto = {p.id: p.cliente for p in projetos}

        tarefas = self.tarefa_repository.get_by_projetos(ids)
        # Só as colunas DOS PROJETOS VISÍVEIS — `listar_todas` traz o núcleo
        # inteiro, e um gerente não pode ver colunas de projeto que ele nem
        # enxerga (mesmo vazias, sem tarefa nenhuma).
        colunas_visiveis = [c for c in self.coluna_repository.listar_todas() if c.projeto_id in ids]
        colunas_por_id = {c.id: c for c in colunas_visiveis}
        usuarios = {u.id: u for u in self.usuario_repository.get_all()}

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
            usuario = usuarios.get(t.responsavel_id)
            itens.append(
                {
                    "id": t.id,
                    "titulo": t.titulo,
                    "projeto_id": t.projeto_id,
                    "projeto_nome": nomes_projeto.get(t.projeto_id, ""),
                    "cliente": clientes_projeto.get(t.projeto_id, ""),
                    "responsavel_id": t.responsavel_id,
                    "responsavel_nome": usuario.nome if usuario else f"Usuário {t.responsavel_id}",
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
    ):
        referencia = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id, escopo_id)

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

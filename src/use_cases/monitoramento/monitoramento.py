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

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.atraso_monitoramento import calcular_atraso_projeto
from src.utils.banca_status import ABERTA, calcular_status_banca
from src.utils.dias_uteis import contar_dias_uteis, dias_uteis_de_atraso
from src.utils.tarefa_status import eh_vencida, esta_ativa, janela_semana
from src.utils.tarefa_status import (
    calcular_urgencia,
    dias_para_prazo,
    eh_vencida,
    esta_ativa,
    janela_semana,
)

STATUS_EM_EXECUCAO = ("ambientacao", "em_andamento", "validacao_bancas")
STATUS_PERTO_DO_FIM = ("envio_tep", "periodo_ajustes")


class _BaseMonitoramento:
    """Carrega o recorte e os dados comuns uma vez só."""

    def __init__(self, db: Session):
        self.db = db
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.tarefa_repository = TarefaRepository(db)
        self.reuniao_repository = ReuniaoSemanalRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.coluna_repository = TarefaColunaRepository(db)

    def _dias_nao_letivos(self, desde: Optional[date], ate: date) -> List[date]:
        """O calendário do Insper no intervalo, carregado UMA vez.

        `dias_uteis.py` pede o conjunto pronto de propósito — consultar dentro
        do laço de projetos faria uma query por projeto.
        """
        if desde is None or desde > ate:
            desde = ate
        return [d.data for d in self.dia_nao_letivo_repository.get_por_intervalo(desde, ate)]

    def _projetos_visiveis(self, current_user, frente_id: Optional[int]) -> List[ProjetoModel]:
        query = aplicar_recorte_visao(
            self.db.query(ProjetoModel), current_user, self.db, frente_id
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


def _agrupar(itens, campo: str) -> Dict[int, list]:
    mapa = defaultdict(list)
    for item in itens:
        mapa[getattr(item, campo)].append(item)
    return mapa


class VisaoGeralUseCase(_BaseMonitoramento):
    def execute(self, current_user, frente_id: Optional[int] = None, referencia: Optional[date] = None):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id)
        ctx = self._contexto(projetos)
        atrasos = self._atrasos(projetos, ctx, hoje)
        semestre = self.semestre_repository.get_ativo()

        por_status = defaultdict(int)
        for p in projetos:
            por_status[p.status] += 1

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
            "por_status": dict(por_status),
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
        }

    def _entregas(self, projetos, ctx, semestre, hoje):
        """Contador + lista + tendência semanal (§7.1) — o contraponto positivo."""
        nomes_projeto = {p.id: p.nome for p in projetos}
        realizadas = []
        for projeto_id, escopos in ctx["escopos_por_projeto"].items():
            for e in escopos:
                if not e.data_entrega_real:
                    continue
                if semestre and not (semestre.inicio <= e.data_entrega_real <= semestre.fim):
                    continue
                no_prazo = (
                    e.data_entrega_planejada is None
                    or e.data_entrega_real <= e.data_entrega_planejada
                )
                realizadas.append(
                    {
                        "projeto_id": projeto_id,
                        "projeto_nome": nomes_projeto.get(projeto_id, ""),
                        "escopo": ctx["nomes_escopo"].get(e.id, ""),
                        "data": e.data_entrega_real,
                        "no_prazo": no_prazo,
                    }
                )
        realizadas.sort(key=lambda r: r["data"], reverse=True)

        # Tendência por semana nas últimas 8 — bucketizar em Python é mais
        # simples e testável do que em SQL.
        tendencia = []
        for semanas_atras in range(7, -1, -1):
            inicio = hoje - timedelta(days=hoje.weekday() + 7 * semanas_atras)
            fim = inicio + timedelta(days=6)
            tendencia.append(
                {
                    "inicio": inicio,
                    "total": sum(1 for r in realizadas if inicio <= r["data"] <= fim),
                }
            )

        return {
            "total_escopos": len(realizadas),
            "projetos_finalizados": sum(1 for p in projetos if p.status == "finalizado"),
            "recentes": realizadas[:5],
            "tendencia": tendencia,
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
                    "projeto_id": projeto_id,
                    "projeto_nome": nomes_projeto.get(projeto_id, ""),
                    "escopos": [],
                    "data_hora": banca.data_hora,
                },
            )
            item["escopos"].append(ctx["nomes_escopo"].get(escopo_id, ""))

        proximas = [
            {
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
        """§7.1: o motivo precisa ser EXPLÍCITO, nunca um rótulo genérico."""
        itens = []
        inicio_semana, fim_semana_ = janela_semana(hoje)
        reunioes = self.reuniao_repository.get_by_projetos_e_janela(
            ctx["ids"], inicio_semana, fim_semana_
        )
        projetos_com_reuniao = {r.projeto_id for r in reunioes}
        tarefas_por_projeto = _agrupar(
            self.tarefa_repository.get_by_projetos(ctx["ids"]), "projeto_id"
        )
        encerra = self._encerra_por_coluna()

        for p in projetos:
            if p.status == "finalizado":
                continue

            if not p.data_kickoff:
                itens.append(
                    {
                        "projeto_id": p.id,
                        "projeto_nome": p.nome,
                        "motivo": "kickoff não marcado",
                        "dias": None,
                    }
                )

            for motivo in atrasos[p.id].motivos:
                itens.append(
                    {
                        "projeto_id": p.id,
                        "projeto_nome": p.nome,
                        "motivo": motivo.descricao,
                        "dias": motivo.dias,
                    }
                )

            if p.id not in projetos_com_reuniao and p.data_kickoff:
                itens.append(
                    {
                        "projeto_id": p.id,
                        "projeto_nome": p.nome,
                        "motivo": "sem reunião registrada esta semana",
                        "dias": None,
                    }
                )

            vencidas = [
                t
                for t in tarefas_por_projeto.get(p.id, [])
                if eh_vencida(t.prazo, encerra.get(t.coluna_id, False), hoje)
            ]
            if vencidas:
                itens.append(
                    {
                        "projeto_id": p.id,
                        "projeto_nome": p.nome,
                        "motivo": f"{len(vencidas)} tarefa(s) vencida(s)",
                        "dias": max((hoje - t.prazo).days for t in vencidas),
                    }
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

    def execute(self, current_user, frente_id: Optional[int] = None, referencia: Optional[date] = None):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id)
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
    """§7.3 — carga por pessoa. Coordenador costuma ser gargalo."""

    def execute(self, current_user, frente_id: Optional[int] = None, referencia: Optional[date] = None):
        projetos = self._projetos_visiveis(current_user, frente_id)
        ids = [p.id for p in projetos]
        nomes_projeto = {p.id: p.nome for p in projetos}
        # Só projetos ATIVOS contam como carga — quem coordenou algo
        # finalizado não está ocupado por isso.
        ativos = {p.id for p in projetos if p.status not in ("finalizado",)}

        membros = self.membro_repository.get_by_projetos(ids, apenas_atuais=True)
        usuarios = {u.id: u for u in self.usuario_repository.get_all() if u.status == "ativo"}

        carga: Dict[int, Dict[str, list]] = defaultdict(lambda: {"coordenador": [], "consultor": []})
        for m in membros:
            if m.projeto_id in ativos:
                carga[m.usuario_id][m.papel].append(nomes_projeto.get(m.projeto_id, ""))

        def linha(usuario, papel):
            projetos_da_pessoa = carga.get(usuario.id, {}).get(papel, [])
            return {
                "usuario_id": usuario.id,
                "nome": usuario.nome,
                "posicao": usuario.posicao,
                "total": len(projetos_da_pessoa),
                "projetos": projetos_da_pessoa,
                # 3+ projetos ativos é o limiar de "carga alta" — acima disso
                # a pessoa vira gargalo.
                "carga_alta": len(projetos_da_pessoa) >= 3,
                "disponivel": len(projetos_da_pessoa) == 0,
            }

        # ⚠ Quem aparece na tabela tem que ser quem a pessoa logada ENXERGA.
        # Listar todos os usuários ativos da empresa, mas contar carga só dos
        # projetos visíveis, faz um gerente ver "12 consultores disponíveis"
        # quando 10 deles estão lotados em frentes que ele não vê — pior que
        # não mostrar nada. Um gerente vê quem está nos projetos dele; a
        # diretoria, que enxerga tudo, vê o núcleo inteiro.
        ve_tudo = getattr(current_user, "posicao", None) == "diretor" and frente_id is None
        na_visao = set(carga.keys())

        def entra(usuario, papel) -> bool:
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
        # essa leitura NÃO se perdeu: ela passou para o card de quem está no
        # limite de carga, acima das tabelas, que é onde o sobrecarregado
        # aparece agora. Sem esse card, inverter aqui esconderia o gargalo.
        #
        # O nome é o desempate, senão pessoas com a mesma carga trocam de
        # lugar a cada refresh (a ordem vinha do dicionário de usuários).
        coordenadores.sort(key=lambda x: (x["total"], x["nome"]))
        consultores.sort(key=lambda x: (x["total"], x["nome"]))

        return {
            "coordenadores": coordenadores,
            "consultores": consultores,
            # A checagem de grade horária (§7.3) depende da F13, que não
            # entrou nesta fatia — a carga por projeto já é o essencial.
            "grade_horaria_disponivel": False,
        }


class AtrasosUseCase(_BaseMonitoramento):
    """§7.4 — por projeto e por coordenador, com motivo explícito."""

    def execute(self, current_user, frente_id: Optional[int] = None, referencia: Optional[date] = None):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id)
        ctx = self._contexto(projetos)
        atrasos = self._atrasos(projetos, ctx, hoje)

        por_projeto = []
        for p in projetos:
            atraso = atrasos[p.id]
            if not atraso.atrasado:
                continue
            por_projeto.append(
                {
                    "projeto_id": p.id,
                    "projeto_nome": p.nome,
                    "status": p.status,
                    "dias_totais": atraso.dias_totais,
                    "motivos": [
                        {
                            "tipo": m.tipo,
                            "descricao": m.descricao,
                            "dias": m.dias,
                            "escopo": m.escopo_nome,
                            "projeto_escopo_id": m.projeto_escopo_id,
                            "data_referencia": m.data_referencia,
                        }
                        for m in atraso.motivos
                    ],
                }
            )
        por_projeto.sort(key=lambda x: -x["dias_totais"])

        # Por coordenador: o objetivo do §7.4 é identificar PADRÃO recorrente,
        # não julgar um caso isolado — por isso conta projetos e dias juntos.
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
                    "dias_acumulados": 0,
                },
            )
            entrada["projetos"] += 1
            atraso = atrasos.get(m.projeto_id)
            if atraso and atraso.atrasado:
                entrada["atrasados"] += 1
                entrada["dias_acumulados"] += atraso.dias_totais

        return {
            "por_projeto": por_projeto,
            "por_coordenador": sorted(
                por_coordenador.values(), key=lambda x: -x["dias_acumulados"]
            ),
        }


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

    def execute(self, current_user, frente_id: Optional[int] = None, referencia: Optional[date] = None):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id)
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

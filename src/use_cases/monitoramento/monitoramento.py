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
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.atraso_monitoramento import calcular_atraso_projeto
from src.utils.banca_status import ABERTA, calcular_status_banca
from src.utils.tarefa_status import eh_vencida, esta_ativa, janela_semana

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
        self.coluna_repository = TarefaColunaRepository(db)

    def _projetos_visiveis(self, current_user, frente_id: Optional[int]) -> List[ProjetoModel]:
        query = aplicar_recorte_visao(
            self.db.query(ProjetoModel), current_user, self.db, frente_id
        )
        return query.all()

    def _encerra_por_coluna(self) -> Dict[int, bool]:
        """`coluna_id → encerra_tarefa`. "Vencida" e "ativa" dependem disto,
        e não mais de uma lista fixa de status: as colunas do kanban são
        configuráveis pela diretoria."""
        return {c.id: c.encerra_tarefa for c in self.coluna_repository.listar()}

    def _contexto(self, projetos):
        ids = [p.id for p in projetos]
        escopos = self.escopo_repository.get_by_projetos(ids)
        bancas = self.banca_repository.get_by_projeto_escopos([e.id for e in escopos])
        catalogo = {e.id: e.nome for e in self.catalogo_repository.get_all()}
        return {
            "ids": ids,
            "escopos_por_projeto": _agrupar(escopos, "projeto_id"),
            "bancas_por_escopo": {b.projeto_escopo_id: b for b in bancas},
            "nomes_escopo": {
                e.id: e.nome_customizado or catalogo.get(e.escopo_id, "escopo") for e in escopos
            },
        }

    def _atrasos(self, projetos, ctx, referencia: date):
        return {
            p.id: calcular_atraso_projeto(
                p.id,
                ctx["escopos_por_projeto"].get(p.id, []),
                ctx["bancas_por_escopo"],
                ctx["nomes_escopo"],
                referencia,
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

        return {
            "kpis": {
                "total": len(projetos),
                "em_execucao": sum(1 for p in projetos if p.status in STATUS_EM_EXECUCAO),
                "perto_de_finalizar": sum(1 for p in projetos if p.status in STATUS_PERTO_DO_FIM),
                "atrasados": sum(1 for p in em_curso if atrasos[p.id].atrasado),
                "pausados": sum(1 for p in projetos if p.status == "pausado"),
                "finalizados": sum(1 for p in projetos if p.status == "finalizado"),
            },
            "por_status": dict(por_status),
            "placar_gestao": {
                "percentual": placar,
                "no_prazo": len(no_prazo),
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
        proximas = []
        for escopo_id, banca in ctx["bancas_por_escopo"].items():
            if not banca.data_hora:
                continue
            dia = banca.data_hora.date()
            if not (hoje <= dia <= limite):
                continue
            if calcular_status_banca(banca.data_hora, banca.realizado_em) != ABERTA:
                continue
            projeto_id = escopo_para_projeto.get(escopo_id)
            proximas.append(
                {
                    "projeto_id": projeto_id,
                    "projeto_nome": nomes_projeto.get(projeto_id, ""),
                    "escopo": ctx["nomes_escopo"].get(escopo_id, ""),
                    "data_hora": banca.data_hora,
                }
            )
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
    """§7.2 — quem está distribuindo tarefa e fazendo reunião, sem abrir cada projeto."""

    def execute(self, current_user, frente_id: Optional[int] = None, referencia: Optional[date] = None):
        hoje = referencia or date.today()
        projetos = self._projetos_visiveis(current_user, frente_id)
        ids = [p.id for p in projetos]
        inicio, fim = janela_semana(hoje)

        tarefas_por_projeto = _agrupar(self.tarefa_repository.get_by_projetos(ids), "projeto_id")
        encerra = self._encerra_por_coluna()
        reunioes = self.reuniao_repository.get_by_projetos_e_janela(ids, inicio, fim)
        reunioes_por_projeto = _agrupar(reunioes, "projeto_id")

        tarefas = []
        for p in projetos:
            do_projeto = tarefas_por_projeto.get(p.id, [])
            criadas_na_semana = [
                t for t in do_projeto if t.criado_em and t.criado_em.date() >= inicio
            ]
            movimentacoes = [t.movida_em for t in do_projeto if t.movida_em]
            tarefas.append(
                {
                    "projeto_id": p.id,
                    "projeto_nome": p.nome,
                    "distribuiu_na_semana": len(criadas_na_semana) > 0,
                    "total": len(do_projeto),
                    "ativas": sum(
                        1 for t in do_projeto if esta_ativa(encerra.get(t.coluna_id, False))
                    ),
                    "vencidas": sum(
                        1
                        for t in do_projeto
                        if eh_vencida(t.prazo, encerra.get(t.coluna_id, False), hoje)
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

        return {
            "semana": {"inicio": inicio, "fim": fim},
            "tarefas": tarefas,
            "reunioes": reunioes_resposta,
        }


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
        coordenadores.sort(key=lambda x: -x["total"])
        consultores.sort(key=lambda x: -x["total"])

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

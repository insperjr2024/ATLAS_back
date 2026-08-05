"""Carga inicial para desenvolvimento e demo.

Reproduz o caso que percorre a documentação inteira (docs/banco-de-dados.md):
a gestão 2026.2, as 4 frentes com seus pisos, o catálogo de escopos do §4 e a
equipe do Projeto Alfa.

Rodar:  uv run python -m scripts.seed
É idempotente — rodar de novo não duplica nada.
"""

from datetime import date, datetime, time, timedelta

from src.database.database import SessionLocal
from src.models.banca_model import BancaModel
from src.models.cargo_model import CargoModel
from src.models.configuracao_model import ConfiguracaoModel
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.escopo_model import EscopoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.semestre_model import SemestreModel
from src.models.tarefa_coluna_model import TarefaColunaModel
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_model import UsuarioModel
from src.utils.senha import hash_senha

SENHA_PADRAO = "atlas123"

# Piso de membros da própria frente exigido em cada banca (§8).
FRENTES = [
    ("Business", 3),
    ("Direito", 1),
    ("Tech", 2),
    ("Engenharia de Processos", 2),
]

# O catálogo do §4 do briefing.
ESCOPOS = {
    "Business": [
        "Análise Mercadológica",
        "Plano Estratégico de Marketing",
        "Plano Operacional",
        "Viabilidade Financeira",
    ],
    "Direito": [
        "Elaboração e/ou Revisão Contratual",
        "Planejamento Consultivo Societário",
        "Planejamento Consultivo de Propriedade Industrial",
        "Planejamento e Análise Tributária",
    ],
    "Tech": [
        "Desenvolvimento Tech",
        "AI e Automações",
    ],
    "Engenharia de Processos": [
        "Simulação e Otimização de Processos",
    ],
}

CARGOS = [
    # (nome, definir_formulario, agendar_banca, gerenciar_cargos)
    ("Diretor de Projetos", True, True, True),
    ("Gerente de Frente", False, True, False),
    ("Coordenador", False, True, False),
    ("Membro", False, False, False),
]

# (nome, email, posicao, cargo, frentes, status)
USUARIOS = [
    ("Dani Alves", "dani@al.insper.edu.br", "diretor", "Diretor de Projetos", [], "ativo"),
    ("Gil Nunes", "gil@gmail.com", "gerente", "Gerente de Frente", ["Business"], "ativo"),
    ("Gabi Rocha", "gabi@al.insper.edu.br", "gerente", "Gerente de Frente", ["Tech"], "ativo"),
    ("Ana Souza", "ana@al.insper.edu.br", "coordenador", "Coordenador", ["Business"], "ativo"),
    ("Bia Martins", "bia@gmail.com", "consultor", "Membro", ["Business"], "ativo"),
    ("Caio Ferreira", "caio@icloud.com", "consultor", "Membro", ["Tech"], "ativo"),
    ("Duda Lima", "duda@al.insper.edu.br", "consultor", "Membro", ["Direito"], "ativo"),
    ("Edu Prado", "edu@gmail.com", "consultor", "Membro", ["Business"], "ex_membro"),
]

SEMESTRE = ("2026.2", date(2026, 7, 1), date(2026, 12, 20))

# As colunas do kanban (§4). Nascem aqui, mas a diretoria edita **dentro de
# cada projeto** — nome, cor, ordem e o "encerra a tarefa" são configuráveis,
# e um projeto pode ter um fluxo diferente do outro.
# (chave, nome, cor, ordem, encerra_tarefa)
COLUNAS_TAREFA = [
    ("a_fazer", "A fazer", "#9CA3AF", 0, False),
    ("em_andamento", "Em andamento", "#3B82F6", 1, False),
    ("validacao", "Validação", "#F59E0B", 2, False),
    ("concluido", "Concluído", "#10B981", 3, True),
    ("cancelado", "Cancelado", "#EF4444", 4, True),
]

# Calendário acadêmico — é esta carga que define o dia útil (§5.4).
DIAS_NAO_LETIVOS = [
    (date(2026, 9, 7), "feriado", "Independência"),
    (date(2026, 10, 12), "feriado", "Nossa Senhora Aparecida"),
    (date(2026, 11, 2), "feriado", "Finados"),
    (date(2026, 11, 15), "feriado", "Proclamação da República"),
    (date(2026, 9, 28), "prova", "Semana de provas P1"),
    (date(2026, 9, 29), "prova", "Semana de provas P1"),
    (date(2026, 9, 30), "prova", "Semana de provas P1"),
    (date(2026, 10, 1), "prova", "Semana de provas P1"),
    (date(2026, 10, 2), "prova", "Semana de provas P1"),
]


def dias_nao_letivos_moveis(hoje: date):
    """Uma semana de provas ancorada em HOJE, além do calendário fixo acima.

    Sem isto o calendário do Insper não aparece na demo: as datas fixas são de
    setembro/outubro e os projetos são ancorados em `hoje`, então os intervalos
    de atraso quase nunca cruzam um dia não letivo — e a tela mostra dias úteis
    que batem com dias corridos, escondendo justamente a regra do §5.4.

    Colocada 2 semanas atrás, ela cai dentro do atraso dos projetos mais
    antigos da demo, e aí "18 dias corridos" aparece como 11 dias úteis.
    """
    segunda = hoje - timedelta(days=hoje.weekday() + 14)
    return [
        (segunda + timedelta(days=i), "prova", "Semana de provas (demo)")
        for i in range(5)
    ]


def obter_ou_criar(db, model, filtros: dict, valores: dict | None = None):
    """Idempotência: só cria se ainda não existir."""
    existente = db.query(model).filter_by(**filtros).first()
    if existente:
        return existente, False
    instancia = model(**{**filtros, **(valores or {})})
    db.add(instancia)
    db.flush()
    return instancia, True


def projetos_da_demo(hoje, frentes, catalogo, usuarios):
    """Os projetos da demo, com as datas ancoradas em `hoje`.

    Cada um existe para exercitar UM caminho do monitoramento (§7). Sem essa
    variedade a tela abre com tudo vermelho ou tudo vazio, e não dá para
    conferir se as regras funcionam:

    | Projeto  | O que ele prova                                            |
    |----------|------------------------------------------------------------|
    | Alfa     | caminho feliz: banca realizada, entrega liberada (§5.5)     |
    | Beta     | banca venceu sem acontecer — o estado `atrasada`            |
    | Gama     | atraso SÓ do cliente: cinza, não pesa contra o time (§7.4)  |
    | Delta    | dois motivos no mesmo projeto: a soma contra o pior isolado |
    | Épsilon  | o degrau LEVE da rampa de severidade (âmbar)                |
    | Zeta     | quadro zerado; marco = última tarefa, não o kickoff         |
    | Eta      | tarefa vencida sem atraso de marco — execução ≠ §7.4        |

    Alfa, Beta e Delta ficam sem tarefa nenhuma de propósito: alimentam a
    lista "Projetos sem tarefa atribuída" com idades diferentes, para os três
    degraus de `nivelSemTarefa` aparecerem juntos na tela.
    """
    dias = lambda n: hoje - timedelta(days=n)  # noqa: E731
    futuro = lambda n: hoje + timedelta(days=n)  # noqa: E731

    ana = usuarios["ana@al.insper.edu.br"].id
    duda = usuarios["duda@al.insper.edu.br"].id

    return [
        {
            "nome": "Projeto Alfa",
            "coordenador_id": ana,
            "frente_ids": [frentes["Business"].id, frentes["Tech"].id],
            "campos": {
                "cliente": "Padaria do Zé",
                "descricao": "Diagnóstico comercial e um app de pedidos para a padaria.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(21),
                "dia_reuniao_padrao": 3,  # quarta
                "criado_por": usuarios["gil@gmail.com"].id,
            },
            "equipe": [
                (ana, "coordenador"),
                (usuarios["bia@gmail.com"].id, "consultor"),
                (usuarios["caio@icloud.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(30), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(21), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(14), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["Análise Mercadológica"].id,
                    "frente_id": frentes["Business"].id,
                    "dias_uteis_vendidos": 15,
                    "status": "em_andamento",
                    "data_inicio": dias(14),
                    "data_entrega_planejada": hoje + timedelta(days=7),
                    # ✅ Realizada e aprovada → a entrega está liberada (§5.5).
                    "_banca": {
                        "data_hora": datetime.combine(dias(3), time(14, 0)),
                        "realizado_em": datetime.combine(dias(3), time(15, 30)),
                        "resultado": "aprovada",
                    },
                },
                {
                    # Vendido e não iniciado: a contagem não corre (§5.4).
                    "escopo_id": catalogo["Desenvolvimento Tech"].id,
                    "frente_id": frentes["Tech"].id,
                    "dias_uteis_vendidos": 20,
                    "status": "nao_iniciado",
                },
            ],
        },
        {
            "nome": "Projeto Beta",
            "coordenador_id": duda,
            "frente_ids": [frentes["Direito"].id],
            "campos": {
                "cliente": "Oficina da Lu",
                "descricao": "Revisão contratual e adequação societária da oficina.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(28),
                "dia_reuniao_padrao": 2,  # terça
                "criado_por": usuarios["dani@al.insper.edu.br"].id,
            },
            "equipe": [
                (duda, "coordenador"),
                (usuarios["bia@gmail.com"].id, "consultor"),
                (usuarios["caio@icloud.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(40), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(28), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(21), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["Elaboração e/ou Revisão Contratual"].id,
                    "frente_id": frentes["Direito"].id,
                    "dias_uteis_vendidos": 12,
                    "status": "em_andamento",
                    "data_inicio": dias(21),
                    "data_entrega_planejada": dias(2),
                    # Venceu e NÃO aconteceu: `realizado_em` vazio → atrasada.
                    "_banca": {
                        "data_hora": datetime.combine(dias(5), time(10, 0)),
                        "realizado_em": None,
                        "resultado": None,
                    },
                },
            ],
        },
        # ─── Gama · atraso que NÃO é do time ──────────────────────────────
        # A entrega escorregou por agenda do cliente (`tipo_atraso_entrega =
        # externo`). O §7.4 manda não pesar isso contra o time, então na aba
        # de Atrasos ele aparece em CINZA, com a pílula "espera do cliente",
        # e entra na contagem "N só por agenda do cliente". A banca está
        # realizada de propósito: se ela também estivesse atrasada, o projeto
        # deixaria de ser "só externo" e o caso sumiria.
        {
            "nome": "Projeto Gama",
            "coordenador_id": ana,
            "frente_ids": [frentes["Business"].id],
            "campos": {
                "cliente": "Mercado São Jorge",
                "descricao": "Viabilidade financeira da abertura de uma segunda loja.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(35),
                "dia_reuniao_padrao": 1,  # segunda
                "criado_por": usuarios["gil@gmail.com"].id,
            },
            "equipe": [
                (ana, "coordenador"),
                (usuarios["bia@gmail.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(50), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(35), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(28), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["Viabilidade Financeira"].id,
                    "frente_id": frentes["Business"].id,
                    "dias_uteis_vendidos": 18,
                    "status": "em_andamento",
                    "data_inicio": dias(28),
                    "data_entrega_planejada": dias(9),
                    "tipo_atraso_entrega": "externo",
                    "_banca": {
                        "data_hora": datetime.combine(dias(12), time(14, 0)),
                        "realizado_em": datetime.combine(dias(12), time(15, 0)),
                        "resultado": "aprovada",
                    },
                },
            ],
            # Tem tarefa em dia: fica FORA da lista "sem tarefa atribuída",
            # para o caso externo aparecer limpo na aba de Atrasos.
            "tarefas": [
                ("Levantar custos da segunda loja", "bia@gmail.com", futuro(6), "em_andamento", dias(4)),
                ("Montar projeção de fluxo de caixa", "bia@gmail.com", futuro(10), "a_fazer", dias(2)),
            ],
        },
        # ─── Delta · dois motivos no mesmo projeto ────────────────────────
        # Uma banca vencida há muito (crítico) e uma entrega interna vencida
        # há pouco (leve). É o caso que o número grande sozinho mentia: a
        # SOMA dos dois passa de 10 e leria como crítico mesmo que nenhum
        # motivo isolado fosse. Aqui a soma vem rotulada como "soma" e a cor
        # sai do pior motivo. Sem tarefa nenhuma de propósito — também é o
        # pior caso da lista "sem tarefa atribuída".
        {
            "nome": "Projeto Delta",
            "coordenador_id": duda,
            "frente_ids": [frentes["Direito"].id],
            "campos": {
                "cliente": "Transportadora Vale",
                "descricao": "Reestruturação societária e revisão tributária.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(45),
                "dia_reuniao_padrao": 4,  # quinta
                "criado_por": usuarios["dani@al.insper.edu.br"].id,
            },
            "equipe": [
                (duda, "coordenador"),
                (usuarios["caio@icloud.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(60), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(45), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(38), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["Planejamento e Análise Tributária"].id,
                    "frente_id": frentes["Direito"].id,
                    "dias_uteis_vendidos": 14,
                    "status": "em_andamento",
                    "data_inicio": dias(38),
                    "_banca": {
                        "data_hora": datetime.combine(dias(24), time(9, 0)),
                        "realizado_em": None,
                        "resultado": None,
                    },
                },
                {
                    "escopo_id": catalogo["Planejamento Consultivo Societário"].id,
                    "frente_id": frentes["Direito"].id,
                    "dias_uteis_vendidos": 10,
                    "status": "em_andamento",
                    "data_inicio": dias(30),
                    "data_entrega_planejada": dias(4),
                    "tipo_atraso_entrega": "interno",
                },
            ],
        },
        # ─── Épsilon · o degrau LEVE da rampa ─────────────────────────────
        # Banca vencida há poucos dias úteis: cai em "até 3 dias", o âmbar.
        # Sem um caso assim a legenda tem três degraus e a tela só mostra
        # vermelho, e não dá para conferir se a rampa inteira funciona.
        {
            "nome": "Projeto Épsilon",
            "coordenador_id": ana,
            "frente_ids": [frentes["Business"].id],
            "campos": {
                "cliente": "Café da Praça",
                "descricao": "Plano operacional para a expansão do delivery.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(12),
                "dia_reuniao_padrao": 3,  # quarta
                "criado_por": usuarios["gil@gmail.com"].id,
            },
            "equipe": [
                (ana, "coordenador"),
                (usuarios["bia@gmail.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(20), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(12), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(6), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["Plano Operacional"].id,
                    "frente_id": frentes["Business"].id,
                    "dias_uteis_vendidos": 10,
                    "status": "em_andamento",
                    "data_inicio": dias(6),
                    "_banca": {
                        "data_hora": datetime.combine(dias(3), time(11, 0)),
                        "realizado_em": None,
                        "resultado": None,
                    },
                },
            ],
            "tarefas": [
                ("Mapear rotas de entrega", "bia@gmail.com", futuro(5), "em_andamento", dias(2)),
            ],
            # "Realizou reunião" é AUSÊNCIA DE LINHA na janela seg–dom, não um
            # campo. Só Épsilon e Eta registram: os outros aparecem como "não"
            # justamente por não terem linha nenhuma.
            "reunioes": [hoje - timedelta(days=hoje.weekday())],
        },
        # ─── Zeta · quadro zerado, marco = ÚLTIMA TAREFA ──────────────────
        # O único projeto da demo que exercita o ramo `"ultima_tarefa"` do
        # `_marco_sem_tarefa`. Todas as tarefas foram concluídas e nenhuma
        # nova entrou desde então: `sem_tarefas` é falso (já teve tarefa) mas
        # `sem_tarefas_ativas` é verdadeiro — situações que a diretoria trata
        # diferente. A coluna "Sem tarefa nova há" conta desde a ÚLTIMA
        # TAREFA CRIADA, não desde o kickoff.
        {
            "nome": "Projeto Zeta",
            "coordenador_id": usuarios["caio@icloud.com"].id,
            "frente_ids": [frentes["Tech"].id],
            "campos": {
                "cliente": "Clínica Bem Viver",
                "descricao": "Automação do agendamento de consultas.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(60),
                "dia_reuniao_padrao": 2,  # terça
                "criado_por": usuarios["gabi@al.insper.edu.br"].id,
            },
            "equipe": [
                (usuarios["caio@icloud.com"].id, "coordenador"),
                (usuarios["bia@gmail.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(75), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(60), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(53), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["AI e Automações"].id,
                    "frente_id": frentes["Tech"].id,
                    "dias_uteis_vendidos": 20,
                    "status": "em_andamento",
                    "data_inicio": dias(53),
                    "_banca": {
                        "data_hora": datetime.combine(dias(30), time(10, 0)),
                        "realizado_em": datetime.combine(dias(30), time(11, 30)),
                        "resultado": "aprovada",
                    },
                },
            ],
            "tarefas": [
                ("Levantar requisitos do agendamento", "caio@icloud.com", dias(40), "concluido", dias(50)),
                ("Prototipar o fluxo de confirmação", "bia@gmail.com", dias(32), "concluido", dias(42)),
                ("Integrar com o WhatsApp", "caio@icloud.com", dias(20), "concluido", dias(26)),
            ],
        },
        # ─── Eta · tarefas VENCIDAS ───────────────────────────────────────
        # Quadro com tarefa em atraso, para a coluna "Vencidas" e a de
        # "Atraso" (o pior do quadro, em dias úteis) saírem do zero. Note que
        # este projeto NÃO está atrasado pelo §7.4 — banca e entrega estão em
        # dia. É a distinção entre as duas abas: atraso de execução não é
        # atraso de marco.
        {
            "nome": "Projeto Eta",
            "coordenador_id": usuarios["caio@icloud.com"].id,
            "frente_ids": [frentes["Tech"].id],
            "campos": {
                "cliente": "Escola Girassol",
                "descricao": "Portal de comunicação com os responsáveis.",
                "status": "em_andamento",
                "dias_ambientacao": 5,
                "data_kickoff": dias(22),
                "dia_reuniao_padrao": 5,  # sexta
                "criado_por": usuarios["gabi@al.insper.edu.br"].id,
            },
            "equipe": [
                (usuarios["caio@icloud.com"].id, "coordenador"),
                (usuarios["bia@gmail.com"].id, "consultor"),
            ],
            "historico": [
                (None, "vendido", datetime.combine(dias(32), time(9, 0))),
                ("vendido", "ambientacao", datetime.combine(dias(22), time(9, 0))),
                ("ambientacao", "em_andamento", datetime.combine(dias(15), time(9, 0))),
            ],
            "escopos": [
                {
                    "escopo_id": catalogo["Desenvolvimento Tech"].id,
                    "frente_id": frentes["Tech"].id,
                    "dias_uteis_vendidos": 16,
                    "status": "em_andamento",
                    "data_inicio": dias(15),
                    "data_entrega_planejada": hoje + timedelta(days=10),
                },
            ],
            "tarefas": [
                ("Montar a tela de avisos", "bia@gmail.com", dias(11), "a_fazer", dias(14)),
                ("Configurar envio de e-mail", "caio@icloud.com", dias(4), "em_andamento", dias(9)),
                ("Escrever os testes do portal", "bia@gmail.com", futuro(8), "a_fazer", dias(3)),
            ],
            "reunioes": [hoje - timedelta(days=hoje.weekday())],
        },
    ]


def executar():
    db = SessionLocal()
    hoje = date.today()
    criados = {
        "frente": 0, "escopo": 0, "cargo": 0, "usuario": 0, "dia": 0,
        "projeto": 0, "escopo_vendido": 0, "banca": 0, "coluna": 0,
        "tarefa": 0, "reuniao": 0,
    }

    try:
        # 1 · Frentes
        frentes = {}
        for nome, piso in FRENTES:
            frente, novo = obter_ou_criar(
                db, FrenteModel, {"nome": nome}, {"ativa": True, "piso_banca": piso}
            )
            # Frente que já existia pode não ter o piso certo ainda.
            frente.piso_banca = piso
            frentes[nome] = frente
            criados["frente"] += novo

        # 2 · Catálogo de escopos, agora com dono
        for nome_frente, nomes in ESCOPOS.items():
            for nome in nomes:
                escopo, novo = obter_ou_criar(db, EscopoModel, {"nome": nome})
                escopo.frente_id = frentes[nome_frente].id
                escopo.ativo = True
                criados["escopo"] += novo

        # 3 · Cargos (permissões do módulo de bancas)
        cargos = {}
        for nome, formulario, banca, gerenciar in CARGOS:
            cargo, novo = obter_ou_criar(
                db,
                CargoModel,
                {"nome": nome},
                {
                    "pode_definir_formulario": formulario,
                    "pode_agendar_banca": banca,
                    "pode_gerenciar_cargos": gerenciar,
                },
            )
            cargos[nome] = cargo
            criados["cargo"] += novo

        # 4 · Gestão semestral + calendário do Insper
        nome_sem, inicio, fim = SEMESTRE
        semestre, _ = obter_ou_criar(
            db, SemestreModel, {"nome": nome_sem},
            {"inicio": inicio, "fim": fim, "status": "ativa"},
        )
        db.flush()

        for data, tipo, descricao in DIAS_NAO_LETIVOS + dias_nao_letivos_moveis(hoje):
            _, novo = obter_ou_criar(
                db, DiaNaoLetivoModel,
                {"semestre_id": semestre.id, "data": data},
                {"tipo": tipo, "descricao": descricao},
            )
            criados["dia"] += novo

        # 5 · Membros pré-cadastrados (§10 — ninguém se auto-registra)
        usuarios_por_email = {}
        for nome, email, posicao, nome_cargo, nomes_frentes, status in USUARIOS:
            usuario, novo = obter_ou_criar(
                db, UsuarioModel,
                {"email_insper": email},
                {
                    "nome": nome,
                    "senha_hash": hash_senha(SENHA_PADRAO),
                    "cargo_id": cargos[nome_cargo].id,
                    "posicao": posicao,
                    "status": status,
                    "ativo": status == "ativo",
                },
            )
            criados["usuario"] += novo
            db.flush()
            usuarios_por_email[email] = usuario

            for nome_frente in nomes_frentes:
                obter_ou_criar(
                    db, UsuarioFrenteModel,
                    {"usuario_id": usuario.id, "frente_id": frentes[nome_frente].id},
                )

        # 6 · Os projetos da demo.
        #
        # As datas são ancoradas em HOJE, não fixas: um seed com data cravada
        # envelhece e a contagem de dias aparece zerada (intervalo invertido),
        # que é justamente o que a demo precisa mostrar viva.
        catalogo = {e.nome: e for e in db.query(EscopoModel).all()}

        for spec in projetos_da_demo(hoje, frentes, catalogo, usuarios_por_email):
            projeto, novo = obter_ou_criar(
                db, ProjetoModel, {"nome": spec["nome"]}, spec["campos"]
            )
            db.flush()
            if not novo:
                continue
            criados["projeto"] += 1

            for frente_id in spec["frente_ids"]:
                db.add(ProjetoFrenteModel(projeto_id=projeto.id, frente_id=frente_id))

            for usuario_id, papel in spec["equipe"]:
                db.add(
                    ProjetoMembroModel(
                        projeto_id=projeto.id,
                        usuario_id=usuario_id,
                        papel=papel,
                        entrou_em=spec["campos"]["data_kickoff"],
                    )
                )

            for anterior, novo_status, quando in spec["historico"]:
                db.add(
                    ProjetoStatusHistoricoModel(
                        projeto_id=projeto.id,
                        status_anterior=anterior,
                        status_novo=novo_status,
                        alterado_em=quando,
                    )
                )

            for escopo_spec in spec["escopos"]:
                banca_spec = escopo_spec.pop("_banca", None)
                escopo = ProjetoEscopoModel(projeto_id=projeto.id, **escopo_spec)
                db.add(escopo)
                db.flush()
                criados["escopo_vendido"] += 1

                if banca_spec:
                    db.add(
                        BancaModel(
                            nome_projeto=projeto.nome,
                            escopo_id=escopo.escopo_id,
                            coordenador_id=spec["coordenador_id"],
                            projeto_escopo_id=escopo.id,
                            **banca_spec,
                        )
                    )
                    criados["banca"] += 1

            # As colunas do projeto precisam existir ANTES das tarefas dele: a
            # tarefa aponta para uma coluna e não guarda mais status próprio.
            # O bloco geral abaixo (seção 7) cobre os projetos que já existiam;
            # este cobre os que acabaram de nascer, para as tarefas terem onde
            # cair. `obter_ou_criar` é idempotente, então não duplica.
            colunas_do_projeto = {}
            for chave, nome_col, cor, ordem, encerra in COLUNAS_TAREFA:
                coluna, novo = obter_ou_criar(
                    db, TarefaColunaModel,
                    {"projeto_id": projeto.id, "chave": chave},
                    {"nome": nome_col, "cor": cor, "ordem": ordem, "encerra_tarefa": encerra},
                )
                colunas_do_projeto[chave] = coluna.id
                criados["coluna"] += novo

            # `criado_em` é explícito porque é ELE que o §7.2 usa como marco de
            # "sem tarefa nova há N dias". Deixar o server_default carimbar
            # `now()` faria toda a demo nascer com 0 dias e a coluna morta.
            #
            # O 4º item da tupla era o status da tarefa; virou a CHAVE da
            # coluna do kanban. Os valores não mudaram ("a_fazer",
            # "em_andamento", "concluido") porque são exatamente as chaves de
            # `COLUNAS_TAREFA` — mudou o que eles significam.
            for titulo, email, prazo, chave_coluna, criada_em in spec.get("tarefas", []):
                db.add(
                    TarefaModel(
                        projeto_id=projeto.id,
                        titulo=titulo,
                        responsavel_id=usuarios_por_email[email].id,
                        prazo=prazo,
                        coluna_id=colunas_do_projeto[chave_coluna],
                        criado_por=spec["coordenador_id"],
                        criado_em=datetime.combine(criada_em, time(9, 0)),
                        movida_em=datetime.combine(criada_em, time(9, 0)),
                    )
                )
                criados["tarefa"] += 1

            for data_reuniao in spec.get("reunioes", []):
                db.add(
                    ReuniaoSemanalModel(
                        projeto_id=projeto.id,
                        data_reuniao=data_reuniao,
                        registrado_por=spec["coordenador_id"],
                    )
                )
                criados["reuniao"] += 1

        # 7 · Colunas do kanban — um conjunto POR PROJETO.
        #
        # Varre todos os projetos do banco (não só os recém-criados): um seed
        # rodado sobre uma base que já existia também precisa dar board a
        # quem ainda não tem.
        for projeto in db.query(ProjetoModel).all():
            for chave, nome_col, cor, ordem, encerra in COLUNAS_TAREFA:
                _, novo = obter_ou_criar(
                    db, TarefaColunaModel,
                    {"projeto_id": projeto.id, "chave": chave},
                    {"nome": nome_col, "cor": cor, "ordem": ordem, "encerra_tarefa": encerra},
                )
                criados["coluna"] += novo

        # 8 · Configuração global
        config = db.query(ConfiguracaoModel).first()
        if not config:
            config = ConfiguracaoModel(
                vagas_por_banca=5, cargo_padrao_id=cargos["Membro"].id
            )
            db.add(config)

        db.commit()

        print("Seed aplicado:")
        for chave, total in criados.items():
            print(f"  {chave:8} +{total}")
        print(f"\n  Gestão ativa: {nome_sem} ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y})")
        print(
            f"  {len(DIAS_NAO_LETIVOS) + len(dias_nao_letivos_moveis(hoje))} "
            "dias não letivos carregados"
        )
        # Setas em ASCII: o console do Windows abre em cp1252 e `→` derruba o
        # script com UnicodeEncodeError DEPOIS do commit — o seed funciona mas
        # termina cuspindo traceback, e parece que falhou.
        print(f"\n  Login de qualquer usuário com a senha: {SENHA_PADRAO}")
        print("    dani@al.insper.edu.br  -> diretor")
        print("    gil@gmail.com          -> gerente (Business)")
        print("    ana@al.insper.edu.br   -> coordenador (Business)")
        print("    caio@icloud.com        -> consultor (Tech)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    executar()

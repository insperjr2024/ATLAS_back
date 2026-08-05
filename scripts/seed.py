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
#
# O 4º campo é a FRENTE dona do dia; `None` vale para todas. Feriado é do país,
# então é global. Semana de prova é do CURSO — as datas de Administração não
# são as de Engenharia —, então fica presa a uma frente. O seed usa Business
# como exemplo; as outras frentes recebem as suas quando a diretoria sobe o PDF
# do curso delas.
DIAS_NAO_LETIVOS = [
    (date(2026, 9, 7), "feriado", "Independência", None),
    (date(2026, 10, 12), "feriado", "Nossa Senhora Aparecida", None),
    (date(2026, 11, 2), "feriado", "Finados", None),
    (date(2026, 11, 15), "feriado", "Proclamação da República", None),
    (date(2026, 9, 28), "prova", "Semana de provas P1", "Business"),
    (date(2026, 9, 29), "prova", "Semana de provas P1", "Business"),
    (date(2026, 9, 30), "prova", "Semana de provas P1", "Business"),
    (date(2026, 10, 1), "prova", "Semana de provas P1", "Business"),
    (date(2026, 10, 2), "prova", "Semana de provas P1", "Business"),
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
    """Os dois projetos da demo, com as datas ancoradas em `hoje`.

    **Alfa** é o caminho feliz: sinérgico, um escopo correndo com banca já
    realizada e aprovada (a entrega está liberada) e outro ainda não iniciado
    (a contagem não corre).

    **Beta** existe para a aba Atrasos ter o que mostrar: a banca dele venceu
    e ninguém marcou `realizado_em` — é exatamente o estado `atrasada` que
    não existia no sistema antes da F5. Sem um caso assim, o placar da gestão
    dá 100% e não dá para saber se a costura funcionou.
    """
    dias = lambda n: hoje - timedelta(days=n)  # noqa: E731

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
                    # 🚨 Venceu e NÃO aconteceu: `realizado_em` vazio → atrasada.
                    "_banca": {
                        "data_hora": datetime.combine(dias(5), time(10, 0)),
                        "realizado_em": None,
                        "resultado": None,
                    },
                },
            ],
        },
    ]


def executar():
    db = SessionLocal()
    hoje = date.today()
    criados = {
        "frente": 0, "escopo": 0, "cargo": 0, "usuario": 0, "dia": 0,
        "projeto": 0, "escopo_vendido": 0, "banca": 0, "coluna": 0,
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

        for data, tipo, descricao, nome_frente in DIAS_NAO_LETIVOS:
            frente_do_dia = frentes[nome_frente].id if nome_frente else None
            _, novo = obter_ou_criar(
                db, DiaNaoLetivoModel,
                {"semestre_id": semestre.id, "data": data, "frente_id": frente_do_dia},
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
        print(f"  {len(DIAS_NAO_LETIVOS)} dias não letivos carregados")
        print(f"\n  Login de qualquer usuário com a senha: {SENHA_PADRAO}")
        print("    dani@al.insper.edu.br  → diretor")
        print("    gil@gmail.com          → gerente (Business)")
        print("    ana@al.insper.edu.br   → coordenador (Business)")
        print("    caio@icloud.com        → consultor (Tech)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    executar()

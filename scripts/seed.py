"""Carga inicial para desenvolvimento e demo.

Reproduz o caso que percorre a documentação inteira (docs/banco-de-dados.md):
a gestão 2026.2, as 4 frentes com seus pisos, o catálogo de escopos do §4 e a
equipe do Projeto Alfa.

Rodar:  uv run python -m scripts.seed
É idempotente — rodar de novo não duplica nada.
"""

from datetime import date

from src.database.database import SessionLocal
from src.models.cargo_model import CargoModel
from src.models.configuracao_model import ConfiguracaoModel
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.escopo_model import EscopoModel
from src.models.frente_model import FrenteModel
from src.models.semestre_model import SemestreModel
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


def obter_ou_criar(db, model, filtros: dict, valores: dict | None = None):
    """Idempotência: só cria se ainda não existir."""
    existente = db.query(model).filter_by(**filtros).first()
    if existente:
        return existente, False
    instancia = model(**{**filtros, **(valores or {})})
    db.add(instancia)
    db.flush()
    return instancia, True


def executar():
    db = SessionLocal()
    criados = {"frente": 0, "escopo": 0, "cargo": 0, "usuario": 0, "dia": 0}

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

        for data, tipo, descricao in DIAS_NAO_LETIVOS:
            _, novo = obter_ou_criar(
                db, DiaNaoLetivoModel,
                {"semestre_id": semestre.id, "data": data},
                {"tipo": tipo, "descricao": descricao},
            )
            criados["dia"] += novo

        # 5 · Membros pré-cadastrados (§10 — ninguém se auto-registra)
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

            for nome_frente in nomes_frentes:
                obter_ou_criar(
                    db, UsuarioFrenteModel,
                    {"usuario_id": usuario.id, "frente_id": frentes[nome_frente].id},
                )

        # 6 · Configuração global
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

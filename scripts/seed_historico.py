"""Popula o banco com projetos ENCERRADOS para testar a aba Histórico (§7).

Cada projeto vem com uma CADEIA de mudanças de status (com o coordenador como
autor), para o modal "Ações recentes" da aba ter conteúdo real — algo como
"Ana Souza · Status: Ambientação → Em andamento".

Recria a cada execução: apaga os projetos deste seed (pelo nome) e seus
vínculos antes de criar de novo, então rodar duas vezes não duplica e sempre
reflete a definição atual. Não toca nos outros projetos do banco.

Uso (com o venv ativado):
    python -m scripts.seed_historico
"""

import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database.database import SessionLocal
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.semestre_model import SemestreModel

# Frentes (ids do banco): Business=1, Direito=2, Tech=3, Eng. de Processos=4.
BUSINESS, DIREITO, TECH, PROCESSOS = 1, 2, 3, 4

# Coordenadores existentes (posicao=coordenador).
ANA, RAFA, MALU, TEO, NINA = 4, 10, 11, 12, 13

# Semestres passados que a aba precisa para agrupar. O 2026.2 já existe (ativa);
# os anteriores entram como arquivada (§12: arquivar = mudar status).
SEMESTRES = [
    ("2025.1", date(2025, 2, 1), date(2025, 6, 30), "arquivada"),
    ("2025.2", date(2025, 8, 1), date(2025, 12, 20), "arquivada"),
    ("2026.1", date(2026, 2, 1), date(2026, 6, 30), "arquivada"),
]

# A ordem do ciclo de vida (§4). A cadeia de histórico de cada projeto é o
# prefixo desta lista até o status final dele.
LIFECYCLE = [
    "vendido",
    "ambientacao",
    "em_andamento",
    "validacao_bancas",
    "envio_tep",
    "periodo_ajustes",
    "finalizado",
]

# (nome, cliente, frentes, coordenador, kickoff, encerrado_em, status, arquivado)
#
# `status="finalizado"` gera a cadeia inteira até finalizado; o `encerrado_em` e
# o semestre da aba saem da última transição. `arquivado=True` sem finalizar
# grava só o `arquivado_em` (testa o fallback e a tag "Arquivado"), e a cadeia
# vai até o status em que parou. O de 15/01/2026 cai no vão entre semestres:
# vira o grupo "Sem semestre".
PROJETOS = [
    # ── 2026.2 (ativo) ──────────────────────────────────────────────
    ("Reposicionamento de Marca", "Padaria do Zé", [BUSINESS], ANA,
     date(2026, 7, 14), datetime(2026, 11, 28, 15, 0), "finalizado", False),
    ("Plataforma de Agendamento", "Clínica Bem-Estar", [TECH, BUSINESS], RAFA,
     date(2026, 8, 2), datetime(2026, 12, 5, 16, 0), "finalizado", False),
    ("Adequação LGPD", "Oficina da Lu", [DIREITO], MALU,
     date(2026, 8, 11), datetime(2026, 11, 30, 11, 0), "finalizado", False),
    ("Dashboard Comercial", "Distribuidora Aurora", [TECH], TEO,
     date(2026, 8, 20), datetime(2026, 10, 15, 10, 0), "em_andamento", True),
    # ── Sem semestre (vão entre 2025.2 e 2026.1) ────────────────────
    ("Onboarding Digital", "Meridiano Contábil", [TECH], ANA,
     date(2025, 12, 1), datetime(2026, 1, 15, 14, 0), "finalizado", False),
    # ── 2026.1 ──────────────────────────────────────────────────────
    ("Pesquisa de Satisfação", "Rede Sabor & Cia", [BUSINESS], NINA,
     date(2026, 2, 10), datetime(2026, 6, 18, 15, 0), "finalizado", False),
    ("App de Fidelidade", "Cafeteria Grão Nobre", [TECH, BUSINESS], RAFA,
     date(2026, 2, 24), datetime(2026, 6, 30, 16, 0), "finalizado", False),
    ("Contrato de Franquia", "Açaí do Porto", [DIREITO], MALU,
     date(2026, 3, 2), datetime(2026, 6, 12, 11, 0), "finalizado", False),
    ("Landing de Captação", "Estúdio Foco", [TECH], TEO,
     date(2026, 3, 10), datetime(2026, 4, 28, 10, 0), "validacao_bancas", True),
    # ── 2025.2 ──────────────────────────────────────────────────────
    ("Plano de Expansão", "Rede Sabor & Cia", [BUSINESS], ANA,
     date(2025, 8, 12), datetime(2025, 12, 8, 15, 0), "finalizado", False),
    ("Automação de Faturamento", "Transportadora Rota Sul", [TECH, PROCESSOS], RAFA,
     date(2025, 8, 25), datetime(2025, 12, 12, 16, 0), "finalizado", False),
    # ── 2025.1 ──────────────────────────────────────────────────────
    ("Portal do Cliente", "Seguradora Prumo", [TECH], NINA,
     date(2025, 2, 11), datetime(2025, 6, 16, 15, 0), "finalizado", False),
    ("Precificação de Serviços", "Academia Corpo & Ritmo", [BUSINESS, PROCESSOS], MALU,
     date(2025, 2, 24), datetime(2025, 6, 20, 11, 0), "finalizado", False),
]


def cadeia_de_status(kickoff: date, encerrado: datetime, coord: int, status_final: str):
    """As transições de status do projeto, do vendido até o status final.

    A primeira (vendido) é da venda — autor vazio; as demais são do coordenador
    conduzindo o projeto. As datas são interpoladas entre o kickoff e o
    encerramento, e a última cai exatamente no encerramento (é dela que a aba
    tira o `encerrado_em` e o semestre).
    """
    prefixo = LIFECYCLE[: LIFECYCLE.index(status_final) + 1]
    inicio = datetime.combine(kickoff, time(10, 0))
    total = encerrado - inicio
    n = len(prefixo)

    linhas = []
    for i, status in enumerate(prefixo):
        frac = i / (n - 1) if n > 1 else 1
        quando = encerrado if i == n - 1 else inicio + total * frac
        linhas.append(
            ProjetoStatusHistoricoModel(
                status_anterior=prefixo[i - 1] if i > 0 else None,
                status_novo=status,
                alterado_por=None if i == 0 else coord,
                alterado_em=quando,
            )
        )
    return linhas


def limpar_projeto(db, projeto: ProjetoModel):
    """Apaga um projeto do seed e os vínculos que o seed criou para ele."""
    for model in (ProjetoStatusHistoricoModel, ProjetoFrenteModel, ProjetoMembroModel):
        db.query(model).filter(model.projeto_id == projeto.id).delete()
    db.delete(projeto)


def main():
    db = SessionLocal()
    try:
        # 1. Semestres passados que faltam.
        criados_sem = 0
        for nome, inicio, fim, status in SEMESTRES:
            if not db.query(SemestreModel).filter_by(nome=nome).first():
                db.add(SemestreModel(nome=nome, inicio=inicio, fim=fim, status=status))
                criados_sem += 1
        db.flush()

        # 2. Projetos: recria cada um (apaga o antigo do seed, se houver).
        recriados = 0
        for nome, cliente, frentes, coord, kickoff, encerrado, status, arquivado in PROJETOS:
            existente = db.query(ProjetoModel).filter_by(nome=nome).first()
            if existente:
                limpar_projeto(db, existente)
                db.flush()

            projeto = ProjetoModel(
                nome=nome,
                cliente=cliente,
                status=status,
                data_kickoff=kickoff,
                arquivado_em=encerrado if arquivado else None,
            )
            db.add(projeto)
            db.flush()  # para ter o id

            for frente_id in frentes:
                db.add(ProjetoFrenteModel(projeto_id=projeto.id, frente_id=frente_id))

            db.add(
                ProjetoMembroModel(
                    projeto_id=projeto.id,
                    usuario_id=coord,
                    papel="coordenador",
                    entrou_em=kickoff,
                )
            )

            for linha in cadeia_de_status(kickoff, encerrado, coord, status):
                linha.projeto_id = projeto.id
                db.add(linha)

            recriados += 1

        db.commit()
        print(f"Semestres criados: {criados_sem}")
        print(f"Projetos encerrados (re)criados: {recriados}")
        print("Pronto — abra Monitoramento > Histórico de projetos e clique em 'Ações'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

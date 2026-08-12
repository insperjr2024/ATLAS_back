"""Zera os PROJETOS e repovoa o banco com um cenário por funcionalidade.

Feito para testar a plataforma: cada projeto aqui existe para acender uma tela
ou um alerta específico, e o nome de cada um diz qual. Ver `CENARIOS` no fim do
arquivo para a lista.

⚠ **APAGA todos os projetos e tudo que pende deles** — escopos, bancas,
candidaturas, tarefas, cronograma, reuniões, pedidos de dias e notificações.
NÃO toca no que não é projeto: usuários, frentes, catálogo de escopos,
semestre, calendário acadêmico, configurações, permissões por posição e os
formulários (de banca e de desempenho) ficam como estão.

Rodar:  .venv/bin/python -m scripts.seed_cenarios

Não é idempotente no sentido de "rodar de novo não muda nada": rodar de novo
APAGA e recria tudo do zero, com os mesmos cenários. É o comportamento que se
quer numa base de teste — o estado é sempre o mesmo ponto de partida.
"""

from datetime import date, datetime, time, timedelta

from src.database.database import SessionLocal
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_frente_model import BancaFrenteModel
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.models.cronograma_etapa_model import CronogramaEtapaModel
from src.models.cronograma_reajuste_solicitacao_model import (
    CronogramaReajusteSolicitacaoModel,
)
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.entrega_alteracao_model import EntregaAlteracaoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_justificativa_atraso_model import ProjetoJustificativaAtrasoModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.tarefa.colunas import criar_colunas_padrao
from src.utils.dias_uteis import somar_dias_uteis
from src.utils.senha import hash_senha

#: A data de referência do cenário. Tudo é posicionado em relação a ela, para
#: os alertas ("venceu há N dias") caírem onde se espera ao abrir a tela hoje.
HOJE = date(2026, 8, 12)

SENHA = "atlas123"

# As frentes do seed original, por nome — os ids podem variar entre bases.
BUSINESS, DIREITO, TECH, PROCESSOS = "Business", "Direito", "Tech", "Engenharia de Processos"

#: Ordem de remoção: filhos antes dos pais. Escrito à mão, e não derivado do
#: grafo de FKs, porque a ordem também expressa o que É dado de projeto — as
#: tabelas que ficam de fora desta lista são justamente as que devem sobreviver.
TABELAS_A_LIMPAR = [
    "tarefa_comentario",
    "tarefa",
    "tarefa_coluna",
    "avaliacao_nota",
    "avaliacao",
    "candidatura",
    "equipe_projeto",
    "banca_frente",
    "banca_escopo",
    "banca_remarcacao",
    "projeto_remarcacao_banca",
    "solicitacao_troca",
    "banca",
    "cronograma_etapa",
    "cronograma_marco",
    "cronograma_reajuste_solicitacao",
    "entrega_alteracao",
    "projeto_justificativa_atraso",
    "reuniao_semanal",
    "desempenho_lote_projeto",
    "solicitacao_projeto",
    "projeto_membro",
    "projeto_frente",
    "projeto_status_historico",
    "projeto_escopo",
    # A notificação carrega `projeto_id`; as que não são de projeto também vão,
    # porque uma caixa com 177 avisos de um mundo que não existe mais é ruído.
    "notificacao",
    "projeto",
]

#: Gente a mais para as bancas FECHAREM. O §8 exige o piso de cada frente
#: cumprido por gente daquela frente, mais uma liderança (gerente da frente ou
#: diretor) — e a base tinha Direito sem gerente, Processos sem ninguém e só
#: quatro consultores ativos no total. Sem isto, nenhuma banca sinérgica
#: passaria da validação de composição.
PESSOAS_NOVAS = [
    ("Rafa Dias", "rafa@al.insper.edu.br", "gerente", DIREITO),
    ("Lia Costa", "lia@al.insper.edu.br", "gerente", PROCESSOS),
    ("Nina Rocha", "nina@al.insper.edu.br", "consultor", BUSINESS),
    ("Théo Braga", "theo@al.insper.edu.br", "consultor", BUSINESS),
    ("Íris Melo", "iris@al.insper.edu.br", "consultor", BUSINESS),
    ("Léo Pinto", "leo@al.insper.edu.br", "consultor", TECH),
    ("Vera Luz", "vera@al.insper.edu.br", "consultor", TECH),
    ("Hugo Sá", "hugo@al.insper.edu.br", "consultor", DIREITO),
    ("Cléo Antunes", "cleo@al.insper.edu.br", "consultor", DIREITO),
    ("Ravi Nunes", "ravi@al.insper.edu.br", "consultor", PROCESSOS),
    ("Sofia Mendes", "sofia@al.insper.edu.br", "consultor", PROCESSOS),
]


class Mundo:
    """Os dados de referência já resolvidos, para os cenários lerem por nome."""

    def __init__(self, db):
        self.db = db
        self.frentes = {f.nome: f for f in db.query(FrenteModel).all()}
        self.nao_letivos = [d.data for d in db.query(DiaNaoLetivoModel).all()]
        self.usuarios = {u.nome: u for u in db.query(UsuarioModel).all()}
        self.por_frente = self._indexar_por_frente()

    def _indexar_por_frente(self):
        mapa = {nome: {"gerente": [], "consultor": []} for nome in self.frentes}
        ids_frente = {f.id: nome for nome, f in self.frentes.items()}
        for vinculo in self.db.query(UsuarioFrenteModel).all():
            nome_frente = ids_frente.get(vinculo.frente_id)
            usuario = self.db.get(UsuarioModel, vinculo.usuario_id)
            if not nome_frente or not usuario or usuario.status != "ativo":
                continue
            if usuario.posicao in ("gerente", "consultor"):
                mapa[nome_frente][usuario.posicao].append(usuario)
        return mapa

    def frente_id(self, nome):
        return self.frentes[nome].id

    def dia_util(self, inicio, quantidade):
        """`inicio` + N dias úteis, pelo calendário acadêmico carregado."""
        return somar_dias_uteis(inicio, quantidade, self.nao_letivos)

    def dentro_da_janela(self, inicio, vendidos, folga=1):
        """⭐ Um dia que CABE na janela — para a banca do cenário "no prazo".

        A janela fecha em `somar_dias_uteis(inicio, vendidos)`, contando o
        próprio início como dia 1. Marcar a banca em `vendidos + 1` a coloca um
        dia útil FORA, e o escopo aparece atrasado sem que o cenário quisesse —
        foi exatamente o que aconteceu na primeira rodada deste seed, com sete
        projetos "limpos" caindo na lista de atrasos.
        """
        return self.dia_util(inicio, max(1, vendidos - folga))

    def fora_da_janela(self, inicio, vendidos, dias_alem):
        """O oposto: um dia N dias úteis DEPOIS do fim da janela (§10)."""
        return self.dia_util(inicio, vendidos + dias_alem)

    def avaliadores(self, frentes, equipe_ids):
        """Gente que FECHA a composição das frentes dadas, sem tocar na equipe.

        Devolve, por frente: a liderança (gerente da frente) mais o piso em
        consultores daquela frente. É a leitura direta do §8 — e é o que faz a
        banca poder ser registrada como realizada sem `forcar`.
        """
        escolhidos = []
        for nome in frentes:
            piso = self.frentes[nome].piso_banca
            disponiveis = self.por_frente[nome]
            lideres = [u for u in disponiveis["gerente"] if u.id not in equipe_ids]
            consultores = [u for u in disponiveis["consultor"] if u.id not in equipe_ids]
            escolhidos += lideres[:1] + consultores[: max(0, piso - 1)]
        # Sem repetir quem cobre duas frentes, preservando a ordem.
        vistos, unicos = set(), []
        for u in escolhidos:
            if u.id not in vistos:
                vistos.add(u.id)
                unicos.append(u)
        return unicos


def limpar(db):
    """Apaga o dado de projeto, na ordem que respeita as FKs."""
    from sqlalchemy import text

    apagados = {}
    for tabela in TABELAS_A_LIMPAR:
        existe = db.execute(
            text(
                "select count(*) from information_schema.tables "
                "where table_schema=database() and table_name=:t"
            ),
            {"t": tabela},
        ).scalar()
        if not existe:
            continue
        n = db.execute(text(f"select count(*) from `{tabela}`")).scalar()
        if n:
            db.execute(text(f"delete from `{tabela}`"))
            apagados[tabela] = n
    db.commit()
    return apagados


def criar_pessoas(db, mundo):
    """As pessoas que faltavam para as bancas fecharem. Idempotente por e-mail."""
    criadas = []
    for nome, email, posicao, frente in PESSOAS_NOVAS:
        ja = db.query(UsuarioModel).filter_by(email_insper=email).first()
        if ja:
            continue
        usuario = UsuarioModel(
            nome=nome,
            email_insper=email,
            senha_hash=hash_senha(SENHA),
            posicao=posicao,
            status="ativo",
            ativo=True,
            semestre_graduacao=4 if posicao == "consultor" else None,
        )
        db.add(usuario)
        db.flush()
        db.add(UsuarioFrenteModel(usuario_id=usuario.id, frente_id=mundo.frente_id(frente)))
        criadas.append(nome)
    db.commit()
    return criadas


class Construtor:
    """Monta um projeto inteiro — equipe, frentes, kanban e histórico."""

    def __init__(self, db, mundo):
        self.db = db
        self.mundo = mundo

    def projeto(
        self,
        nome,
        *,
        status,
        coordenador,
        consultores=(),
        frentes=(),
        kickoff=None,
        dias_ambientacao=5,
        cliente="Cliente Exemplo",
        dia_reuniao=2,
        criado_em=None,
    ):
        p = ProjetoModel(
            nome=nome,
            cliente=cliente,
            status=status,
            dias_ambientacao=dias_ambientacao,
            data_kickoff=kickoff,
            dia_reuniao_padrao=dia_reuniao,
            criado_por=self.mundo.usuarios["Dani Alves"].id,
            criado_em=datetime.combine(criado_em or (kickoff or HOJE), time(9, 0)),
        )
        self.db.add(p)
        self.db.flush()

        for nome_frente in frentes:
            self.db.add(
                ProjetoFrenteModel(projeto_id=p.id, frente_id=self.mundo.frente_id(nome_frente))
            )

        entrou = kickoff or HOJE
        self.db.add(
            ProjetoMembroModel(
                projeto_id=p.id,
                usuario_id=self.mundo.usuarios[coordenador].id,
                papel="coordenador",
                entrou_em=entrou,
            )
        )
        for consultor in consultores:
            self.db.add(
                ProjetoMembroModel(
                    projeto_id=p.id,
                    usuario_id=self.mundo.usuarios[consultor].id,
                    papel="consultor",
                    entrou_em=entrou,
                )
            )

        criar_colunas_padrao(self.db, p.id)
        self._historico(p, status)
        self.db.flush()
        return p

    def _historico(self, projeto, status):
        """A trilha até o status atual — é dela que saem as janelas de pausa e
        a timeline da aba Histórico."""
        caminho = [
            "vendido",
            "ambientacao",
            "em_andamento",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
        ]
        alvo = "em_andamento" if status == "pausado" else status
        if alvo not in caminho:
            alvo = "em_andamento"
        anterior = None
        quando = datetime.combine(projeto.data_kickoff or HOJE, time(9, 0))
        for etapa in caminho[: caminho.index(alvo) + 1]:
            self.db.add(
                ProjetoStatusHistoricoModel(
                    projeto_id=projeto.id,
                    status_anterior=anterior,
                    status_novo=etapa,
                    alterado_por=self.mundo.usuarios["Dani Alves"].id,
                    alterado_em=quando,
                )
            )
            anterior = etapa
            quando += timedelta(days=2)
        if status == "pausado":
            self.db.add(
                ProjetoStatusHistoricoModel(
                    projeto_id=projeto.id,
                    status_anterior=anterior,
                    status_novo="pausado",
                    alterado_por=self.mundo.usuarios["Dani Alves"].id,
                    alterado_em=quando,
                )
            )

    def escopo(
        self,
        projeto,
        *,
        catalogo=None,
        nome_customizado=None,
        frente,
        vendidos,
        ajustados=0,
        inicio=None,
        entrega_planejada=None,
        entrega_real=None,
        status=None,
        ordem=0,
    ):
        from src.models.escopo_model import EscopoModel

        escopo_id = None
        if catalogo:
            linha = self.db.query(EscopoModel).filter_by(nome=catalogo).first()
            escopo_id = linha.id if linha else None

        e = ProjetoEscopoModel(
            projeto_id=projeto.id,
            escopo_id=escopo_id,
            nome_customizado=nome_customizado,
            frente_id=self.mundo.frente_id(frente),
            dias_uteis_vendidos=vendidos,
            dias_uteis_ajustados=ajustados,
            ordem=ordem,
            data_inicio=inicio,
            data_entrega_planejada=entrega_planejada,
            data_entrega_real=entrega_real,
            status=status
            or ("entregue" if entrega_real else ("em_andamento" if inicio else "nao_iniciado")),
        )
        self.db.add(e)
        self.db.flush()

        if inicio:
            # A reunião inicial é o que ABRE a janela do escopo — sem ela, a
            # `data_inicio` seria um número solto que a tela não sabe explicar.
            self.db.add(
                ReuniaoSemanalModel(
                    projeto_id=projeto.id,
                    projeto_escopo_id=e.id,
                    data_reuniao=inicio,
                    observacoes="Reunião inicial — abertura do escopo",
                    registrado_por=self.mundo.usuarios["Dani Alves"].id,
                )
            )
        if entrega_real:
            self.db.add(
                EntregaAlteracaoModel(
                    projeto_id=projeto.id,
                    projeto_escopo_id=e.id,
                    data_anterior=None,
                    data_nova=entrega_real,
                    justificativa="Primeira marcação",
                    alterado_por=self.mundo.usuarios["Dani Alves"].id,
                )
            )
        return e

    def banca(
        self,
        projeto,
        escopos,
        *,
        quando,
        realizada_em=None,
        frentes,
        coordenador,
        avaliadores=None,
        confirmados=True,
    ):
        equipe = {
            m.usuario_id
            for m in self.db.query(ProjetoMembroModel).filter_by(projeto_id=projeto.id)
        }
        b = BancaModel(
            nome_projeto=projeto.nome,
            escopo_id=escopos[0].escopo_id,
            coordenador_id=self.mundo.usuarios[coordenador].id,
            data_hora=quando,
            realizado_em=realizada_em,
        )
        self.db.add(b)
        self.db.flush()

        for e in escopos:
            self.db.add(BancaEscopoModel(banca_id=b.id, projeto_escopo_id=e.id))
        for nome_frente in frentes:
            self.db.add(
                BancaFrenteModel(banca_id=b.id, frente_id=self.mundo.frente_id(nome_frente))
            )

        escalados = (
            avaliadores
            if avaliadores is not None
            else self.mundo.avaliadores(frentes, equipe)
        )
        for usuario in escalados:
            self.db.add(
                CandidaturaModel(
                    banca_id=b.id,
                    usuario_id=usuario.id,
                    criado_em=datetime.combine(HOJE - timedelta(days=7), time(10, 0)),
                    confirmado=bool(realizada_em) and confirmados,
                )
            )
        self.db.flush()
        return b

    def etapas(self, escopo, blocos):
        """Pinta o cronograma. `blocos` = [(nome, cor, inicio, fim)]."""
        for ordem, (nome, cor, inicio, fim) in enumerate(blocos):
            self.db.add(
                CronogramaEtapaModel(
                    projeto_escopo_id=escopo.id,
                    nome=nome,
                    cor=cor,
                    data_inicio=inicio,
                    data_fim=fim,
                    status="concluida" if fim < HOJE else "em_andamento",
                    ordem=ordem,
                    criado_por=self.mundo.usuarios["Dani Alves"].id,
                )
            )

    def tarefas(self, projeto, itens):
        """`itens` = [(titulo, responsavel, prazo, chave_da_coluna)]."""
        from src.models.tarefa_coluna_model import TarefaColunaModel

        colunas = {
            c.chave: c
            for c in self.db.query(TarefaColunaModel).filter_by(projeto_id=projeto.id)
        }
        for titulo, responsavel, prazo, chave in itens:
            self.db.add(
                TarefaModel(
                    projeto_id=projeto.id,
                    titulo=titulo,
                    responsavel_id=self.mundo.usuarios[responsavel].id,
                    prazo=prazo,
                    coluna_id=colunas[chave].id,
                    criado_por=self.mundo.usuarios["Dani Alves"].id,
                )
            )

    def reuniao(self, projeto, quando, observacoes="Reunião semanal"):
        self.db.add(
            ReuniaoSemanalModel(
                projeto_id=projeto.id,
                data_reuniao=quando,
                observacoes=observacoes,
                registrado_por=self.mundo.usuarios["Dani Alves"].id,
            )
        )

    def pedido_de_dias(
        self, escopo, *, dias, motivo, status="pendente", resposta=None, quando=None
    ):
        self.db.add(
            CronogramaReajusteSolicitacaoModel(
                projeto_escopo_id=escopo.id,
                solicitado_por=self.mundo.usuarios["Ana Souza"].id,
                dias_solicitados=dias,
                motivo=motivo,
                status=status,
                respondido_por=(
                    self.mundo.usuarios["Dani Alves"].id if status != "pendente" else None
                ),
                resposta_justificativa=resposta,
                criado_em=datetime.combine(quando or (HOJE - timedelta(days=3)), time(11, 0)),
                respondido_em=(
                    datetime.combine(HOJE - timedelta(days=2), time(15, 0))
                    if status != "pendente"
                    else None
                ),
            )
        )

    def justificativa_de_atraso(self, projeto, escopo, texto, tipo="escopo"):
        self.db.add(
            ProjetoJustificativaAtrasoModel(
                projeto_id=projeto.id,
                projeto_escopo_id=escopo.id if escopo else None,
                tipo=tipo,
                texto=texto,
                registrado_por=self.mundo.usuarios["Ana Souza"].id,
                registrado_em=datetime.combine(HOJE - timedelta(days=1), time(16, 0)),
            )
        )


def povoar(db, mundo):
    """Um cenário por bloco. O nome do projeto diz o que ele acende."""
    c = Construtor(db, mundo)
    d = mundo.dia_util
    #: Banca que CABE na janela vs. banca N dias úteis além dela.
    no_prazo = mundo.dentro_da_janela
    alem = mundo.fora_da_janela
    resumo = []

    def registrar(nome, o_que_testa):
        resumo.append((nome, o_que_testa))

    # ── 1. Vendido, sem kickoff ────────────────────────────────────────────
    p = c.projeto(
        "01 · Vendido sem kickoff",
        status="vendido",
        coordenador="Ana Souza",
        consultores=["Bia Martins"],
        frentes=[BUSINESS],
        kickoff=None,
    )
    c.escopo(p, catalogo="Análise Mercadológica", frente=BUSINESS, vendidos=10)
    registrar(p.nome, "alerta de kickoff pendente; escopo que ainda não conta dias")

    # ── 2. Em ambientação ─────────────────────────────────────────────────
    p = c.projeto(
        "02 · Em ambientação",
        status="ambientacao",
        coordenador="Coordenador Tech",
        consultores=["Léo Pinto"],
        frentes=[TECH],
        kickoff=HOJE - timedelta(days=2),
    )
    c.escopo(p, catalogo="Desenvolvimento Tech", frente=TECH, vendidos=12)
    registrar(p.nome, "janela de ambientação correndo; escopo sem reunião inicial")

    # ── 3. Em andamento, tudo no prazo ────────────────────────────────────
    inicio = HOJE - timedelta(days=7)
    p = c.projeto(
        "03 · Em dia",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Nina Rocha", "Théo Braga"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=7),
    )
    e = c.escopo(
        p,
        catalogo="Plano Financeiro",
        frente=BUSINESS,
        vendidos=15,
        inicio=inicio,
        entrega_planejada=d(inicio, 18),
    )
    c.banca(p, [e], quando=datetime.combine(no_prazo(inicio, 15), time(10, 0)),
            frentes=[BUSINESS], coordenador="Ana Souza")
    c.etapas(e, [("Diagnóstico", "#3B82F6", inicio, HOJE - timedelta(days=2))])
    c.reuniao(p, HOJE - timedelta(days=1))
    c.tarefas(p, [
        ("Levantar premissas", "Nina Rocha", HOJE + timedelta(days=3), "em_andamento"),
        ("Validar com o cliente", "Théo Braga", HOJE + timedelta(days=6), "a_fazer"),
    ])
    registrar(p.nome, "caminho feliz: banca marcada dentro da janela, reunião na semana")

    # ── 4. Banca venceu e não aconteceu ───────────────────────────────────
    # Início recente de propósito: a JANELA ainda está aberta, e o único
    # problema é a banca que venceu sem acontecer. Com um início antigo, o
    # escopo apareceria também em "passou da janela" e o cenário deixaria de
    # isolar uma coisa só.
    inicio = HOJE - timedelta(days=14)
    p = c.projeto(
        "04 · Banca atrasada",
        status="em_andamento",
        coordenador="Coordenador Tech",
        consultores=["Vera Luz"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="AI e Automações", frente=TECH, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 16))
    c.banca(p, [e], quando=datetime.combine(HOJE - timedelta(days=6), time(14, 0)),
            frentes=[TECH], coordenador="Coordenador Tech")
    registrar(p.nome, "aba Atrasos: banca vencida sem justificativa; fila de Aprovações")

    # ── 5. Banca atrasada, já justificada pela diretoria ──────────────────
    inicio = HOJE - timedelta(days=16)
    p = c.projeto(
        "05 · Banca atrasada justificada",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Íris Melo"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Plano Operacional", frente=BUSINESS, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 16))
    c.banca(p, [e], quando=datetime.combine(HOJE - timedelta(days=9), time(9, 0)),
            frentes=[BUSINESS], coordenador="Ana Souza")
    c.justificativa_de_atraso(p, e, "Avaliadores não fecharam agenda; remarcada com a diretoria.",
                              tipo="banca")
    registrar(p.nome, "selo 'justificado' no motivo, com link para o Histórico")

    # ── 6. Estourou a janela, banca feita, SEM justificativa ──────────────
    inicio = HOJE - timedelta(days=28)
    p = c.projeto(
        "06 · Estourou a janela",
        status="validacao_bancas",
        coordenador="Coordenador Tech",
        consultores=["mateus loureiro"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=6),
    )
    e = c.escopo(p, catalogo="Análise de Dados", frente=TECH, vendidos=10,
                 inicio=inicio, entrega_planejada=d(inicio, 15))
    # Banca 3 dias úteis DEPOIS do fim da janela: é o atraso do §10.
    banca_em = alem(inicio, 10, 3)
    c.banca(p, [e], quando=datetime.combine(banca_em, time(10, 0)),
            realizada_em=datetime.combine(banca_em, time(11, 30)),
            frentes=[TECH], coordenador="Coordenador Tech")
    registrar(p.nome, "'Escopos que passaram da janela' — ainda sem justificativa")

    # ── 7. Estourou a janela, COM justificativa do coordenador ────────────
    inicio = HOJE - timedelta(days=26)
    p = c.projeto(
        "07 · Estourou e justificou",
        status="validacao_bancas",
        coordenador="Ana Souza",
        consultores=["Nina Rocha"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=6),
    )
    e = c.escopo(p, catalogo="Plano Estratégico de Marketing", frente=BUSINESS, vendidos=9,
                 inicio=inicio, entrega_planejada=d(inicio, 14))
    banca_em = alem(inicio, 9, 3)
    c.banca(p, [e], quando=datetime.combine(banca_em, time(10, 0)),
            realizada_em=datetime.combine(banca_em, time(11, 0)),
            frentes=[BUSINESS], coordenador="Ana Souza")
    c.justificativa_de_atraso(p, e, "O cliente parou de responder por duas semanas e o "
                                    "levantamento travou; retomamos com o escopo já apertado.")
    registrar(p.nome, "mesma seção, com o porquê escrito — compara com o 06")

    # ── 8. Entregue no prazo ──────────────────────────────────────────────
    inicio = HOJE - timedelta(days=45)
    p = c.projeto(
        "08 · Entregue no prazo",
        status="finalizado",
        coordenador="Ana Souza",
        consultores=["Bia Martins"],
        frentes=[DIREITO],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Revisão Contratual", frente=DIREITO, vendidos=10,
                 inicio=inicio, entrega_planejada=d(inicio, 14),
                 entrega_real=d(inicio, 13))
    c.banca(p, [e], quando=datetime.combine(no_prazo(inicio, 10), time(10, 0)),
            realizada_em=datetime.combine(no_prazo(inicio, 10), time(11, 0)),
            frentes=[DIREITO], coordenador="Ana Souza")
    registrar(p.nome, "projeto fechado sem nenhum alerta — o contraste dos demais")

    # ── 9. Entregue com atraso ────────────────────────────────────────────
    inicio = HOJE - timedelta(days=50)
    p = c.projeto(
        "09 · Entregue com atraso",
        status="periodo_ajustes",
        coordenador="Coordenador Tech",
        consultores=["Léo Pinto"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Desenvolvimento Web (Front/Back)", frente=TECH, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 15),
                 entrega_real=d(inicio, 22))
    c.banca(p, [e], quando=datetime.combine(no_prazo(inicio, 12), time(14, 0)),
            realizada_em=datetime.combine(no_prazo(inicio, 12), time(15, 30)),
            frentes=[TECH], coordenador="Coordenador Tech")
    registrar(p.nome, "entrega depois da prevista — Histórico registra o 'de → para'")

    # ── 10/11/12. Os três estados do pedido de dias ───────────────────────
    for rotulo, estado, resposta, dias_ajustados in (
        ("10 · Pedido de dias pendente", "pendente", None, 0),
        ("11 · Pedido de dias aprovado", "aprovado", "Faz sentido, o escopo veio apertado.", 5),
        ("12 · Pedido de dias negado", "rejeitado", "Dá para caber remanejando a equipe.", 0),
    ):
        inicio = HOJE - timedelta(days=4)
        p = c.projeto(
            rotulo,
            status="em_andamento",
            coordenador="Ana Souza",
            consultores=["Théo Braga"],
            frentes=[BUSINESS],
            kickoff=inicio - timedelta(days=5),
        )
        e = c.escopo(p, catalogo="Análise Mercadológica", frente=BUSINESS, vendidos=8,
                     ajustados=dias_ajustados, inicio=inicio,
                     entrega_planejada=d(inicio, 14 + dias_ajustados))
        c.banca(p, [e],
                quando=datetime.combine(no_prazo(inicio, 8 + dias_ajustados), time(10, 0)),
                frentes=[BUSINESS], coordenador="Ana Souza")
        c.pedido_de_dias(e, dias=5, motivo="Os 8 dias vendidos não cobrem a coleta de campo.",
                         status=estado, resposta=resposta)
        registrar(p.nome, {
            "pendente": "aba Aprovações: decidir Aprovar/Negar",
            "aprovado": "janela esticada (+5 ajustados) e decisão no Histórico",
            "rejeitado": "recusa registrada; o coordenador pode pedir de novo",
        }[estado])

    # ── 13. Vão FECHADO entre escopos ─────────────────────────────────────
    # O vão é fixado em 21 dias e ancorado no FIM: o escopo 2 começa há 5
    # dias, então a banca dele ainda está por vir e o projeto não entra na
    # lista de atrasos. Ancorar no início deixaria o escopo 2 velho e a banca
    # dele vencida — o cenário viraria dois problemas em vez de um vão.
    inicio2 = HOJE - timedelta(days=5)
    entrega1 = inicio2 - timedelta(days=21)
    inicio1 = entrega1 - timedelta(days=20)
    p = c.projeto(
        "13 · Vão entre escopos (fechado)",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Íris Melo", "Vera Luz"],
        frentes=[BUSINESS, TECH],
        kickoff=inicio1 - timedelta(days=5),
    )
    e1 = c.escopo(p, catalogo="Plano Financeiro", frente=BUSINESS, vendidos=10, ordem=0,
                  inicio=inicio1, entrega_planejada=entrega1, entrega_real=entrega1)
    c.banca(p, [e1], quando=datetime.combine(no_prazo(inicio1, 10), time(10, 0)),
            realizada_em=datetime.combine(no_prazo(inicio1, 10), time(11, 0)),
            frentes=[BUSINESS], coordenador="Ana Souza")
    e2 = c.escopo(p, catalogo="Desenvolvimento Tech", frente=TECH, vendidos=12, ordem=1,
                  inicio=inicio2, entrega_planejada=d(inicio2, 16))
    c.banca(p, [e2], quando=datetime.combine(no_prazo(inicio2, 12), time(14, 0)),
            frentes=[TECH], coordenador="Ana Souza")
    registrar(p.nome, "card 'Tempo parado entre escopos': vão fechado, medido até a reunião")

    # ── 14. Vão ABERTO entre escopos ──────────────────────────────────────
    inicio1 = HOJE - timedelta(days=40)
    p = c.projeto(
        "14 · Vão entre escopos (aberto)",
        status="em_andamento",
        coordenador="Coordenador Tech",
        consultores=["Ravi Nunes"],
        frentes=[PROCESSOS],
        kickoff=inicio1 - timedelta(days=5),
    )
    e1 = c.escopo(p, catalogo="Simulação e Otimização de Processos", frente=PROCESSOS,
                  vendidos=10, ordem=0, inicio=inicio1,
                  entrega_planejada=d(inicio1, 14), entrega_real=d(inicio1, 14))
    c.banca(p, [e1], quando=datetime.combine(no_prazo(inicio1, 10), time(10, 0)),
            realizada_em=datetime.combine(no_prazo(inicio1, 10), time(11, 0)),
            frentes=[PROCESSOS], coordenador="Coordenador Tech")
    c.escopo(p, catalogo="Simulação e Otimização de Processos", frente=PROCESSOS,
             vendidos=8, ordem=1)  # sem reunião inicial: o vão está correndo
    registrar(p.nome, "mesmo card, vão ABERTO — ninguém começou o próximo escopo")

    # ── 15. Sinérgico, uma banca para dois escopos ────────────────────────
    inicio = HOJE - timedelta(days=5)
    p = c.projeto(
        "15 · Sinérgico (uma banca, dois escopos)",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Nina Rocha", "Léo Pinto"],
        frentes=[BUSINESS, TECH],
        kickoff=inicio - timedelta(days=6),
    )
    e1 = c.escopo(p, catalogo="Análise Mercadológica", frente=BUSINESS, vendidos=12,
                  ordem=0, inicio=inicio, entrega_planejada=d(inicio, 18))
    e2 = c.escopo(p, catalogo="Desenvolvimento Web (Mock-Up)", frente=TECH, vendidos=12,
                  ordem=1, inicio=inicio, entrega_planejada=d(inicio, 18))
    c.banca(p, [e1, e2], quando=datetime.combine(no_prazo(inicio, 12), time(15, 0)),
            frentes=[BUSINESS, TECH], coordenador="Ana Souza")
    registrar(p.nome, "composição por frente (piso 3+2) e 'esta banca também avalia X'")

    # ── 16. Pausado ───────────────────────────────────────────────────────
    inicio = HOJE - timedelta(days=25)
    p = c.projeto(
        "16 · Pausado",
        status="pausado",
        coordenador="Coordenador Tech",
        consultores=["Cléo Antunes"],
        frentes=[DIREITO],
        kickoff=inicio - timedelta(days=5),
    )
    c.escopo(p, catalogo="Planejamento Consultivo Tributário", frente=DIREITO, vendidos=10,
             inicio=inicio, entrega_planejada=d(inicio, 15))
    registrar(p.nome, "dia pausado não consome janela nem vira atraso")

    # ── 17. Escopo "Outro" + quadro de tarefas problemático ───────────────
    inicio = HOJE - timedelta(days=8)
    p = c.projeto(
        "17 · Escopo fora do catálogo",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Sofia Mendes"],
        frentes=[PROCESSOS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, nome_customizado="Mapeamento de Processos Sob Medida", frente=PROCESSOS,
                 vendidos=14, inicio=inicio, entrega_planejada=d(inicio, 18))
    c.banca(p, [e], quando=datetime.combine(no_prazo(inicio, 14), time(10, 0)),
            frentes=[PROCESSOS], coordenador="Ana Souza")
    c.tarefas(p, [
        ("Entrevistar a operação", "Sofia Mendes", HOJE - timedelta(days=5), "em_andamento"),
        ("Desenhar o AS-IS", "Sofia Mendes", HOJE - timedelta(days=2), "a_fazer"),
    ])
    registrar(p.nome, "escopo 'Outro' (nome livre) + duas tarefas VENCIDAS")

    # ── 18. Sem tarefas e sem reunião na semana ───────────────────────────
    inicio = HOJE - timedelta(days=6)
    p = c.projeto(
        "18 · Sem tarefas e sem reunião",
        status="em_andamento",
        coordenador="Coordenador Tech",
        consultores=["Hugo Sá"],
        frentes=[DIREITO],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Elaboração Contratual", frente=DIREITO, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 16))
    c.banca(p, [e], quando=datetime.combine(no_prazo(inicio, 12), time(10, 0)),
            frentes=[DIREITO], coordenador="Coordenador Tech")
    registrar(p.nome, "aba Execução: quadro vazio e nenhuma reunião registrada")

    # ── 19. Banca sem ninguém alocado ─────────────────────────────────────
    inicio = HOJE - timedelta(days=10)
    p = c.projeto(
        "19 · Banca sem alocação",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Bia Martins"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Plano Operacional", frente=BUSINESS, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 16))
    c.banca(p, [e], quando=datetime.combine(no_prazo(inicio, 12), time(10, 0)),
            frentes=[BUSINESS], coordenador="Ana Souza", avaliadores=[])
    registrar(p.nome, "0 de 3 alocados: 'Disponíveis para alocação' e o push automático")

    # ── 20. Correções pós-banca ───────────────────────────────────────────
    inicio = HOJE - timedelta(days=35)
    p = c.projeto(
        "20 · Em correções pós-banca",
        status="periodo_ajustes",
        coordenador="Coordenador Tech",
        consultores=["Vera Luz"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Desenvolvimento Tech", frente=TECH, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 20))
    banca_em = no_prazo(inicio, 12)
    c.banca(p, [e], quando=datetime.combine(banca_em, time(10, 0)),
            realizada_em=datetime.combine(banca_em, time(11, 30)),
            frentes=[TECH], coordenador="Coordenador Tech")
    c.etapas(e, [
        ("Construção", "#3B82F6", inicio, banca_em - timedelta(days=1)),
        ("Correções da banca", "#F59E0B", banca_em + timedelta(days=1), HOJE - timedelta(days=1)),
    ])
    registrar(p.nome, "coluna Correções (§11): dias pintados depois da banca não consomem janela")

    db.commit()
    return resumo


def main():
    db = SessionLocal()
    try:
        print(f"Referência: {HOJE}\n")

        apagados = limpar(db)
        print("── APAGADO ──")
        for tabela, n in apagados.items():
            print(f"  {tabela}: {n}")

        mundo = Mundo(db)
        novas = criar_pessoas(db, mundo)
        if novas:
            print(f"\n── PESSOAS CRIADAS ({len(novas)}) ──")
            print("  " + ", ".join(novas))

        mundo = Mundo(db)  # recarrega com a gente nova
        resumo = povoar(db, mundo)

        print(f"\n── PROJETOS CRIADOS ({len(resumo)}) ──")
        for nome, o_que in resumo:
            print(f"  {nome}\n      → {o_que}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

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
from zoneinfo import ZoneInfo

from src.database.database import SessionLocal
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_frente_model import BancaFrenteModel
from src.models.banca_model import BancaModel
from src.models.banca_sessao_model import BancaSessaoModel
from src.models.avaliacao_model import AvaliacaoModel
from src.models.avaliacao_nota_model import AvaliacaoNotaModel
from src.models.pergunta_model import PerguntaModel
from src.models.banca_excecao_choque_model import BancaExcecaoChoqueModel
from src.models.banca_fora_janela_solicitacao_model import (
    BancaForaJanelaSolicitacaoModel,
)
from src.models.candidatura_model import CandidaturaModel
from src.models.formulario_model import FormularioModel
from src.models.banca_remarcacao_model import BancaRemarcacaoModel
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
from src.utils.dias_uteis import proximo_dia_util, somar_dias_uteis
from src.utils.senha import hash_senha

#: A data de referência do cenário. Tudo é posicionado em relação a ela, para
#: os alertas ("venceu há N dias") caírem onde se espera ao abrir a tela hoje.
HOJE = date(2026, 8, 12)

#: ⚠ **A plataforma grava HORÁRIO EM UTC.** O front converte a hora escolhida
#: na tela com `new Date(...).toISOString()` antes de mandar, e é esse instante
#: que chega ao banco: uma banca marcada às 16:00 no Brasil fica `19:00` na
#: coluna. Verificado no caminho real (`PUT /escopos-projeto/{id}/banca`).
#:
#: O seed precisa gravar do mesmo jeito. Gravando hora local crua, toda banca
#: semeada aparecia TRÊS HORAS mais cedo na tela — 14:00 virava 11:00 — e os
#: cenários mentiam sobre o que a plataforma produz.
FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")


def instante(dia, hora, minuto=0):
    """A hora que se quer VER na tela, convertida para o UTC que o banco guarda.

    `instante(HOJE, 14)` é "14h no Brasil" — e devolve o naive UTC equivalente,
    que é exatamente o que o front produz ao mandar a mesma escolha.
    """
    local = datetime.combine(dia, time(hora, minuto), tzinfo=FUSO_LOCAL)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

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
    # ⚠ Antes de `banca` E de `projeto_escopo`: o pedido de exceção aponta para
    # os dois, e só a FK para `banca` é SET NULL — a de `projeto_escopo` é
    # restritiva e faria o delete estourar no meio da limpeza.
    "banca_excecao_choque_solicitacao",
    # ⚠ Faltava, e pela mesma razão: `banca_fora_janela_solicitacao` tem a
    # mesma FK restritiva para `projeto_escopo`. Enquanto nenhum cenário criava
    # um pedido destes a ausência não aparecia — bastava o primeiro para o seed
    # passar a estourar na limpeza, num erro de FK sem relação óbvia com o
    # cenário que o causou.
    "banca_fora_janela_solicitacao",
    # Antes de `banca`. A FK é CASCADE, mas a limpeza é por DELETE explícito e
    # a contagem impressa no fim só existe para quem está na lista.
    "banca_sessao",
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
    # ⚠ Faltava, e os cenários de Tech morriam com `KeyError: 'Coordenador
    # Tech'` — 12 projetos o citam como coordenador e nenhum passo o criava. O
    # seed só rodava em base que já tivesse essa pessoa de outro lugar, o que
    # é o oposto do que um seed existe para fazer.
    ("Coordenador Tech", "coord.tech@al.insper.edu.br", "coordenador", TECH),
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

    def util(self, dia):
        """O próprio dia, se for útil; senão o próximo útil.

        ⚠ Os cenários posicionam datas com `HOJE - timedelta(days=N)`, que cai
        em sábado ou domingo com frequência. Uma reunião inicial no fim de
        semana não é só feia: ela é o "dia 1" da janela do escopo, e
        `somar_dias_uteis` começa a contar do próximo dia útil — o dia 1 some e
        toda a janela do cenário fica deslocada em relação ao que ele quer
        demonstrar.
        """
        return proximo_dia_util(dia, self.nao_letivos)

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
    """Apaga o dado de projeto, na ordem que respeita as FKs.

    ⚠ **Sem SQL preso a um dialeto.** Este bloco nasceu em MySQL e usava
    `database()` e crase para citar identificador — nenhum dos dois existe no
    Postgres, que é onde a plataforma roda de verdade. O seed morria na
    primeira tabela com "function database() does not exist", então o arquivo
    inteiro nunca tinha sido exercido contra o banco de produção.

    `inspect` responde "esta tabela existe?" pelo dialeto certo, e o
    `identifier_preparer` cita o nome do jeito de cada banco (crase no MySQL,
    aspas no Postgres) — o mesmo script serve aos dois.
    """
    from sqlalchemy import inspect, text

    bind = db.get_bind()
    existentes = set(inspect(bind).get_table_names())
    citar = bind.dialect.identifier_preparer.quote

    apagados = {}
    for tabela in TABELAS_A_LIMPAR:
        if tabela not in existentes:
            continue
        nome = citar(tabela)
        n = db.execute(text(f"select count(*) from {nome}")).scalar()
        if n:
            db.execute(text(f"delete from {nome}"))
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
        entrega_prevista_cliente=None,
    ):
        p = ProjetoModel(
            nome=nome,
            cliente=cliente,
            status=status,
            dias_ambientacao=dias_ambientacao,
            data_kickoff=kickoff,
            # ⭐ A PROMESSA feita ao cliente, ao lado do fato. É a diferença
            # entre as duas que responde "entregamos no prazo?" no nível do
            # projeto — e é ela que o cronograma marca. Deixá-la nula em todos
            # os cenários fazia o marcador nunca aparecer na tela.
            data_entrega_prevista_cliente=(
                entrega_prevista_cliente
                if entrega_prevista_cliente is not None
                # Default derivado do kickoff: uma promessa plausível para os
                # cenários que não têm opinião sobre ela.
                else (self.mundo.dia_util(kickoff, 30) if kickoff else None)
            ),
            dia_reuniao_padrao=dia_reuniao,
            criado_por=self.mundo.usuarios["Dani Alves"].id,
            criado_em=instante(criado_em or (kickoff or HOJE), 9, 0),
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
        quando = instante(projeto.data_kickoff or HOJE, 9, 0)
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

        # Sempre em dia útil: é a reunião inicial que abre a janela (§5.4), e
        # ela precisa existir no calendário para o "dia 1" da contagem existir.
        if inicio:
            inicio = self.mundo.util(inicio)

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
        resultado=None,
        votos=None,
    ):
        """A banca do escopo, com a SESSÃO 1 e, se houver, os votos.

        ⭐ **A sessão nasce junto, sempre** — é o que `MarcarBancaEscopoUseCase`
        faz ao criar a banca. Sem ela, o histórico do projeto e a apuração
        veriam uma banca sem nenhuma tentativa registrada, e a segunda banca não
        teria de onde partir.

        `votos` é uma lista de `True`/`False` casada por posição com os
        avaliadores escalados — `[True, True, False]` são dois a favor e um
        contra. Menos votos que avaliadores é de propósito nos cenários de
        quórum parcial; `None` é "ninguém votou".

        ⚠ `resultado` é passado à mão, e não derivado dos votos, porque os dois
        precisam poder DIVERGIR: o cenário do override da diretoria é
        justamente uma banca com resultado e sem voto nenhum.
        """
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
            resultado=resultado,
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
                    criado_em=instante(HOJE - timedelta(days=7), 10, 0),
                    confirmado=bool(realizada_em) and confirmados,
                )
            )

        self.db.add(
            BancaSessaoModel(
                banca_id=b.id,
                numero=1,
                data_hora=quando,
                realizado_em=realizada_em,
                resultado=resultado,
                # Encerra só quando há veredito: sessão realizada e ainda sem
                # resultado continua sendo a CORRENTE, e é ela que a apuração
                # procura quando um voto atrasado chega.
                encerrada_em=(
                    instante(HOJE, 9, 0) if resultado else None
                ),
            )
        )
        self.db.flush()

        if votos:
            self.votos(b, escalados, votos, sessao=1)
        return b

    def votos(self, banca, escalados, votos, *, sessao=1):
        """Avaliações submetidas, com o voto que decide a banca (§8).

        Cada voto é uma linha de `avaliacao` com `voto_aprovacao` e o carimbo da
        sessão — é assim que a apuração separa a 1ª banca da 2ª.
        """
        formulario = self.db.query(FormularioModel).filter_by(ativo=True).first()
        if not formulario:
            formulario = self.db.query(FormularioModel).first()
        if not formulario:
            return
        # As perguntas que valem para o escopo desta banca: as do catálogo dele
        # mais as GERAIS (escopo_id nulo), que valem para qualquer banca.
        perguntas = [
            q
            for q in self.db.query(PerguntaModel)
            .filter_by(formulario_id=formulario.id)
            .order_by(PerguntaModel.ordem)
            .all()
            if q.escopo_id is None or q.escopo_id == banca.escopo_id
        ]

        quando = (banca.realizado_em or instante(HOJE, 10, 0)) + timedelta(hours=2)
        for usuario, voto in zip(escalados, votos):
            self.db.add(
                AvaliacaoModel(
                    banca_id=banca.id,
                    avaliador_id=usuario.id,
                    formulario_id=formulario.id,
                    sessao=sessao,
                    status="submetida",
                    submetida_em=quando,
                    voto_aprovacao=voto,
                    nome_avaliador=usuario.nome,
                    tipo_avaliador="consultor" if usuario.posicao == "consultor" else "lideranca",
                    projeto_avaliado=banca.nome_projeto,
                )
            )
            self.db.flush()
            self._notas(self.db.query(AvaliacaoModel).order_by(AvaliacaoModel.id.desc()).first(),
                        perguntas, voto)
        self.db.flush()

    def _notas(self, avaliacao, perguntas, voto):
        """As notas por critério, coerentes com o voto.

        ⭐ Sem elas a avaliação fica só com o veredito, e a tela que abre "o que
        esta pessoa respondeu" não tem o que mostrar — o recurso existiria sem
        dado para exercitá-lo.

        Quem aprovou dá notas altas, quem reprovou dá baixas: notas aleatórias
        contradiriam o voto e fariam o cenário mentir sobre a relação entre as
        duas dimensões (a nota mede QUÃO BEM, o voto decide se vai ao cliente).
        """
        altas = [5, 4, 5, 4, 4]
        baixas = [2, 3, 2, 2, 3]
        escala = altas if voto else baixas
        for i, pergunta in enumerate(perguntas):
            self.db.add(
                AvaliacaoNotaModel(
                    avaliacao_id=avaliacao.id,
                    pergunta_id=pergunta.id,
                    nota=escala[i % len(escala)],
                )
            )

    def segunda_banca(self, banca, *, quando, realizada_em=None, resultado=None, votos=None):
        """⭐ A 2ª banca do escopo — a primeira reprovou (§9).

        ⚠ **Não é uma banca nova.** Continua a MESMA linha de `banca` (é uma por
        escopo, o UNIQUE permanece); o que muda é a sessão. A sessão anterior
        fecha guardando `realizado_em` e `resultado='nao_aprovada'`, e a linha
        da banca é reapontada para a data nova com os campos limpos — que é
        exatamente o que `_sincronizar_sessao` + `_campos_da_remarcacao` fazem.

        Sem este arquivamento, a reprovação sumiria e ninguém conseguiria
        responder "por que este escopo teve duas bancas?".
        """
        corrente = (
            self.db.query(BancaSessaoModel)
            .filter_by(banca_id=banca.id, encerrada_em=None)
            .order_by(BancaSessaoModel.numero.desc())
            .first()
        )
        proximo = 2
        if corrente:
            corrente.encerrada_em = instante(HOJE - timedelta(days=1), 9, 0)
            proximo = corrente.numero + 1

        banca.data_hora = quando
        banca.realizado_em = realizada_em
        banca.resultado = resultado

        self.db.add(
            BancaSessaoModel(
                banca_id=banca.id,
                numero=proximo,
                data_hora=quando,
                realizado_em=realizada_em,
                resultado=resultado,
                encerrada_em=(
                    instante(HOJE, 9, 0) if resultado else None
                ),
            )
        )
        self.db.add(
            BancaRemarcacaoModel(
                banca_id=banca.id,
                data_anterior=corrente.data_hora if corrente else quando,
                data_nova=quando,
                justificativa="Segunda banca — a anterior foi reprovada",
                remarcado_por=banca.coordenador_id,
            )
        )
        self.db.flush()

        if votos:
            escalados = [
                self.db.get(UsuarioModel, cand.usuario_id)
                for cand in self.db.query(CandidaturaModel).filter_by(banca_id=banca.id)
            ]
            self.votos(banca, escalados, votos, sessao=proximo)
        return banca

    def excecao_de_choque(
        self, escopo, banca_conflitante, *, quando, justificativa, status="pendente", resposta=None
    ):
        """§8: o pedido para marcar banca num horário já ocupado."""
        self.db.add(
            BancaExcecaoChoqueModel(
                projeto_escopo_id=escopo.id,
                banca_id=None,
                data_hora_pretendida=quando,
                banca_conflitante_id=banca_conflitante.id,
                justificativa=justificativa,
                status=status,
                solicitado_por=self.mundo.usuarios["Ana Souza"].id,
                respondido_por=(
                    self.mundo.usuarios["Dani Alves"].id if status != "pendente" else None
                ),
                resposta=resposta,
                criado_em=instante(HOJE - timedelta(days=2), 14, 0),
                respondido_em=(
                    instante(HOJE - timedelta(days=1), 10, 0)
                    if status != "pendente"
                    else None
                ),
            )
        )
        self.db.flush()

    def pedido_fora_da_janela(
        self, escopo, *, quando, justificativa, status="pendente", resposta=None
    ):
        """§13: o pedido para marcar banca depois do fim da janela do escopo."""
        self.db.add(
            BancaForaJanelaSolicitacaoModel(
                projeto_escopo_id=escopo.id,
                # Nulo de propósito: o gate roda ANTES de a banca existir, e é
                # a aprovação que a cria. Ver `_marcar_a_banca`.
                banca_id=None,
                data_hora_pretendida=quando,
                justificativa=justificativa,
                status=status,
                solicitado_por=self.mundo.usuarios["Ana Souza"].id,
                respondido_por=(
                    self.mundo.usuarios["Dani Alves"].id if status != "pendente" else None
                ),
                resposta=resposta,
                criado_em=instante(HOJE - timedelta(days=1), 9, 0),
                respondido_em=(
                    instante(HOJE, 10, 0) if status != "pendente" else None
                ),
            )
        )
        self.db.flush()

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
                criado_em=instante(quando or (HOJE - timedelta(days=3)), 11, 0),
                respondido_em=(
                    instante(HOJE - timedelta(days=2), 15, 0)
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
                registrado_em=instante(HOJE - timedelta(days=1), 16, 0),
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
    c.banca(p, [e], quando=instante(no_prazo(inicio, 15), 10, 0),
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
    c.banca(p, [e], quando=instante(HOJE - timedelta(days=6), 14, 0),
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
    c.banca(p, [e], quando=instante(HOJE - timedelta(days=9), 9, 0),
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
        # Era "mateus loureiro" — um nome que sobrou de base real e não
        # existia em pessoa nenhuma do seed. Trocado por um consultor de Tech
        # que o próprio seed cria.
        consultores=["Caio Ferreira"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=6),
    )
    e = c.escopo(p, catalogo="Análise de Dados", frente=TECH, vendidos=10,
                 inicio=inicio, entrega_planejada=d(inicio, 15))
    # Banca 3 dias úteis DEPOIS do fim da janela: é o atraso do §10.
    banca_em = alem(inicio, 10, 3)
    c.banca(p, [e], quando=instante(banca_em, 10, 0),
            realizada_em=instante(banca_em, 11, 30),
            frentes=[TECH], coordenador="Coordenador Tech",
            # Unanimidade: entrega liberada, o atraso é só da janela.
            resultado="aprovada", votos=[True, True])
    registrar(p.nome, "'Escopos que passaram da janela' — ainda sem justificativa; "
                      "banca aprovada por unanimidade libera a entrega")

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
    c.banca(p, [e], quando=instante(banca_em, 10, 0),
            realizada_em=instante(banca_em, 11, 0),
            frentes=[BUSINESS], coordenador="Ana Souza",
            resultado="aprovada", votos=[True, True, True])
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
    c.banca(p, [e], quando=instante(no_prazo(inicio, 10), 10, 0),
            realizada_em=instante(no_prazo(inicio, 10), 11, 0),
            frentes=[DIREITO], coordenador="Ana Souza",
            resultado="aprovada", votos=[True, True, True])
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
    c.banca(p, [e], quando=instante(no_prazo(inicio, 12), 14, 0),
            realizada_em=instante(no_prazo(inicio, 12), 15, 30),
            frentes=[TECH], coordenador="Coordenador Tech",
            resultado="aprovada", votos=[True, True, True])
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
                quando=instante(no_prazo(inicio, 8 + dias_ajustados), 10, 0),
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
    # Maioria, não unanimidade: um avaliador votou contra e a banca passou.
    c.banca(p, [e1], quando=instante(no_prazo(inicio1, 10), 10, 0),
            realizada_em=instante(no_prazo(inicio1, 10), 11, 0),
            frentes=[BUSINESS], coordenador="Ana Souza",
            resultado="aprovada", votos=[True, True, False])
    e2 = c.escopo(p, catalogo="Desenvolvimento Tech", frente=TECH, vendidos=12, ordem=1,
                  inicio=inicio2, entrega_planejada=d(inicio2, 16))
    c.banca(p, [e2], quando=instante(no_prazo(inicio2, 12), 14, 0),
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
    c.banca(p, [e1], quando=instante(no_prazo(inicio1, 10), 10, 0),
            realizada_em=instante(no_prazo(inicio1, 10), 11, 0),
            frentes=[PROCESSOS], coordenador="Coordenador Tech",
            resultado="aprovada", votos=[True, True, True])
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
    c.banca(p, [e1, e2], quando=instante(no_prazo(inicio, 12), 15, 0),
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
    c.banca(p, [e], quando=instante(no_prazo(inicio, 14), 10, 0),
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
    c.banca(p, [e], quando=instante(no_prazo(inicio, 12), 10, 0),
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
    c.banca(p, [e], quando=instante(no_prazo(inicio, 12), 10, 0),
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
    c.banca(p, [e], quando=instante(banca_em, 10, 0),
            realizada_em=instante(banca_em, 11, 30),
            frentes=[TECH], coordenador="Coordenador Tech")
    c.etapas(e, [
        ("Construção", "#3B82F6", inicio, banca_em - timedelta(days=1)),
        ("Correções da banca", "#F59E0B", banca_em + timedelta(days=1), HOJE - timedelta(days=1)),
    ])
    registrar(p.nome, "coluna Correções (§11): dias pintados depois da banca não consomem janela; "
                      "banca sem voto nenhum e prazo vencido → override da diretoria")

    # ══════════════════════════════════════════════════════════════════════
    # Daqui para baixo: os cenários da REFORMA DAS BANCAS — sessões, voto,
    # trava da entrega pelo resultado e exceção de choque.
    # ══════════════════════════════════════════════════════════════════════

    # ── 21. Reprovada, 2ª banca MARCADA e ainda por acontecer ─────────────
    #
    # ⭐ O cenário central da reforma. A 1ª banca reprovou; a sessão 1 guarda a
    # reprovação e a sessão 2 está aberta, esperando a data nova. A entrega
    # continua travada — e a mensagem tem de dizer "marque uma nova banca".
    inicio = HOJE - timedelta(days=30)
    p = c.projeto(
        "21 · Reprovada, 2ª banca marcada",
        status="validacao_bancas",
        coordenador="Ana Souza",
        consultores=["Nina Rocha", "Théo Braga"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Plano Operacional", frente=BUSINESS, vendidos=12,
                 inicio=inicio, entrega_planejada=d(inicio, 18))
    primeira = no_prazo(inicio, 12)
    b = c.banca(p, [e], quando=instante(primeira, 10, 0),
                realizada_em=instante(primeira, 11, 30),
                frentes=[BUSINESS], coordenador="Ana Souza",
                resultado="nao_aprovada", votos=[False, False, True])
    c.segunda_banca(b, quando=instante(HOJE + timedelta(days=4), 14, 0))
    c.etapas(e, [("Construção", "#3B82F6", inicio, primeira - timedelta(days=1))])
    registrar(p.nome, "sessões: histórico mostra a 1ª REPROVADA e a 2ª marcada; "
                      "entrega travada com 'é preciso marcar uma nova banca'")

    # ── 22. Reprovada por EMPATE ──────────────────────────────────────────
    #
    # ⚠ A borda que é uma DECISÃO, não um acidente: 1×1 não é "meio aprovado".
    # O resultado é um gate que abre a entrega ao cliente, e o default seguro
    # de um gate é fechado.
    inicio = HOJE - timedelta(days=26)
    p = c.projeto(
        "22 · Reprovada por empate",
        status="validacao_bancas",
        coordenador="Coordenador Tech",
        consultores=["Léo Pinto"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="AI e Automações", frente=TECH, vendidos=10,
                 inicio=inicio, entrega_planejada=d(inicio, 15))
    banca_em = no_prazo(inicio, 10)
    c.banca(p, [e], quando=instante(banca_em, 9, 0),
            realizada_em=instante(banca_em, 10, 30),
            frentes=[TECH], coordenador="Coordenador Tech",
            resultado="nao_aprovada", votos=[True, False])
    registrar(p.nome, "empate (1×1) reprova; a entrega segue travada")

    # ── 23. 2ª banca já realizada e APROVADA ──────────────────────────────
    #
    # O desfecho do 21: duas sessões, a 1ª arquivada com a reprovação e a 2ª
    # aprovada. O escopo pôde ser entregue. É a prova de que a segunda chance
    # existe e de que a reprovação não se perde no caminho.
    inicio = HOJE - timedelta(days=45)
    p = c.projeto(
        "23 · Reprovou, refez e aprovou",
        status="finalizado",
        coordenador="Ana Souza",
        consultores=["Íris Melo"],
        frentes=[DIREITO],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Revisão Contratual", frente=DIREITO, vendidos=10,
                 inicio=inicio, entrega_planejada=d(inicio, 15),
                 entrega_real=d(inicio, 20))
    primeira = no_prazo(inicio, 10)
    b = c.banca(p, [e], quando=instante(primeira, 10, 0),
                realizada_em=instante(primeira, 11, 0),
                frentes=[DIREITO], coordenador="Ana Souza",
                resultado="nao_aprovada", votos=[False, False, True])
    segunda = d(primeira, 6)
    c.segunda_banca(b, quando=instante(segunda, 10, 0),
                    realizada_em=instante(segunda, 11, 0),
                    resultado="aprovada", votos=[True, True, True])
    registrar(p.nome, "duas sessões no histórico: 1ª reprovada, 2ª aprovada — "
                      "e a entrega liberada só depois da segunda")

    # ── 24/25. Choque de horário: pedido PENDENTE e exceção APROVADA ──────
    #
    # ⚠ Os dois projetos abaixo marcam banca no MESMO horário de propósito —
    # é o que faz o calendário de bancas acender o aviso de choque e o que dá
    # sentido ao pedido de exceção. Um pedido fica pendente na fila da
    # diretoria; o outro já foi liberado.
    #
    # ⚠ O horário precisa caber na JANELA dos três escopos envolvidos. O gate
    # da janela (§9) roda ANTES da checagem de choque: com a data fora dela, a
    # recusa que volta é "fora da janela" e o cenário do choque nunca é
    # exercido — foi exatamente o que aconteceu na primeira montagem.
    # Por isso os três começam juntos e com janela folgada.
    inicio_do_choque = HOJE - timedelta(days=5)
    horario_disputado = instante(d(HOJE, 3), 15, 0)

    inicio = inicio_do_choque
    p_ocupa = c.projeto(
        "24 · Ocupa o horário disputado",
        status="em_andamento",
        coordenador="Coordenador Tech",
        consultores=["Vera Luz"],
        frentes=[TECH],
        kickoff=inicio - timedelta(days=5),
    )
    e_ocupa = c.escopo(p_ocupa, catalogo="Desenvolvimento Web (Mock-Up)", frente=TECH,
                       vendidos=20, inicio=inicio, entrega_planejada=d(inicio, 24))
    b_ocupa = c.banca(p_ocupa, [e_ocupa], quando=horario_disputado,
                      frentes=[TECH], coordenador="Coordenador Tech")
    registrar(p_ocupa.nome, "a banca que já está no horário — o outro lado do choque")

    inicio = inicio_do_choque
    p = c.projeto(
        "25 · Pediu exceção de choque",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Hugo Sá"],
        frentes=[DIREITO],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Planejamento Consultivo Tributário", frente=DIREITO,
                 vendidos=20, inicio=inicio, entrega_planejada=d(inicio, 24))
    c.excecao_de_choque(e, b_ocupa, quando=horario_disputado,
                        justificativa="É a única data em que o cliente e os dois sócios "
                                      "conseguem estar presentes.")
    registrar(p.nome, "fila 'Exceções de choque' na aba Aprovações — pedido PENDENTE")

    inicio = inicio_do_choque
    p = c.projeto(
        "26 · Exceção de choque já liberada",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Ravi Nunes"],
        frentes=[PROCESSOS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Simulação e Otimização de Processos", frente=PROCESSOS,
                 vendidos=20, inicio=inicio, entrega_planejada=d(inicio, 24))
    c.excecao_de_choque(e, b_ocupa, quando=horario_disputado,
                        justificativa="Bancas em salas diferentes, sem avaliador em comum.",
                        status="aprovada",
                        resposta="Liberado: salas e avaliadores distintos, sem prejuízo.")
    # ⭐ E a banca DE FATO marcada no horário disputado — é a exceção aprovada
    # sendo exercida. Sem esta linha o cenário ficaria pela metade: o aviso de
    # choque do calendário de bancas só acende com DUAS bancas no mesmo
    # horário, e teria ficado invisível justamente no cenário criado para ele.
    c.banca(p, [e], quando=horario_disputado,
            frentes=[PROCESSOS], coordenador="Ana Souza")
    registrar(p.nome, "exceção APROVADA e exercida: duas bancas no mesmo horário — "
                      "o calendário de bancas acende o aviso de choque")

    # ── 27. Banca de ontem, votação em ANDAMENTO ──────────────────────────
    #
    # ⭐ O único estado "aguardando" honesto: a banca aconteceu ontem, o prazo
    # de 2 dias está aberto e 2 de 3 já votaram. A apuração NÃO decide aqui de
    # propósito — 2×0 com um voto por vir pode virar 2×2, e decidir agora seria
    # decidir com meia urna.
    #
    # ⚠ Precisa ser recente. Nos cenários de banca antiga o prazo já venceu, e
    # aí o job diário fecha com quem votou — o "aguardando" não sobreviveria à
    # primeira execução das 6h45.
    inicio = HOJE - timedelta(days=14)
    p = c.projeto(
        "27 · Votação da banca em andamento",
        status="validacao_bancas",
        coordenador="Ana Souza",
        consultores=["Nina Rocha"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Análise Mercadológica", frente=BUSINESS, vendidos=14,
                 inicio=inicio, entrega_planejada=d(inicio, 18))
    ontem = HOJE - timedelta(days=1)
    c.banca(p, [e], quando=instante(ontem, 10, 0),
            realizada_em=instante(ontem, 11, 30),
            frentes=[BUSINESS], coordenador="Ana Souza",
            votos=[True, True])
    registrar(p.nome, "2 de 3 votaram e o prazo está aberto: entrega travada com "
                      "'aguardando o voto dos avaliadores'; o 3º ainda é cobrado")

    # ── 28. Fora da janela E em cima de outra banca ───────────────────────
    #
    # ⭐ **O cenário que faltava, e que custou uma decisão travada em
    # produção.** É o cruzamento de duas regras que sempre foram tratadas
    # separadamente: o pedido do §13 (data depois do fim da janela) cuja data
    # também esbarra na banca de outro projeto (§8).
    #
    # Autorizar falhava com "peça uma exceção de choque à diretoria" — dito a
    # QUEM É a diretoria, numa fila sem botão nenhum para conceder. O pedido
    # voltava para pendente e a única saída visível era negar um pedido
    # legítimo. A saída agora é o segundo clique da tela, "Autorizar o choque
    # também e marcar", que grava a exceção do §8 antes de marcar a banca.
    #
    # ⚠ **Reusa `b_ocupa` do cenário 24 de propósito**: uma banca trava
    # quantos pedidos caírem no horário dela, e é assim que o choque aparece
    # na vida real. O que separa este cenário dos 25 e 26 é a JANELA — a deste
    # escopo fecha bem antes do horário disputado, e é isso que faz o pedido
    # ser de fora da janela em vez de exceção de choque pura.
    inicio = HOJE - timedelta(days=40)
    p = c.projeto(
        "28 · Fora da janela e em cima de outra banca",
        status="em_andamento",
        coordenador="Ana Souza",
        consultores=["Hugo Sá"],
        frentes=[BUSINESS],
        kickoff=inicio - timedelta(days=5),
    )
    e = c.escopo(p, catalogo="Análise Mercadológica", frente=BUSINESS, vendidos=10,
                 inicio=inicio, entrega_planejada=d(inicio, 14))
    c.pedido_fora_da_janela(
        e,
        quando=horario_disputado,
        justificativa="Cronograma estabelecido com o comercial e acordado com o cliente.",
    )
    registrar(p.nome, "fila 'Bancas fora da janela' na aba Aprovações — 'Autorizar e "
                      "marcar' esbarra no choque com o cenário 24 e oferece "
                      "'Autorizar o choque também e marcar'")

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

"""⭐ §9 e §13: a banca dentro da janela, e os dois gates de remarcação.

**Este é o único bloqueio duro do cronograma.** Pintar etapa além da janela é
livre e só avisa (§15); marcar banca fora dela não passa sem a diretoria. A
assimetria é proposital: etapa é planejamento, banca tem avaliadores escalados
e uma data que o cliente e o núcleo reservaram.

Três regras que estes testes prendem:

- **Sem reunião inicial não há banca** (§20.4). É o INVERSO da trava antiga,
  que exigia a banca antes da reunião inicial.
- **Fora da janela é decisão da diretoria**, com justificativa — e os dias além
  dela viram atraso sozinhos, sem ninguém conceder nada.
- **Remarcar em cima da hora exige diretoria**, mesmo dentro da janela: os
  avaliadores já reservaram a agenda.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch` —
mesmo idioma de `test_destinatarios_notificacao.py`.
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.banca import fora_janela, marcar_banca_escopo
from src.use_cases.banca.marcar_banca_escopo import (
    MarcarBancaEscopoRequest,
    MarcarBancaEscopoUseCase,
)
from src.utils.dias_uteis import somar_dias_uteis
from src.utils.exceptions import RegraDeNegocioError

CALENDARIO = [date(2026, 9, 7)]  # feriado da Independência

QUI_03_09 = date(2026, 9, 3)  # a reunião inicial
DENTRO = datetime(2026, 9, 25, 14, 0)  # 15º dia útil — dentro dos 20 vendidos
FORA = datetime(2026, 10, 20, 14, 0)  # bem depois do fim da janela

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


def escopo(id=7, inicio=QUI_03_09, vendidos=20, ajustados=0):
    return SimpleNamespace(
        id=id,
        projeto_id=3,
        escopo_id=None,
        frente_id=1,
        nome_customizado="Elaboração Contratual",
        data_inicio=inicio,
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
    )


@pytest.fixture
def marcar(monkeypatch):
    """Devolve `(executar, estado)`; `estado.remarcacoes` mostra o registrado."""

    def _montar(alvo=None, *, banca_existente=None, escopos_extras=(), fora_janela_aprovada=None):
        alvo = alvo if alvo is not None else escopo()
        estado = SimpleNamespace(
            sessoes=[],remarcacoes=[], bancas=[], notificou=False)
        todos = {e.id: e for e in (alvo, *escopos_extras)}
        # `(projeto_escopo_id, data_hora)` já autorizados pela diretoria —
        # mesma régua de `BancaForaJanelaRepository.get_aprovada`.
        aprovadas = set(fora_janela_aprovada or [])

        class ForaJanelaFake:
            def __init__(self, db): pass
            def get_aprovada(self, escopo_id, data_hora):
                return SimpleNamespace(id=1) if (escopo_id, data_hora) in aprovadas else None

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, _id): return banca_existente
            # Recarrega a linha depois da apuração: é a mesma instância aqui,
            # mas o use case precisa enxergar o veredito que acabou de nascer
            # antes de julgar se a 2ª banca pode existir.
            def get_by_id(self, _id): return banca_existente
            def get_por_data_hora(self, _dh): return []
            def update(self, _id, **campos):
                for k, v in campos.items():
                    setattr(banca_existente, k, v)
                return banca_existente
            def create(self, **campos):
                # `coordenador_id` vem em `campos` — o use case o resolve a
                # partir da equipe antes de criar.
                nova = SimpleNamespace(id=50, realizado_em=None, **campos)
                estado.bancas.append(nova)
                return nova

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return todos.get(_id)

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id):
                return SimpleNamespace(id=3, nome="Projeto Alfa")

        class MembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id, apenas_atuais=False):
                return [SimpleNamespace(usuario_id=ANA.id, papel="coordenador")]

        class BancaFrenteFake:
            def __init__(self, db): pass
            def get_by_banca(self, _id): return []
            def create(self, **campos): pass

        class BancaEscopoFake:
            def __init__(self, db): pass
            def get_escopo_ids(self, _id): return []
            def get_banca_id(self, _id): return None
            def definir(self, banca_id, escopo_ids): pass

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None

        class SessaoFake:
            """As sessões da banca (§9) — cada tentativa.

            Guarda em `estado.sessoes` para os testes afirmarem que a
            reprovação da sessão anterior foi ARQUIVADA antes de a linha de
            `banca` ser limpa.
            """

            def __init__(self, db): pass

            def get_corrente(self, banca_id):
                abertas = [
                    s for s in estado.sessoes
                    if s.banca_id == banca_id and s.encerrada_em is None
                ]
                return abertas[-1] if abertas else None

            def proximo_numero(self, banca_id):
                return len([s for s in estado.sessoes if s.banca_id == banca_id]) + 1

            def create(self, **campos):
                sessao = SimpleNamespace(
                    id=len(estado.sessoes) + 1,
                    realizado_em=None,
                    resultado=None,
                    encerrada_em=None,
                    **campos,
                )
                estado.sessoes.append(sessao)
                return sessao

            def update(self, sessao_id, **campos):
                alvo = next(s for s in estado.sessoes if s.id == sessao_id)
                for chave, valor in campos.items():
                    setattr(alvo, chave, valor)
                return alvo

        class RemarcacaoFake:
            def __init__(self, db): pass
            def create(self, **campos):
                estado.remarcacoes.append(campos)
                return SimpleNamespace(id=1, **campos)

        class RemarcacaoProjetoFake:
            """A OUTRA tabela de remarcação.

            `banca_remarcacao` e `projeto_remarcacao_banca` nasceram em paralelo
            em branches diferentes, para o mesmo evento, e cada uma guarda uma
            coluna que a outra não tem. As duas continuam sendo escritas para
            nenhum dos dois lados perder função — o histórico deduplica na
            leitura. Aqui basta o dublê não estourar; quem os testes verificam é
            `estado.remarcacoes`, alimentado pela outra.
            """

            def __init__(self, db): pass
            def create(self, **campos):
                return SimpleNamespace(id=1, **campos)

        class DiaNaoLetivoFake:
            def __init__(self, db): pass
            def get_all(self):
                return [SimpleNamespace(data=d) for d in CALENDARIO]

        class HistoricoFake:
            """Projeto que nunca foi pausado — a janela não desloca.

            A pausa que empurra o fim da janela tem teste próprio em
            `tests/utils/test_janela_escopo.py`; aqui ela só precisa não
            existir, para as datas de `DENTRO`/`FORA` continuarem valendo.
            """

            def __init__(self, db): pass
            def get_by_projeto(self, _id): return []

        for nome, fake in [
            ("BancaRepository", BancaFake),
            ("ProjetoEscopoRepository", EscopoProjetoFake),
            ("ProjetoRepository", ProjetoFake),
            ("ProjetoMembroRepository", MembroFake),
            ("BancaFrenteRepository", BancaFrenteFake),
            ("BancaEscopoRepository", BancaEscopoFake),
            ("EscopoRepository", CatalogoFake),
            ("BancaRemarcacaoRepository", RemarcacaoFake),
            ("BancaSessaoRepository", SessaoFake),
            ("ProjetoRemarcacaoBancaRepository", RemarcacaoProjetoFake),
            ("DiaNaoLetivoRepository", DiaNaoLetivoFake),
            ("ProjetoStatusHistoricoRepository", HistoricoFake),
        ]:
            monkeypatch.setattr(marcar_banca_escopo, nome, fake)

        monkeypatch.setattr(fora_janela, "BancaForaJanelaRepository", ForaJanelaFake)

        def notificou(*a, **k):
            estado.notificou = True

        monkeypatch.setattr(marcar_banca_escopo, "notificar_banca_remarcada", notificou)

        uc = MarcarBancaEscopoUseCase(db=None)

        def executar(data_hora=DENTRO, quem=ANA, justificativa=None, escopo_ids=None):
            return uc.execute(
                alvo.id,
                MarcarBancaEscopoRequest(
                    data_hora=data_hora, justificativa=justificativa, escopo_ids=escopo_ids
                ),
                eh_diretor_projetos=quem.posicao == "diretor_projetos",
                current_user=quem,
            )

        return executar, estado

    return _montar


def banca_marcada(data_hora):
    return SimpleNamespace(
        id=50, data_hora=data_hora, realizado_em=None, coordenador_id=ANA.id
    )


def _amanha_util(hoje):
    return somar_dias_uteis(hoje + timedelta(days=1), 1, CALENDARIO)


def _daqui_a_dias_uteis(hoje, quantos):
    return somar_dias_uteis(hoje + timedelta(days=1), quantos, CALENDARIO)


class TestPrimeiraMarcacao:
    def test_dentro_da_janela_o_coordenador_marca(self, marcar):
        executar, estado = marcar()

        resposta = executar()

        assert resposta["data_hora"] == DENTRO
        assert len(estado.bancas) == 1
        # Primeira marcação não é remarcação: nada no histórico.
        assert estado.remarcacoes == []

    def test_fora_da_janela_o_coordenador_e_barrado(self, marcar):
        """A mensagem tem que dizer ONDE é a janela — senão a pessoa fica
        tentando datas até acertar."""
        executar, _ = marcar()

        with pytest.raises(RegraDeNegocioError, match="fora da janela"):
            executar(data_hora=FORA)

    def test_fora_da_janela_a_diretoria_tambem_e_barrada_sem_autorizacao(self, marcar):
        """⭐ Não é mais atalho de um ato só: nem a diretoria marca sozinha
        fora da janela. Sem um pedido APROVADO (`fora_janela`), ela esbarra
        na mesma trava que o coordenador — a decisão dela agora é um ato
        separado, tomado na aba Aprovações, não um clique na marcação."""
        executar, _ = marcar()

        with pytest.raises(RegraDeNegocioError, match="autorização da diretoria"):
            executar(data_hora=FORA, quem=DANI, justificativa="Agenda do cliente")

    def test_fora_da_janela_com_autorizacao_aprovada_o_coordenador_marca(self, marcar):
        """§13: aprovado o pedido de `fora_janela`, os dias além da janela
        viram atraso — derivado, sem coluna — e quem marca não precisa mais
        ser diretor: a autorização já foi dada, separadamente, por quem podia."""
        executar, estado = marcar(fora_janela_aprovada=[(7, FORA)])

        resposta = executar(data_hora=FORA, quem=ANA, justificativa="Agenda do cliente")

        assert resposta["data_hora"] == FORA

    def test_fora_da_janela_sem_justificativa_nao_passa_mesmo_autorizada(self, marcar):
        executar, _ = marcar(fora_janela_aprovada=[(7, FORA)])

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(data_hora=FORA, quem=DANI)

    def test_dias_ajustados_ampliam_onde_a_banca_cabe(self, marcar):
        """⭐ O efeito prático do §8: a mesma data recusada passa a caber."""
        executar, _ = marcar()
        with pytest.raises(RegraDeNegocioError):
            executar(data_hora=datetime(2026, 10, 15, 14, 0))

        executar_com_ajuste, _ = marcar(escopo(ajustados=10))
        assert executar_com_ajuste(data_hora=datetime(2026, 10, 15, 14, 0))

    def test_escopo_sem_reuniao_inicial_nao_tem_banca(self, marcar):
        """§20.4 — e o INVERSO da trava antiga, que exigia a banca primeiro."""
        executar, _ = marcar(escopo(inicio=None))

        with pytest.raises(RegraDeNegocioError, match="reunião inicial"):
            executar()

    def test_banca_de_varios_escopos_precisa_caber_nos_dois(self, marcar):
        """Estar fora da janela de um deles é o atraso que o §10 vai cobrar
        daquele escopo — deixar passar em silêncio esconderia isso."""
        curto = escopo(id=8, vendidos=2)  # janela fecha em 04/09
        executar, _ = marcar(escopos_extras=[curto])

        with pytest.raises(RegraDeNegocioError, match="fora da janela"):
            executar(escopo_ids=[8])


class TestRemarcacao:
    def test_dentro_da_janela_e_com_folga_o_coordenador_remarca(self, marcar):
        """⭐ Era decisão da diretoria para TODA remarcação, e isso fazia da
        exceção uma rotina. §13 soltou o caso comum."""
        executar, estado = marcar(banca_existente=banca_marcada(datetime(2026, 9, 24, 14, 0)))

        executar(data_hora=DENTRO, justificativa="O cliente pediu um dia depois")

        assert estado.notificou is True

    def test_remarcacao_sempre_exige_justificativa(self, marcar):
        """§9: nunca é silenciosa. O §13 dispensa a diretoria, não o registro."""
        executar, _ = marcar(banca_existente=banca_marcada(datetime(2026, 9, 24, 14, 0)))

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(data_hora=DENTRO)

    def test_a_data_antiga_fica_registrada(self, marcar):
        """Sem isto, "de 24/09 para 25/09" existiria só na notificação — que
        some assim que é lida."""
        antiga = datetime(2026, 9, 24, 14, 0)
        executar, estado = marcar(banca_existente=banca_marcada(antiga))

        executar(data_hora=DENTRO, justificativa="O cliente pediu um dia depois")

        (registro,) = estado.remarcacoes
        assert registro["data_anterior"] == antiga
        assert registro["data_nova"] == DENTRO
        assert registro["justificativa"] == "O cliente pediu um dia depois"
        # Remarcação livre: ninguém precisou autorizar.
        assert registro["autorizado_por"] is None

    def test_remarcacao_autorizada_registra_quem_liberou(self, marcar):
        executar, estado = marcar(
            banca_existente=banca_marcada(datetime(2026, 9, 24, 14, 0)),
            fora_janela_aprovada=[(7, FORA)],
        )

        executar(data_hora=FORA, quem=DANI, justificativa="Agenda do cliente")

        assert estado.remarcacoes[0]["autorizado_por"] == DANI.id

    def test_em_cima_da_hora_exige_diretoria_mesmo_dentro_da_janela(self, marcar):
        """§13: os avaliadores já reservaram a agenda.

        As datas são relativas a HOJE de propósito — o gate compara com o
        relógio, e datas fixas fariam este teste vencer sozinho no dia em que
        passassem. A aritmética de dias úteis em si está prendida em
        `test_janela_escopo.py`, com `referencia` injetada.
        """
        hoje = date.today()
        proxima, daqui_a_muito = _amanha_util(hoje), _daqui_a_dias_uteis(hoje, 12)
        executar, _ = marcar(
            escopo(inicio=hoje, vendidos=40),
            banca_existente=banca_marcada(datetime.combine(proxima, datetime.min.time())),
        )

        alvo = datetime.combine(daqui_a_muito, datetime.min.time())
        with pytest.raises(RegraDeNegocioError, match="cima da hora"):
            executar(data_hora=alvo, justificativa="O cliente pediu")

        assert executar(data_hora=alvo, quem=DANI, justificativa="Autorizado")

    def test_salvar_a_mesma_data_nao_e_remarcacao(self, marcar):
        """Outra edição na mesma request não pode virar linha no histórico."""
        executar, estado = marcar(banca_existente=banca_marcada(DENTRO))

        executar(data_hora=DENTRO)

        assert estado.remarcacoes == []
        assert estado.notificou is False


class TestBancaReprovadaRemarcada:
    """⭐ É **uma banca por escopo, sempre a mesma linha** — inclusive depois de
    reprovada (§9). O que muda é que agora existe uma SESSÃO por tentativa.

    Como a linha é reusada, remarcá-la tem de limpar o que descrevia a sessão
    ANTERIOR. Sem isso, `calcular_status_banca` (que testa `realizado_em` antes
    da data) continuava dizendo "realizada" para uma banca marcada para o
    futuro, e o escopo seguia com a entrega liberada — dava para entregar ao
    cliente com a nova banca ainda por acontecer.

    ⚠ **Limpar já foi APAGAR.** Antes de `banca_sessao`, o veredito sumia do
    banco: sobrava a data antiga em `banca_remarcacao` e nada dizendo que a
    banca tinha sido reprovada. Agora a sessão arquiva antes da limpeza.
    """

    def _reprovada(self, quando):
        return SimpleNamespace(
            id=50,
            data_hora=quando,
            realizado_em=quando,
            resultado="nao_aprovada",
            coordenador_id=ANA.id,
        )

    def test_remarcar_apaga_a_sessao_anterior(self, marcar):
        antiga = datetime(2026, 9, 24, 14, 0)
        banca = self._reprovada(antiga)
        executar, _ = marcar(banca_existente=banca)

        executar(data_hora=DENTRO, justificativa="Reprovada — refazendo")

        assert banca.data_hora == DENTRO
        assert banca.realizado_em is None
        assert banca.resultado is None

    def test_a_reprovacao_nao_se_perde(self, marcar):
        """O que aconteceu fica em `banca_remarcacao`, que alimenta o
        Histórico — apagar da linha da banca não é apagar do projeto."""
        antiga = datetime(2026, 9, 24, 14, 0)
        executar, estado = marcar(banca_existente=self._reprovada(antiga))

        executar(data_hora=DENTRO, justificativa="Reprovada — refazendo")

        (registro,) = estado.remarcacoes
        assert registro["data_anterior"] == antiga
        assert registro["justificativa"] == "Reprovada — refazendo"

    def test_salvar_a_mesma_data_nao_apaga_o_resultado(self, marcar):
        """Não é remarcação: a banca aconteceu e o veredito continua valendo."""
        banca = self._reprovada(DENTRO)
        executar, _ = marcar(banca_existente=banca)

        executar(data_hora=DENTRO)

        assert banca.realizado_em == DENTRO
        assert banca.resultado == "nao_aprovada"

    def test_salvar_a_mesma_data_nao_abre_sessao_nova(self, marcar):
        """⚠ A sessão fantasma.

        Salvar a mesma data numa banca já realizada — o que acontece quando a
        request edita outro campo — não é uma segunda tentativa. Abrir sessão
        nova aqui encerraria a sessão viva e deixaria os votos carimbados com
        `sessao=1` apontando para uma sessão morta: a apuração passaria a ler a
        sessão nova, vazia, e a banca nunca fecharia.
        """
        banca = self._reprovada(DENTRO)
        executar, estado = marcar(banca_existente=banca)
        estado.sessoes.append(
            SimpleNamespace(
                id=1,
                banca_id=banca.id,
                numero=1,
                data_hora=DENTRO,
                realizado_em=DENTRO,
                resultado="nao_aprovada",
                encerrada_em=None,
            )
        )

        executar(data_hora=DENTRO)

        # Uma sessão só, e ainda aberta: nada foi arquivado nem aberto.
        assert len(estado.sessoes) == 1
        assert estado.sessoes[0].encerrada_em is None

    def test_a_sessao_anterior_arquiva_o_veredito(self, marcar):
        """⭐ O que esta fatia inteira existe para consertar.

        A sessão 1 fecha guardando `realizado_em` e `resultado`; só DEPOIS a
        linha da banca é limpa. Antes, a reprovação era apagada sem cópia — o
        histórico perdia a tentativa e ninguém conseguia responder "por que
        este escopo teve duas bancas?".
        """
        antiga = datetime(2026, 9, 24, 14, 0)
        banca = self._reprovada(antiga)
        executar, estado = marcar(banca_existente=banca)
        # A sessão que já existia quando a banca aconteceu.
        estado.sessoes.append(
            SimpleNamespace(
                id=1,
                banca_id=banca.id,
                numero=1,
                data_hora=antiga,
                realizado_em=antiga,
                resultado="nao_aprovada",
                encerrada_em=None,
            )
        )

        executar(data_hora=DENTRO, justificativa="Reprovada — refazendo")

        anterior, nova = estado.sessoes
        # A tentativa que falhou ficou inteira, apesar de a linha da banca
        # ter sido limpa logo depois.
        assert anterior.realizado_em == antiga
        assert anterior.resultado == "nao_aprovada"
        assert anterior.encerrada_em is not None
        # E a 2ª nasceu aberta, na data nova.
        assert (nova.numero, nova.data_hora, nova.encerrada_em) == (2, DENTRO, None)
        assert banca.resultado is None


class TestSegundaBancaNaoEhRemarcacao:
    """⭐ Os gates do adiamento NÃO valem para a 2ª banca.

    O caso que motivou: `dias_uteis_ate_a_banca` devolve **0** para data no
    passado, e `0 <= FOLGA_LIVRE_REMARCACAO_DIAS_UTEIS` é sempre verdadeiro.
    Passar a 2ª banca por `_exigir_remarcacao_permitida` exigiria diretoria em
    TODAS elas — por um gate que existe para proteger a agenda de avaliadores
    já escalados, numa banca a que eles já compareceram.
    """

    def _reprovada_no_passado(self):
        # Ontem: garante `folga == 0` sem depender de data fixa.
        ontem = datetime.combine(date.today(), datetime.min.time()) - timedelta(days=1)
        return SimpleNamespace(
            id=60,
            data_hora=ontem,
            realizado_em=ontem,
            resultado="nao_aprovada",
            coordenador_id=ANA.id,
        )

    def test_coordenador_marca_a_segunda_sem_diretoria(self, marcar):
        """Se o gate de folga valesse aqui, isto levantaria 'cima da hora'."""
        hoje = date.today()
        executar, _ = marcar(
            escopo(inicio=hoje, vendidos=40),
            banca_existente=self._reprovada_no_passado(),
        )

        alvo = datetime.combine(_daqui_a_dias_uteis(hoje, 12), datetime.min.time())

        assert executar(data_hora=alvo, quem=ANA)

    def test_segunda_banca_dispensa_justificativa(self, marcar):
        """O motivo é a reprovação, que já está registrada na sessão."""
        hoje = date.today()
        executar, _ = marcar(
            escopo(inicio=hoje, vendidos=40),
            banca_existente=self._reprovada_no_passado(),
        )

        alvo = datetime.combine(_daqui_a_dias_uteis(hoje, 12), datetime.min.time())

        assert executar(data_hora=alvo, justificativa=None)

    def test_aprovacao_que_nasce_na_apuracao_tambem_barra_a_segunda(self, marcar):
        """⚠ A janela de ordenação que quase custou a trava da entrega.

        A banca aconteceu e ainda não tinha veredito na linha de `banca` — o
        veredito só nasce quando a apuração roda. Como a apuração acontecia
        DEPOIS da guarda, `_exigir_segunda_permitida` lia `resultado=None` e
        deixava passar: a sessão era arquivada como "aprovada", a 2ª banca
        nascia, e `_campos_da_remarcacao` apagava o resultado da linha que a
        trava do §5.5 lê. O escopo ficava aprovado no histórico e travado na
        tela.

        Aqui a apuração já rodou quando a guarda decide, e a recusa acontece.
        """
        banca = self._reprovada_no_passado()
        banca.resultado = None  # ainda sem veredito quando a request chega
        executar, estado = marcar(banca_existente=banca)
        estado.sessoes.append(
            SimpleNamespace(
                id=1, banca_id=banca.id, numero=1, data_hora=banca.data_hora,
                realizado_em=banca.realizado_em, resultado=None, encerrada_em=None,
            )
        )

        # A apuração (dublada abaixo) grava "aprovada" ao ser chamada.
        import src.use_cases.avaliacao.submeter_avaliacao as submeter

        def apurar_falso(db, alvo, prazo_vencido=None):
            alvo.resultado = "aprovada"
            return SimpleNamespace(resultado="aprovada", decidida=True)

        original = submeter.apurar_banca
        submeter.apurar_banca = apurar_falso
        try:
            with pytest.raises(RegraDeNegocioError, match="APROVADA"):
                executar(data_hora=DENTRO)
        finally:
            submeter.apurar_banca = original

        # E nada foi arquivado nem aberto: a recusa veio antes.
        assert len(estado.sessoes) == 1
        assert estado.sessoes[0].encerrada_em is None

    def test_banca_aprovada_nao_ganha_segunda(self, marcar):
        """⚠ Antes isto passava e apagava a aprovação em silêncio — o escopo
        perdia o veredito que liberava a entrega, sem registro nenhum."""
        hoje = date.today()
        aprovada = self._reprovada_no_passado()
        aprovada.resultado = "aprovada"
        executar, _ = marcar(escopo(inicio=hoje, vendidos=40), banca_existente=aprovada)

        alvo = datetime.combine(_daqui_a_dias_uteis(hoje, 12), datetime.min.time())

        with pytest.raises(RegraDeNegocioError, match="APROVADA"):
            executar(data_hora=alvo)

    def test_adiamento_continua_com_os_gates(self, marcar):
        """Proteção contra regressão: banca que ainda NÃO aconteceu segue
        exigindo justificativa e, em cima da hora, diretoria."""
        executar, _ = marcar(banca_existente=banca_marcada(datetime(2026, 9, 24, 14, 0)))

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(data_hora=DENTRO, justificativa=None)

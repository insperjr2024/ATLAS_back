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

from src.use_cases.banca import marcar_banca_escopo
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
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor")


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

    def _montar(alvo=None, *, banca_existente=None, escopos_extras=()):
        alvo = alvo if alvo is not None else escopo()
        estado = SimpleNamespace(remarcacoes=[], bancas=[], notificou=False)
        todos = {e.id: e for e in (alvo, *escopos_extras)}

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, _id): return banca_existente
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
            ("ProjetoRemarcacaoBancaRepository", RemarcacaoProjetoFake),
            ("DiaNaoLetivoRepository", DiaNaoLetivoFake),
            ("ProjetoStatusHistoricoRepository", HistoricoFake),
        ]:
            monkeypatch.setattr(marcar_banca_escopo, nome, fake)

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
                eh_diretor=quem.posicao == "diretor",
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

    def test_fora_da_janela_a_diretoria_marca_com_justificativa(self, marcar):
        """§13: os dias além da janela viram atraso — derivado, sem coluna."""
        executar, estado = marcar()

        resposta = executar(data_hora=FORA, quem=DANI, justificativa="Agenda do cliente")

        assert resposta["data_hora"] == FORA

    def test_fora_da_janela_sem_justificativa_nao_passa_nem_para_a_diretoria(self, marcar):
        executar, _ = marcar()

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
        executar, estado = marcar(banca_existente=banca_marcada(datetime(2026, 9, 24, 14, 0)))

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
    reprovada (§9).

    Como a linha é reusada, remarcá-la tem de apagar o que descrevia a sessão
    ANTERIOR. Sem isso, `calcular_status_banca` (que testa `realizado_em` antes
    da data) continuava dizendo "realizada" para uma banca marcada para o
    futuro, e o escopo seguia com a entrega liberada — dava para entregar ao
    cliente com a nova banca ainda por acontecer.
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

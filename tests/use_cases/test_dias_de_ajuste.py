"""⭐ O pedido de dias de ajuste (§8) — o único fluxo de aprovação que sobrou
no cronograma.

Quatro regras dominam estes testes, e todas as quatro protegem a mesma coisa:
que "vendidos" continue significando o que foi vendido.

- **Só o coordenador pede**, e é o papel NO PROJETO que vale — não a posição
  na plataforma nem uma caixa de `cargo`.
- **Só nos 3 primeiros dias úteis**, contando a reunião inicial como dia 1.
  Depois disso acabou: o que passar da janela é atraso, sem autorização.
- **Aprovar SOMA** em `dias_uteis_ajustados` e **nunca toca no vendido**.
- **Negar não fecha a porta** — dentro do prazo dá para pedir de novo.

Os dublês são escritos à mão e as CLASSES de repositório são trocadas no
módulo via `monkeypatch`, porque os use cases as instanciam por dentro —
mesmo idioma de `test_destinatarios_notificacao.py`.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.cronograma_reajuste import responder, solicitar
from src.use_cases.cronograma_reajuste.responder import (
    ResponderReajusteRequest,
    ResponderReajusteUseCase,
)
from src.use_cases.cronograma_reajuste.solicitar import (
    MAXIMO_DIAS_POR_PEDIDO,
    SolicitarReajusteRequest,
    SolicitarReajusteUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# O calendário 2026.2 do seed: 07/09 é feriado.
CALENDARIO = [date(2026, 9, 7), date(2026, 10, 12)]

QUI_03_09 = date(2026, 9, 3)  # a reunião inicial
TER_08_09 = date(2026, 9, 8)  # o 3º dia útil — último dia do prazo
QUA_09_09 = date(2026, 9, 9)  # o 4º — acabou

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
CAIO = SimpleNamespace(id=11, nome="Caio Ferreira", posicao="consultor")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


def escopo(vendidos=20, ajustados=0, data_inicio=QUI_03_09):
    return SimpleNamespace(
        id=7,
        projeto_id=3,
        escopo_id=None,
        nome_customizado="Elaboração Contratual",
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
        data_inicio=data_inicio,
    )


@pytest.fixture
def pedir(monkeypatch):
    """Devolve `(executar, estado)` — `estado` mostra o que foi gravado."""

    def _montar(alvo=None, *, hoje=QUI_03_09, equipe=None, pendente=None):
        alvo = alvo if alvo is not None else escopo()
        estado = SimpleNamespace(criados=[], notificados=[])
        equipe = equipe if equipe is not None else [
            SimpleNamespace(usuario_id=ANA.id, papel="coordenador"),
            SimpleNamespace(usuario_id=CAIO.id, papel="consultor"),
        ]

        class ReajusteFake:
            def __init__(self, db): pass
            def get_pendente_do_escopo(self, escopo_id):
                return pendente
            def create(self, **campos):
                estado.criados.append(campos)
                return SimpleNamespace(id=99, status="pendente", respondido_por=None,
                                       resposta_justificativa=None, respondido_em=None,
                                       criado_em=None, **campos)

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, escopo_id):
                return alvo if alvo and alvo.id == escopo_id else None

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, escopo_id): return None

        class UsuarioFake:
            def __init__(self, db): pass
            def get_por_posicao(self, posicao):
                return [DANI] if posicao == "diretor_projetos" else []
            def get_por_posicoes(self, *posicoes):
                return [DANI] if "diretor_projetos" in posicoes else []

        class MembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, projeto_id, apenas_atuais=False):
                return equipe

        class DiaNaoLetivoFake:
            def __init__(self, db): pass
            def get_all(self):
                return [SimpleNamespace(data=d) for d in CALENDARIO]

        monkeypatch.setattr(solicitar, "CronogramaReajusteRepository", ReajusteFake)
        monkeypatch.setattr(solicitar, "ProjetoEscopoRepository", EscopoProjetoFake)
        class HistoricoFake:
            """Projeto que nunca foi pausado — a janela não desloca.

            O prazo de pedido passou a descontar as janelas de pausa (um projeto
            ⏸ Pausado não pode perder o direito de pedir por dias em que ninguém
            trabalhou). Estes testes medem o prazo, não a pausa: histórico vazio
            mantém as datas deles valendo. A pausa tem teste próprio em
            `tests/utils/test_janela_escopo.py`.
            """

            def __init__(self, db): pass
            def get_by_projeto(self, _id): return []

        monkeypatch.setattr(solicitar, "EscopoRepository", CatalogoFake)
        monkeypatch.setattr(solicitar, "UsuarioRepository", UsuarioFake)
        monkeypatch.setattr(solicitar, "ProjetoMembroRepository", MembroFake)
        monkeypatch.setattr(solicitar, "DiaNaoLetivoRepository", DiaNaoLetivoFake)
        monkeypatch.setattr(
            solicitar, "ProjetoStatusHistoricoRepository", HistoricoFake
        )
        monkeypatch.setattr(
            solicitar, "notificar_reajuste_solicitado",
            lambda db, dest, *a, **k: estado.notificados.append(dest),
        )
        # `calcular_janela` é pura, mas lê `date.today()` quando não recebe
        # referência — aqui a data do teste entra por este atalho.
        original = solicitar.calcular_janela
        monkeypatch.setattr(
            solicitar, "calcular_janela",
            lambda *a, **k: original(*a, **{**k, "referencia": hoje}),
        )

        uc = SolicitarReajusteUseCase.__new__(SolicitarReajusteUseCase)
        uc.__init__(db=None)

        def executar(dias=10, motivo="O cliente atrasou a base de contratos", quem=ANA):
            return uc.execute(
                alvo.id if alvo else 7,
                SolicitarReajusteRequest(dias_solicitados=dias, motivo=motivo),
                quem,
            )

        return executar, estado

    return _montar


class TestQuemPode:
    def test_coordenador_do_projeto_pede(self, pedir):
        executar, estado = pedir()

        resposta = executar()

        assert resposta["dias_solicitados"] == 10
        assert estado.criados[0]["dias_solicitados"] == 10
        # A diretoria é avisada — é ela que decide.
        assert estado.notificados == [DANI.id]

    def test_consultor_da_equipe_nao_pede(self, pedir):
        executar, _ = pedir()

        with pytest.raises(RegraDeNegocioError, match="Só o coordenador"):
            executar(quem=CAIO)

    def test_diretor_nao_pede_para_si_mesmo(self, pedir):
        """Ele decide, não pede — e não está na equipe do projeto."""
        executar, _ = pedir()

        with pytest.raises(RegraDeNegocioError, match="Só o coordenador"):
            executar(quem=DANI)

    def test_coordenador_de_outro_projeto_nao_pede(self, pedir):
        """A equipe deste projeto não tem a Ana como coordenadora."""
        executar, _ = pedir(equipe=[SimpleNamespace(usuario_id=99, papel="coordenador")])

        with pytest.raises(RegraDeNegocioError, match="Só o coordenador"):
            executar()


class TestPrazo:
    def test_no_ultimo_dia_do_prazo_ainda_da(self, pedir):
        """§20.1: vale a data do PEDIDO. 08/09 é o 3º dia útil (07/09 é
        feriado), e a diretora pode responder depois disso."""
        executar, estado = pedir(hoje=TER_08_09)

        executar()

        assert len(estado.criados) == 1

    def test_no_dia_seguinte_acabou(self, pedir):
        executar, _ = pedir(hoje=QUA_09_09)

        with pytest.raises(RegraDeNegocioError, match="prazo para pedir dias"):
            executar()

    def test_escopo_sem_reuniao_inicial_nao_tem_prazo_correndo(self, pedir):
        """§20.4: sem janela não há o que esticar — e o próprio início ainda
        pode mudar."""
        executar, _ = pedir(escopo(data_inicio=None))

        with pytest.raises(RegraDeNegocioError, match="reunião inicial"):
            executar()


class TestValidacaoDoPedido:
    def test_pedido_de_zero_dias_nao_passa(self, pedir):
        executar, _ = pedir()
        with pytest.raises(RegraDeNegocioError, match="pelo menos 1 dia"):
            executar(dias=0)

    def test_dedo_escorregado_no_teclado_e_barrado(self, pedir):
        """Sem teto, um "+300" seria aprovado sem ninguém perceber e não
        haveria como desfazer."""
        executar, _ = pedir()
        with pytest.raises(RegraDeNegocioError):
            executar(dias=MAXIMO_DIAS_POR_PEDIDO + 1)

    def test_motivo_vazio_nao_passa(self, pedir):
        executar, _ = pedir()
        with pytest.raises(RegraDeNegocioError, match="Descreva"):
            executar(motivo="   ")

    def test_um_pendente_por_vez(self, pedir):
        """Dois pendentes fariam a diretora responder pedidos que se somam sem
        ver o efeito combinado."""
        executar, _ = pedir(pendente=SimpleNamespace(id=1))

        with pytest.raises(RegraDeNegocioError, match="pendente"):
            executar()


@pytest.fixture
def responder_pedido(monkeypatch):
    def _montar(*, dias=10, aprovado=True, alvo=None, status="pendente"):
        alvo = alvo if alvo is not None else escopo()
        estado = SimpleNamespace(atualizacoes=[])
        solicitacao = SimpleNamespace(
            id=99,
            projeto_escopo_id=alvo.id,
            solicitado_por=ANA.id,
            dias_solicitados=dias,
            motivo="...",
            status=status,
            respondido_por=None,
            resposta_justificativa=None,
            criado_em=None,
            respondido_em=None,
        )

        class ReajusteFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return solicitacao
            def update(self, _id, **campos):
                for k, v in campos.items():
                    setattr(solicitacao, k, v)
                return solicitacao

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return alvo
            def update(self, _id, **campos):
                estado.atualizacoes.append(campos)
                for k, v in campos.items():
                    setattr(alvo, k, v)
                return alvo

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None

        monkeypatch.setattr(responder, "CronogramaReajusteRepository", ReajusteFake)
        monkeypatch.setattr(responder, "ProjetoEscopoRepository", EscopoProjetoFake)
        monkeypatch.setattr(responder, "EscopoRepository", CatalogoFake)
        monkeypatch.setattr(responder, "notificar_reajuste_respondido", lambda *a, **k: None)

        uc = ResponderReajusteUseCase.__new__(ResponderReajusteUseCase)
        uc.__init__(db=None)

        def executar(justificativa="Faz sentido, o cliente travou a base"):
            return uc.execute(
                99, ResponderReajusteRequest(aprovado=aprovado, justificativa=justificativa), DANI
            )

        return executar, estado, alvo

    return _montar


class TestDecisao:
    def test_aprovar_soma_nos_ajustados_e_nao_toca_no_vendido(self, responder_pedido):
        """⭐ O exemplo do §5: 20 vendidos + 10 aprovados = janela de 30, e a
        tela continua dizendo *vendidos 20 · ajustados 10*."""
        executar, estado, alvo = responder_pedido(dias=10)

        executar()

        assert estado.atualizacoes == [{"dias_uteis_ajustados": 10}]
        assert alvo.dias_uteis_vendidos == 20

    def test_dois_pedidos_aprovados_se_somam(self, responder_pedido):
        """§8: +5 e depois +5 = 10 dias ajustados."""
        executar, estado, alvo = responder_pedido(dias=5, alvo=escopo(ajustados=5))

        executar()

        assert alvo.dias_uteis_ajustados == 10

    def test_negar_nao_mexe_em_dia_nenhum(self, responder_pedido):
        executar, estado, alvo = responder_pedido(dias=10, aprovado=False)

        executar()

        assert estado.atualizacoes == []
        assert alvo.dias_uteis_ajustados == 0

    def test_pedido_ja_respondido_nao_responde_de_novo(self, responder_pedido):
        """Sem isso, aprovar duas vezes somaria os dias duas vezes."""
        executar, _, _ = responder_pedido(status="aprovado")

        with pytest.raises(RegraDeNegocioError, match="já foi respondida"):
            executar()

    def test_decisao_exige_justificativa(self, responder_pedido):
        executar, _, _ = responder_pedido()

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(justificativa="  ")

"""⭐ O pedido de dias de ajuste (§8) — o único fluxo de aprovação que sobrou
no cronograma.

Quatro regras dominam estes testes, e todas as quatro protegem a mesma coisa:
que "vendidos" continue significando o que foi vendido.

- **Pede o coordenador do projeto ou a diretoria de projetos.** Para o
  coordenador vale o papel NO PROJETO — não a posição na plataforma nem uma
  caixa de `cargo`; a diretoria de projetos entra pela POSIÇÃO, sem estar na
  equipe (2026-08-31).
- **Só dentro do prazo**, e ele tem duas réguas: o PRIMEIRO escopo vendido
  pede até o último dia da ambientação (o kickoff); os demais, nos 3 primeiros
  dias úteis da reunião inicial deles, contando a reunião como o dia 1. Depois
  disso acabou: o que passar da janela é atraso, sem autorização.
- **Aprovar SOMA** em `dias_uteis_ajustados` e **nunca toca no vendido**.
- **Negar não fecha a porta** — dentro do prazo dá para pedir de novo.

Os dublês são escritos à mão e as CLASSES de repositório são trocadas no
módulo via `monkeypatch`, porque os use cases as instanciam por dentro —
mesmo idioma de `test_destinatarios_notificacao.py`.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.use_cases.cronograma_reajuste import responder, solicitar
from src.use_cases.cronograma_reajuste.responder import (
    ResponderReajusteRequest,
    ResponderReajusteUseCase,
)
from src.use_cases.monitoramento.aprovacoes import pedido_fora_do_prazo
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

SEX_28_08 = date(2026, 8, 28)  # kickoff cuja ambientação de 5 dias fecha em 03/09
QUI_27_08 = date(2026, 8, 27)  # kickoff cuja ambientação de 5 dias fechou em 02/09

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
CAIO = SimpleNamespace(id=11, nome="Caio Ferreira", posicao="consultor")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")
GIL = SimpleNamespace(id=2, nome="Gil Nunes", posicao="gerente")


def projeto(status="em_andamento", data_kickoff=None, dias_ambientacao=5):
    return SimpleNamespace(
        id=3,
        status=status,
        data_kickoff=data_kickoff,
        data_inicio_ambientacao=None,
        dias_ambientacao=dias_ambientacao,
    )


def escopo(vendidos=20, ajustados=0, data_inicio=QUI_03_09, id=7, ordem=0):
    return SimpleNamespace(
        id=id,
        projeto_id=3,
        escopo_id=None,
        nome_customizado="Elaboração Contratual",
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
        data_inicio=data_inicio,
        # A posição na lista *Escopos vendidos* — é ela que decide se o prazo
        # deste escopo é o do kickoff ou os 3 dias úteis da largada.
        ordem=ordem,
    )


@pytest.fixture
def pedir(monkeypatch):
    """Devolve `(executar, estado)` — `estado` mostra o que foi gravado."""

    def _montar(
        alvo=None, *, hoje=QUI_03_09, equipe=None, pendente=None, dono=None, vendidos=None
    ):
        alvo = alvo if alvo is not None else escopo()
        dono = dono if dono is not None else projeto()
        # A lista *Escopos vendidos* do projeto. Com um escopo só, ele é o
        # primeiro; os testes do segundo escopo passam a lista inteira.
        vendidos = vendidos if vendidos is not None else [alvo]
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
                return next((e for e in vendidos if e.id == escopo_id), None)
            def get_by_projeto(self, projeto_id):
                return sorted(vendidos, key=lambda e: (e.ordem, e.id))

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
                return [SimpleNamespace(data=d, frente_id=None) for d in CALENDARIO]
            # O calendário deste projeto. Sem variantes no fake, é o mesmo
            # `get_all()` — o que muda na produção é só o corte por curso.
            def get_do_projeto(self, _projeto_id):
                return self.get_all()

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, projeto_id):
                return dono if dono.id == projeto_id else None

        monkeypatch.setattr(solicitar, "CronogramaReajusteRepository", ReajusteFake)
        monkeypatch.setattr(solicitar, "ProjetoEscopoRepository", EscopoProjetoFake)
        monkeypatch.setattr(solicitar, "ProjetoRepository", ProjetoFake)
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

    def test_diretoria_de_projetos_pede_sem_estar_na_equipe(self, pedir):
        """2026-08-31: ela enxerga o portfólio inteiro e pede em qualquer
        projeto. Antes era barrada aqui ("decide, não pede")."""
        executar, estado = pedir()

        resposta = executar(quem=DANI)

        assert resposta["dias_solicitados"] == 10
        assert estado.criados[0]["solicitado_por"] == DANI.id

    def test_quem_pede_nao_e_notificado_do_proprio_pedido(self, pedir):
        """DANI é a única `diretor_projetos` do dublê: pedindo ela mesma, não
        sobra ninguém para avisar."""
        executar, estado = pedir()

        executar(quem=DANI)

        assert estado.notificados == []

    def test_gerente_nao_pede(self, pedir):
        """Nem conduz o escopo nem decide sobre ele."""
        executar, _ = pedir()

        with pytest.raises(RegraDeNegocioError, match="Só o coordenador"):
            executar(quem=GIL)

    def test_coordenador_de_outro_projeto_nao_pede(self, pedir):
        """A equipe deste projeto não tem a Ana como coordenadora."""
        executar, _ = pedir(equipe=[SimpleNamespace(usuario_id=99, papel="coordenador")])

        with pytest.raises(RegraDeNegocioError, match="Só o coordenador"):
            executar()


class TestPrazoSemAmbientacao:
    """A régua dos 3 dias úteis, medida num projeto SEM kickoff marcado.

    Sem ambientação não há "último dia da ambientação" para servir de prazo, e
    até o primeiro escopo cai na régua da reunião inicial — que é a mesma dos
    escopos seguintes. É por isso que `projeto()` nasce sem `data_kickoff`.
    """

    def test_no_ultimo_dia_do_prazo_ainda_da(self, pedir):
        """§20.1: vale a data do PEDIDO. 08/09 é o 3º dia útil (07/09 é
        feriado), e a diretora pode responder depois disso."""
        executar, estado = pedir(hoje=TER_08_09)

        executar()

        assert len(estado.criados) == 1

    def test_no_dia_seguinte_acabou(self, pedir):
        executar, _ = pedir(hoje=QUA_09_09)

        with pytest.raises(RegraDeNegocioError, match="3 dias úteis"):
            executar()

    def test_escopo_sem_reuniao_inicial_nao_tem_prazo_correndo(self, pedir):
        """§20.4: sem janela não há o que esticar — e o próprio início ainda
        pode mudar."""
        executar, _ = pedir(escopo(data_inicio=None))

        with pytest.raises(RegraDeNegocioError, match="reunião inicial"):
            executar()


class TestPrazoDoPrimeiroEscopo:
    """⭐ O primeiro escopo vendido pede dias **até o último dia da
    ambientação** — o kickoff.

    É nela que a equipe conhece o projeto e descobre que os dias vendidos não
    fecham, e é ali que a conversa com a diretoria cabe: a largada seguinte já
    é o time produzindo dentro de um prazo que ninguém mais vai renegociar.

    ⚠ Isto ENCURTOU a regra anterior, em que a ambientação era só uma exceção
    que antecipava o pedido e os 3 dias úteis seguiam correndo depois da
    largada. Hoje, para o primeiro escopo, a largada não estende nada.
    """

    def test_durante_a_ambientacao_pede_sem_reuniao_inicial(self, pedir):
        executar, estado = pedir(
            escopo(data_inicio=None),
            dono=projeto(status="ambientacao", data_kickoff=SEX_28_08),
            hoje=date(2026, 9, 1),
        )

        executar()

        assert len(estado.criados) == 1

    def test_no_ultimo_dia_da_ambientacao_ainda_da(self, pedir):
        """Kickoff 28/08 + 5 dias úteis (o kickoff é o 1º) → o 5º é 03/09,
        e nele o pedido ainda vale — a virada é só no dia seguinte."""
        executar, estado = pedir(
            escopo(data_inicio=None),
            dono=projeto(status="ambientacao", data_kickoff=SEX_28_08),
            hoje=QUI_03_09,
        )

        executar()

        assert len(estado.criados) == 1

    def test_depois_da_ambientacao_a_largada_nao_estende_o_prazo(self, pedir):
        """⭐ O coração da mudança.

        Largada em 03/09 (o último dia da ambientação) e pedido em 04/09: pela
        régua antiga ainda haveria dois dias úteis de prazo, porque os 3 dias
        contavam da reunião inicial. Hoje o prazo do primeiro escopo acabou
        junto com a ambientação.
        """
        executar, _ = pedir(
            escopo(data_inicio=QUI_03_09),
            dono=projeto(data_kickoff=SEX_28_08),
            hoje=date(2026, 9, 4),
        )

        with pytest.raises(RegraDeNegocioError, match="último dia da ambientação"):
            executar()

    def test_status_atrasado_nao_reabre_depois_do_fim(self, pedir):
        """A virada automática pode não ter rodado: o status ainda diz
        Ambientação, mas a data diz que ela acabou em 02/09 — a data manda."""
        executar, _ = pedir(
            escopo(data_inicio=None),
            dono=projeto(status="ambientacao", data_kickoff=QUI_27_08),
            hoje=QUI_03_09,
        )

        with pytest.raises(RegraDeNegocioError, match="último dia da ambientação"):
            executar()

    def test_projeto_vendido_nao_pede(self, pedir):
        """Antes da ambientação não há equipe em campo — nada para ajustar,
        e o próprio kickoff ainda pode mudar. O STATUS é que segura a entrada:
        sem ele, o escopo cai na régua da reunião inicial, que nem existe."""
        executar, _ = pedir(
            escopo(data_inicio=None),
            dono=projeto(status="vendido", data_kickoff=SEX_28_08),
            hoje=date(2026, 9, 1),
        )

        with pytest.raises(RegraDeNegocioError, match="reunião inicial"):
            executar()

    def test_reuniao_inicial_dentro_da_ambientacao_nao_encurta_o_prazo(self, pedir):
        """Reunião inicial no 1º dia da ambientação: os 3 dias úteis dela
        venceriam em 01/09, mas o prazo do primeiro escopo é a ambientação
        inteira, até 03/09."""
        executar, estado = pedir(
            escopo(data_inicio=SEX_28_08),
            dono=projeto(status="ambientacao", data_kickoff=SEX_28_08),
            hoje=QUI_03_09,
        )

        executar()

        assert len(estado.criados) == 1


class TestPrazoDoSegundoEscopo:
    """⭐ O segundo escopo NÃO tem ambientação — ela é do projeto e aconteceu
    uma vez só, lá no começo.

    Pendurar o prazo dele naquela data seria nascer vencido: quando o segundo
    escopo larga, semanas depois, a ambientação já acabou há muito. Por isso
    ele fica com a régua de sempre, os 3 dias úteis da reunião inicial dele.
    """

    def segundo(self):
        """A lista *Escopos vendidos* do projeto: o primeiro e o segundo."""
        primeiro = escopo(id=7, ordem=0, data_inicio=SEX_28_08)
        segundo = escopo(id=8, ordem=1, data_inicio=QUI_03_09)
        return segundo, [primeiro, segundo]

    def test_os_3_dias_uteis_valem_mesmo_com_a_ambientacao_encerrada(self, pedir):
        """Ambientação fechada em 03/09 e pedido em 08/09: para o segundo
        escopo o que vale é a reunião inicial dele, não o kickoff."""
        alvo, vendidos = self.segundo()
        executar, estado = pedir(
            alvo,
            vendidos=vendidos,
            dono=projeto(data_kickoff=SEX_28_08),
            hoje=TER_08_09,
        )

        executar()

        assert len(estado.criados) == 1

    def test_no_dia_seguinte_ao_3o_dia_util_acabou(self, pedir):
        alvo, vendidos = self.segundo()
        executar, _ = pedir(
            alvo,
            vendidos=vendidos,
            dono=projeto(data_kickoff=SEX_28_08),
            hoje=QUA_09_09,
        )

        with pytest.raises(RegraDeNegocioError, match="3 dias úteis"):
            executar()

    def test_a_ambientacao_do_projeto_nao_abre_pedido_para_ele(self, pedir):
        """Projeto em ambientação, segundo escopo ainda sem reunião inicial:
        não há prazo correndo. A ambientação abre o pedido do PRIMEIRO escopo,
        não o de todos."""
        primeiro = escopo(id=7, ordem=0, data_inicio=None)
        alvo = escopo(id=8, ordem=1, data_inicio=None)
        executar, _ = pedir(
            alvo,
            vendidos=[primeiro, alvo],
            dono=projeto(status="ambientacao", data_kickoff=SEX_28_08),
            hoje=date(2026, 9, 1),
        )

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

        def executar(justificativa="Faz sentido, o cliente travou a base", quem=DANI):
            return uc.execute(
                99, ResponderReajusteRequest(aprovado=aprovado, justificativa=justificativa), quem
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

    def test_gerente_nao_decide(self, responder_pedido):
        """O recheck do use case não pode depender só do gate da rota: quem
        chega aqui por outro caminho também é barrado — e é por POSIÇÃO, a
        única dimensão de permissão desde que `cargo` saiu."""
        executar, estado, _ = responder_pedido()

        with pytest.raises(RegraDeNegocioError, match="diretoria de projetos"):
            executar(quem=GIL)

        assert estado.atualizacoes == []


class TestPedidoForaDoPrazo:
    """A pílula que a diretoria lê na fila — §20.1: vale a data do PEDIDO.

    ⚠ A conta era "prazo < hoje", e por isso acusava de atrasado quem pediu
    dentro do prazo e só esperou a resposta. Com o prazo do primeiro escopo
    fechando junto com a ambientação, isso virou o caso comum: a diretoria
    quase sempre responde depois que o prazo daquele escopo já passou.
    """

    PRAZO = date(2026, 8, 25)

    def test_pedido_dentro_do_prazo_nao_e_atrasado_por_demora_da_resposta(self):
        assert pedido_fora_do_prazo(datetime(2026, 8, 25, 12, 0), self.PRAZO) is False

    def test_pedido_no_fim_do_ultimo_dia_conta_no_fuso_local(self):
        """⏱ 26/08 00:30 em UTC é 25/08 21:30 em São Paulo — o último dia do
        prazo. Sem a conversão, quem pede à noite nasce fora do prazo."""
        assert pedido_fora_do_prazo(datetime(2026, 8, 26, 0, 30), self.PRAZO) is False

    def test_pedido_no_dia_seguinte_e_fora_do_prazo(self):
        """Só chega aqui pedido gravado por outro caminho (dado antigo, ou
        prazo que encurtou depois) — `solicitar` recusa na porta."""
        assert pedido_fora_do_prazo(datetime(2026, 8, 26, 15, 0), self.PRAZO) is True

    def test_escopo_sem_prazo_nao_perde_prazo_nenhum(self):
        assert pedido_fora_do_prazo(datetime(2026, 8, 26, 15, 0), None) is False

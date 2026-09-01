"""⭐ A etapa não sai da janela do escopo — e a saída é pedir dias, não arrastar.

A regra INVERTEU. Antes, pintar além da janela avisava e deixava passar (§15):
o calendário era planejamento livre e o estouro virava atraso. A diretoria
fechou o contrário — o calendário do escopo é o tempo que foi vendido, e
esticar o trabalho para fora dele é renegociar prazo.

A porta de saída continua sendo o pedido de dias de ajuste, e ela tem prazo
(§5.4): até o último dia da ambientação para o PRIMEIRO escopo vendido, e 3
dias úteis a partir da largada para os demais. Por isso a mensagem de recusa
precisa dizer as três coisas: onde a janela termina, que o caminho é pedir
dias, e se esse caminho ainda existe.

⚠ Exceção: depois da BANCA REALIZADA, qualquer mudança no cronograma daquele
escopo é entendida como **ajustes** — e ajuste nasce fora da janela por
definição. A entrega também libera, mas é consequência: o §5.5 só a permite
depois da banca.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.cronograma import update_cronograma
from src.use_cases.cronograma.update_cronograma import (
    CreateEtapaUseCase,
    EtapaIntervaloRequest,
    EtapaRequest,
    UpdateEtapaIntervaloUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# Calendário real do seed 2026.2: o feriado de 07/09 empurra a conta.
CALENDARIO = [date(2026, 9, 7)]
QUI_03_09 = date(2026, 9, 3)  # a largada
FIM_DA_JANELA = date(2026, 10, 1)  # 20º dia útil a partir dela (07/09 é feriado)


def escopo(entregue=None, ajustados=0, banca=None):
    return SimpleNamespace(
        id=7,
        projeto_id=3,
        ordem=0,
        data_inicio=QUI_03_09,
        dias_uteis_vendidos=20,
        dias_uteis_ajustados=ajustados,
        data_entrega_real=entregue,
        _banca=banca,
    )


def projeto(status="em_andamento", data_kickoff=None, dias_ambientacao=5):
    """Sem kickoff por padrão: o prazo do pedido cai na régua dos 3 dias úteis
    da largada, que é a que a maioria destes testes mede."""
    return SimpleNamespace(
        id=3,
        status=status,
        data_kickoff=data_kickoff,
        data_inicio_ambientacao=None,
        dias_ambientacao=dias_ambientacao,
    )


@pytest.fixture
def cronograma(monkeypatch):
    """`(criar, mover, estado)` com os repositórios trocados por dublês."""

    def _montar(alvo=None, dono=None):
        alvo = alvo if alvo is not None else escopo()
        dono = dono if dono is not None else projeto()
        estado = SimpleNamespace(criadas=[], movidas=[])

        class EtapaFake:
            def __init__(self, db): pass
            def get_by_id(self, _id):
                return SimpleNamespace(id=_id, projeto_escopo_id=alvo.id)
            def proxima_ordem(self, _id): return 1
            def create(self, **campos):
                estado.criadas.append(campos)
                return SimpleNamespace(id=99, **campos)
            def update(self, _id, **campos):
                estado.movidas.append(campos)
                return SimpleNamespace(id=_id, **campos)

        class EscopoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return alvo
            # A lista do projeto: é ela que diz se `alvo` é o PRIMEIRO escopo
            # vendido e, portanto, se o prazo do pedido é o do kickoff.
            def get_by_projeto(self, _id): return [alvo]

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return dono

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, _id):
                return getattr(alvo, "_banca", None)

        class DiaNaoLetivoFake:
            def __init__(self, db): pass
            def get_all(self): return [SimpleNamespace(data=d) for d in CALENDARIO]
            # O calendário deste projeto. Sem variantes no fake, é o mesmo
            # `get_all()` — o que muda na produção é só o corte por curso.
            def get_do_escopo(self, _escopo): return self.get_all()

        class HistoricoFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id): return []

        for nome, fake in [
            ("CronogramaEtapaRepository", EtapaFake),
            ("ProjetoEscopoRepository", EscopoFake),
            ("ProjetoRepository", ProjetoFake),
            ("BancaRepository", BancaFake),
            ("DiaNaoLetivoRepository", DiaNaoLetivoFake),
            ("ProjetoStatusHistoricoRepository", HistoricoFake),
        ]:
            monkeypatch.setattr(update_cronograma, nome, fake)

        def criar(inicio, fim):
            return CreateEtapaUseCase(db=None).execute(
                alvo.id,
                EtapaRequest(nome="Entrevistas", cor="#397AD0", data_inicio=inicio, data_fim=fim),
                criado_por=1,
            )

        def mover(inicio, fim):
            return UpdateEtapaIntervaloUseCase(db=None).execute(
                42, EtapaIntervaloRequest(data_inicio=inicio, data_fim=fim)
            )

        return criar, mover, estado

    return _montar


class TestDentroDaJanela:
    def test_a_etapa_que_cabe_passa(self, cronograma):
        criar, _, estado = cronograma()

        criar(date(2026, 9, 8), date(2026, 9, 11))

        assert len(estado.criadas) == 1

    def test_o_ultimo_dia_da_janela_cabe(self, cronograma):
        criar, _, estado = cronograma()

        criar(date(2026, 9, 29), FIM_DA_JANELA)

        assert len(estado.criadas) == 1

    def test_dias_ajustados_ampliam_onde_a_etapa_cabe(self, cronograma):
        """⭐ O efeito prático do pedido: a mesma pincelada recusada passa."""
        criar, _, _ = cronograma()
        with pytest.raises(RegraDeNegocioError):
            criar(date(2026, 10, 5), date(2026, 10, 7))

        criar_com_ajuste, _, estado = cronograma(escopo(ajustados=10))
        criar_com_ajuste(date(2026, 10, 5), date(2026, 10, 7))
        assert len(estado.criadas) == 1


class TestForaDaJanela:
    def test_criar_fora_da_janela_e_recusado(self, cronograma):
        criar, _, estado = cronograma()

        with pytest.raises(RegraDeNegocioError, match="caber na janela"):
            criar(date(2026, 10, 1), date(2026, 10, 2))

        assert estado.criadas == []

    def test_arrastar_para_fora_tambem_e_recusado(self, cronograma):
        """O arrasto é o jeito mais fácil de sair da janela sem perceber — a
        trava não pode existir só na criação."""
        _, mover, estado = cronograma()

        with pytest.raises(RegraDeNegocioError, match="caber na janela"):
            mover(date(2026, 9, 8), date(2026, 10, 20))

        assert estado.movidas == []

    def test_comecar_antes_da_largada_tambem_nao(self, cronograma):
        criar, _, _ = cronograma()

        with pytest.raises(RegraDeNegocioError, match="caber na janela"):
            criar(date(2026, 9, 1), date(2026, 9, 4))

    def test_a_mensagem_diz_onde_a_janela_termina(self, cronograma):
        """Sem a data, a pessoa fica tentando dias até acertar."""
        criar, _, _ = cronograma()

        with pytest.raises(RegraDeNegocioError, match="01/10/2026"):
            criar(date(2026, 10, 5), date(2026, 10, 6))

    def test_dentro_do_prazo_a_mensagem_oferece_o_pedido(self, cronograma):
        """3 dias úteis a partir da largada: a saída existe e é dita."""
        criar, _, _ = cronograma()

        with pytest.raises(RegraDeNegocioError, match="Peça dias de ajuste"):
            # `referencia` do prazo é hoje; com a largada em 2026 o prazo ainda
            # não começou, e o §20.1 diz que antes dele o pedido está aberto.
            criar(date(2026, 10, 5), date(2026, 10, 6))

    def test_primeiro_escopo_com_ambientacao_vencida_nao_ganha_a_oferta(self, cronograma):
        """⭐ A mensagem segue a régua do escopo, não uma régua só.

        Este escopo é o primeiro da lista, e o prazo dele acabou junto com a
        ambientação (kickoff em 2020, muito antes de hoje). Oferecer "peça
        dias" aqui mandaria o coordenador a um pedido que `solicitar` recusa.
        """
        criar, _, _ = cronograma(
            dono=projeto(data_kickoff=date(2020, 1, 6))
        )

        with pytest.raises(RegraDeNegocioError, match="já venceu"):
            criar(date(2026, 10, 5), date(2026, 10, 6))


class TestSemJanela:
    def test_escopo_sem_reuniao_inicial_nao_aceita_etapa(self, cronograma):
        """A largada é o que abre a janela — sem ela não há onde pintar."""
        criar, _, _ = cronograma(
            SimpleNamespace(
                id=7, projeto_id=3, data_inicio=None,
                dias_uteis_vendidos=20, dias_uteis_ajustados=0, data_entrega_real=None,
            )
        )

        with pytest.raises(RegraDeNegocioError, match="reunião inicial"):
            criar(date(2026, 9, 8), date(2026, 9, 11))


class TestAjustesDepoisDaBanca:
    """⭐ Realizada a banca, o cronograma daquele escopo vira território de
    AJUSTES — e ajuste não cabe na janela por definição.

    O gatilho é a banca, não a entrega: é entre uma e outra que os ajustes
    pedidos pela banca acontecem. Barrar aí impediria registrar no calendário
    exatamente o trabalho que a avaliação gerou.
    """

    def test_banca_realizada_libera_etapa_fora_da_janela(self, cronograma):
        realizada = SimpleNamespace(id=50, realizado_em=date(2026, 9, 25))
        criar, _, estado = cronograma(escopo(banca=realizada))

        criar(date(2026, 10, 5), date(2026, 10, 9))

        assert len(estado.criadas) == 1

    def test_banca_apenas_marcada_nao_libera(self, cronograma):
        """Marcada não é realizada: até ela acontecer, o trabalho vendido ainda
        está correndo e a janela continua valendo."""
        marcada = SimpleNamespace(id=50, realizado_em=None)
        criar, _, _ = cronograma(escopo(banca=marcada))

        with pytest.raises(RegraDeNegocioError, match="caber na janela"):
            criar(date(2026, 10, 5), date(2026, 10, 9))

    def test_escopo_entregue_tambem_libera(self, cronograma):
        """Consequência, não regra à parte: o §5.5 só libera a entrega depois
        da banca — quando ela existe, a exceção da banca já valia."""
        criar, _, estado = cronograma(escopo(entregue=date(2026, 9, 25)))

        criar(date(2026, 10, 5), date(2026, 10, 9))

        assert len(estado.criadas) == 1

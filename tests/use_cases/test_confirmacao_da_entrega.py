"""A confirmação da entrega — o único ato que move o escopo para "Entregue".

⭐ **Por que existe um passo além da data.** Os dois já foram a mesma escrita:
gravar `data_entrega_real` no cronograma virava o status na mesma linha. Só que
a data é campo de calendário — editável, corrigível, clicável por engano — e o
status na tabela de escopos é lido como uma afirmação: *este trabalho foi ao
cliente*. Um clique num dia passava por declaração.

Agora a data é registro, e o status espera alguém dizer "sim, entregamos".

⚠ **Quem confirma é vínculo, não cargo**: o coordenador DAQUELE projeto ou a
diretoria. Um coordenador de outro projeto não confirma este — por isso a
checagem mora no use case, que tem a equipe à mão, e não numa dependência de
posição na rota.

Dublês à mão + `monkeypatch` das classes de repositório no módulo — mesmo
idioma de `test_entrega_autorizada.py`.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.projeto_escopo import update_escopo_projeto
from src.use_cases.projeto_escopo.update_escopo_projeto import (
    ConfirmarEntregaEscopoRequest,
    ConfirmarEntregaEscopoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

QUI_03_09 = date(2026, 9, 3)
QUI_15_10 = date(2026, 10, 15)

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
BRUNO = SimpleNamespace(id=11, nome="Bruno Lima", posicao="coordenador")
CAIO = SimpleNamespace(id=12, nome="Caio Reis", posicao="consultor")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


@pytest.fixture
def confirmar(monkeypatch):
    """`(executar, estado)` — `estado.gravado` mostra o que foi para o banco."""

    def _montar(
        *,
        data_entrega=QUI_15_10,
        status="em_andamento",
        resultado="aprovada",
        banca_realizada=True,
        tem_banca=True,
    ):
        estado = SimpleNamespace(gravado={}, avancou=[], alteracoes=[])
        escopo = SimpleNamespace(
            id=7,
            projeto_id=3,
            status=status,
            data_inicio=QUI_03_09,
            data_entrega_real=data_entrega,
            entrega_confirmada_em=None,
            entrega_confirmada_por=None,
        )

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return escopo
            def update(self, _id, **campos):
                estado.gravado.update(campos)
                for k, v in campos.items():
                    setattr(escopo, k, v)
                return escopo

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, _id):
                if not tem_banca:
                    return None
                return SimpleNamespace(
                    id=50,
                    realizado_em=QUI_15_10 if banca_realizada else None,
                    resultado=resultado,
                )

        class MembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id, apenas_atuais=False):
                return [
                    SimpleNamespace(usuario_id=ANA.id, papel="coordenador"),
                    SimpleNamespace(usuario_id=CAIO.id, papel="consultor"),
                ]

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None  # sem projeto, não notifica

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None

        class AlteracaoFake:
            def __init__(self, db): pass
            def create(self, **campos):
                estado.alteracoes.append(campos)
                return SimpleNamespace(id=1, **campos)

        class AvancarFake:
            def __init__(self, db): pass
            def executar_para(self, projeto_id): estado.avancou.append(projeto_id)

        for nome, fake in [
            ("ProjetoEscopoRepository", EscopoProjetoFake),
            ("BancaRepository", BancaFake),
            ("ProjetoMembroRepository", MembroFake),
            ("ProjetoRepository", ProjetoFake),
            ("EscopoRepository", CatalogoFake),
            ("EntregaAlteracaoRepository", AlteracaoFake),
        ]:
            monkeypatch.setattr(update_escopo_projeto, nome, fake)
        # O avanço automático é importado dentro do método (import tardio para
        # evitar ciclo), então o alvo do patch é o módulo de origem.
        monkeypatch.setattr(
            "src.use_cases.projeto.avancar_status.AvancarStatusAutomaticoUseCase",
            AvancarFake,
        )

        uc = ConfirmarEntregaEscopoUseCase(db=None)

        def executar(quem=ANA, dia=None):
            return uc.execute(
                escopo.id,
                quem,
                eh_diretor_projetos=quem.posicao == "diretor_projetos",
                request=ConfirmarEntregaEscopoRequest(data_entrega_real=dia),
            )

        return executar, estado

    return _montar


class TestQuemPodeConfirmar:
    """Vínculo com o projeto, não posição no organograma."""

    def test_o_coordenador_do_projeto_confirma(self, confirmar):
        executar, estado = confirmar()

        resposta = executar(ANA)

        assert estado.gravado["status"] == "entregue"
        assert estado.gravado["entrega_confirmada_por"] == ANA.id
        assert resposta["status"] == "entregue"

    def test_a_diretoria_confirma_sem_estar_no_projeto(self, confirmar):
        """Dani não é membro — a diretoria responde por qualquer projeto."""
        executar, estado = confirmar()

        executar(DANI)

        assert estado.gravado["entrega_confirmada_por"] == DANI.id

    def test_coordenador_de_outro_projeto_nao_confirma(self, confirmar):
        """⭐ O caso que motiva a checagem por equipe: Bruno tem o cargo, mas
        não é o coordenador DESTE projeto."""
        executar, estado = confirmar()

        with pytest.raises(RegraDeNegocioError, match="coordenador do projeto"):
            executar(BRUNO)

        assert estado.gravado == {}

    def test_consultor_do_projeto_nao_confirma(self, confirmar):
        """Estar na equipe não basta — quem responde pela entrega é quem
        coordena."""
        executar, _ = confirmar()

        with pytest.raises(RegraDeNegocioError, match="coordenador do projeto"):
            executar(CAIO)


class TestATravaDaBanca:
    """🔒 §5.5 inteiro, repetido nesta porta de propósito.

    Não delegado à marcação da data: esta é a porta que de fato muda o estado
    do escopo, e uma trava que mora só na outra porta é uma trava com dois
    caminhos.
    """

    def test_sem_banca_marcada_nao_confirma(self, confirmar):
        executar, estado = confirmar(tem_banca=False)

        with pytest.raises(RegraDeNegocioError, match="banca marcada"):
            executar()

        assert estado.gravado == {}

    def test_banca_nao_realizada_nao_confirma(self, confirmar):
        executar, _ = confirmar(banca_realizada=False)

        with pytest.raises(RegraDeNegocioError, match="não foi realizada"):
            executar()

    def test_banca_sem_resultado_nao_confirma(self, confirmar):
        """Ninguém votou ainda: pendente não é aprovado."""
        executar, _ = confirmar(resultado=None)

        with pytest.raises(RegraDeNegocioError, match="ainda não tem resultado"):
            executar()

    def test_banca_reprovada_nao_confirma(self, confirmar):
        """E a mensagem aponta a saída — marcar a segunda banca."""
        executar, _ = confirmar(resultado="nao_aprovada")

        with pytest.raises(RegraDeNegocioError, match="nova banca"):
            executar()


class TestOEstadoDoEscopo:
    def test_sem_data_nenhuma_nao_ha_o_que_confirmar(self, confirmar):
        """⚠ Confirmar sem data deixaria o escopo entregue sem dizer quando."""
        executar, _ = confirmar(data_entrega=None)

        with pytest.raises(RegraDeNegocioError, match="Informe o dia"):
            executar()

    def test_a_data_pode_chegar_junto_com_a_confirmacao(self, confirmar):
        """⭐ Sem isto, confirmar exigia ir ao Cronograma, voltar e clicar de
        novo — dois gestos em duas telas para um fato só."""
        executar, estado = confirmar(data_entrega=None)

        executar(dia=QUI_15_10)

        assert estado.gravado["data_entrega_real"] == QUI_15_10
        assert estado.gravado["status"] == "entregue"

    def test_a_data_que_chega_junto_entra_no_historico(self, confirmar):
        """Reaproveita a marcação: uma entrega confirmada por aqui deixa o
        mesmo rastro que uma marcada no calendário."""
        executar, estado = confirmar(data_entrega=None)

        executar(dia=QUI_15_10)

        (registro,) = estado.alteracoes
        assert registro["data_anterior"] is None
        assert registro["data_nova"] == QUI_15_10

    def test_a_data_que_chega_junto_respeita_o_inicio_do_escopo(self, confirmar):
        """A borda da marcação vale aqui: a data passa pela mesma porta, então
        entregar antes de começar continua impossível."""
        executar, estado = confirmar(data_entrega=None)

        with pytest.raises(RegraDeNegocioError, match="anterior ao início"):
            executar(dia=QUI_03_09.replace(day=1))

        assert estado.gravado == {}

    def test_data_ja_marcada_ignora_o_dia_informado(self, confirmar):
        """⚠ Mudar entrega registrada é do §13 (diretoria + justificativa), e
        tem porta própria — a confirmação não pode virar um atalho para isso."""
        executar, estado = confirmar(data_entrega=QUI_15_10)

        executar(dia=QUI_15_10.replace(day=22))

        assert "data_entrega_real" not in estado.gravado
        assert estado.alteracoes == []

    def test_confirmar_duas_vezes_e_recusado(self, confirmar):
        """Senão o segundo clique reescreveria quem confirmou e quando."""
        executar, _ = confirmar(status="entregue")

        with pytest.raises(RegraDeNegocioError, match="já foi confirmada"):
            executar()

    def test_escopo_cancelado_nao_entrega(self, confirmar):
        executar, _ = confirmar(status="cancelado")

        with pytest.raises(RegraDeNegocioError, match="cancelado"):
            executar()


class TestOProjetoAndaJunto:
    """🤖 §4: com todos os escopos entregues, o projeto vai a Período de ajustes.

    O gatilho mudou junto com a regra — era a data, agora é a confirmação, que é
    quem diz que o escopo acabou.
    """

    def test_confirmar_dispara_o_avanco_do_projeto(self, confirmar):
        executar, estado = confirmar()

        executar()

        assert estado.avancou == [3]

    def test_falha_no_avanco_nao_derruba_a_confirmacao(self, confirmar, monkeypatch):
        """⚠ A entrega já foi gravada quando o avanço roda: deixar a exceção
        subir devolveria 500 para uma confirmação que aconteceu."""
        executar, estado = confirmar()

        class ExplodeFake:
            def __init__(self, db): pass
            def executar_para(self, _id): raise RuntimeError("banco caiu")

        monkeypatch.setattr(
            "src.use_cases.projeto.avancar_status.AvancarStatusAutomaticoUseCase",
            ExplodeFake,
        )

        resposta = executar()

        assert resposta["status"] == "entregue"
        assert estado.gravado["status"] == "entregue"

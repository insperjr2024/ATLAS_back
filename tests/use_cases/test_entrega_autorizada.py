"""§13: marcar a entrega é livre; MUDAR uma entrega já registrada é da diretoria.

A assimetria é o ponto inteiro. Registrar a entrega é o passo em que o
coordenador fecha o escopo no cronograma — travá-lo faria o time depender da
diretoria para anotar o que já aconteceu. Mudar a data depois é outra coisa: a
data que o cliente ouviu vira outra, e sem gate um escopo entregue com atraso
podia ter a data empurrada em silêncio até o atraso sumir do monitoramento.

⭐ **Existe UMA entrega, não duas.** "Entrega ao cliente" e "entrega do escopo"
são a mesma coisa: o cliente recebe quando o escopo é entregue. A do projeto é
derivada da última — não há data própria para ela.

⚠ E, diferente da banca, a entrega **não** precisa caber na janela do escopo: a
janela é o tempo de TRABALHO vendido, e a apresentação ao cliente costuma
acontecer dias depois da banca.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch` —
mesmo idioma de `test_banca_na_janela.py`.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.projeto_escopo import update_escopo_projeto
from src.use_cases.projeto_escopo.update_escopo_projeto import (
    RegistrarEntregaEscopoRequest,
    RegistrarEntregaEscopoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

QUI_03_09 = date(2026, 9, 3)
QUI_15_10 = date(2026, 10, 15)
QUI_22_10 = date(2026, 10, 22)

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


@pytest.fixture
def entregar_escopo(monkeypatch):
    """`(executar, estado)` — `estado.alteracoes` mostra o que foi registrado."""

    def _montar(entrega_atual=None, *, banca_realizada=True, resultado="aprovada"):
        estado = SimpleNamespace(alteracoes=[], gravado={})
        escopo = SimpleNamespace(
            id=7,
            projeto_id=3,
            escopo_id=None,
            nome_customizado="Elaboração Contratual",
            data_inicio=QUI_03_09,
            data_entrega_real=entrega_atual,
            # ⭐ Marcar a data deixou de mover o status: quem faz isso é a
            # CONFIRMAÇÃO da entrega, que tem porta e teste próprios.
            status="em_andamento",
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
                if not banca_realizada:
                    return None
                return SimpleNamespace(id=50, realizado_em=QUI_15_10, resultado=resultado)

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

        for nome, fake in [
            ("ProjetoEscopoRepository", EscopoProjetoFake),
            ("BancaRepository", BancaFake),
            ("ProjetoRepository", ProjetoFake),
            ("EscopoRepository", CatalogoFake),
            ("EntregaAlteracaoRepository", AlteracaoFake),
        ]:
            monkeypatch.setattr(update_escopo_projeto, nome, fake)

        uc = RegistrarEntregaEscopoUseCase(db=None)

        def executar(data=QUI_15_10, quem=ANA, justificativa=None):
            return uc.execute(
                escopo.id,
                RegistrarEntregaEscopoRequest(
                    data_entrega_real=data, justificativa=justificativa
                ),
                eh_diretor_projetos=quem.posicao == "diretor_projetos",
                current_user=quem,
            )

        return executar, estado

    return _montar


class TestEntregaDoEscopo:
    def test_a_primeira_marcacao_e_livre(self, entregar_escopo):
        """O passo normal do fluxo: o coordenador fecha o escopo sozinho."""
        executar, estado = entregar_escopo()

        resposta = executar()

        assert resposta["data_entrega_real"] == QUI_15_10
        # ⚠ A data grava, mas NÃO move o status — isso agora é da confirmação.
        assert "status" not in estado.gravado

    def test_a_primeira_marcacao_entra_no_historico(self, entregar_escopo):
        """Com `data_anterior` nula — é o "de onde veio" da promessa."""
        executar, estado = entregar_escopo()

        executar()

        (registro,) = estado.alteracoes
        assert registro["data_anterior"] is None
        assert registro["data_nova"] == QUI_15_10
        # Ninguém autorizou porque ninguém precisou.
        assert registro["autorizado_por"] is None

    def test_mudar_uma_entrega_registrada_barra_o_coordenador(self, entregar_escopo):
        """A mensagem diz a data que já valia — senão a pessoa não sabe o que
        está tentando sobrescrever."""
        executar, _ = entregar_escopo(entrega_atual=QUI_15_10)

        with pytest.raises(RegraDeNegocioError, match="diretoria"):
            executar(data=QUI_22_10)

    def test_a_diretoria_muda_com_justificativa(self, entregar_escopo):
        executar, estado = entregar_escopo(entrega_atual=QUI_15_10)

        executar(data=QUI_22_10, quem=DANI, justificativa="Agenda do cliente")

        (registro,) = estado.alteracoes
        assert registro["data_anterior"] == QUI_15_10
        assert registro["data_nova"] == QUI_22_10
        assert registro["autorizado_por"] == DANI.id

    def test_a_diretoria_tambem_precisa_justificar(self, entregar_escopo):
        executar, _ = entregar_escopo(entrega_atual=QUI_15_10)

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(data=QUI_22_10, quem=DANI)

    def test_salvar_a_mesma_data_nao_e_alteracao(self, entregar_escopo):
        """Reenviar o mesmo dia não pode pedir diretoria nem virar linha no
        Histórico."""
        executar, estado = entregar_escopo(entrega_atual=QUI_15_10)

        executar(data=QUI_15_10)

        assert estado.alteracoes == []

    def test_a_trava_do_5_5_continua_de_pe(self, entregar_escopo):
        """O gate novo não substitui o antigo: sem banca realizada, nada vai ao
        cliente."""
        executar, _ = entregar_escopo(banca_realizada=False)

        with pytest.raises(RegraDeNegocioError, match="banca"):
            executar()


class TestOResultadoDaBancaDestrava:
    """🔒 §5.5 na íntegra: não basta a banca acontecer, ela precisa APROVAR.

    Esta exigência já existiu, foi removida quando o resultado virou um campo
    que ninguém tinha como preencher — não havia UI para registrá-lo — e volta
    agora que o veredito sai do voto dos avaliadores.
    """

    def test_banca_aprovada_libera(self, entregar_escopo):
        executar, estado = entregar_escopo(resultado="aprovada")

        executar()

        # ⚠ A data grava, mas NÃO move o status — isso agora é da confirmação.
        assert "status" not in estado.gravado

    def test_banca_reprovada_trava(self, entregar_escopo):
        """⭐ O caso que motivou a mudança: reprovar não pode liberar o cliente.

        A saída é marcar uma segunda banca — e a mensagem precisa dizer isso,
        senão o coordenador fica sem próximo passo.
        """
        executar, estado = entregar_escopo(resultado="nao_aprovada")

        with pytest.raises(RegraDeNegocioError, match="nova banca"):
            executar()

        assert estado.gravado == {}

    def test_sem_resultado_ainda_trava(self, entregar_escopo):
        """Banca realizada e ninguém votou: pendente não é aprovado.

        Mas a mensagem aponta a saída — a diretoria pode registrar o resultado
        quando o prazo vence sem voto nenhum.
        """
        executar, _ = entregar_escopo(resultado=None)

        with pytest.raises(RegraDeNegocioError, match="ainda não tem resultado"):
            executar()

    def test_reprovada_nao_registra_alteracao(self, entregar_escopo):
        """A trava vem ANTES do histórico: uma entrega barrada não pode deixar
        rastro de que aconteceu."""
        executar, estado = entregar_escopo(resultado="nao_aprovada")

        with pytest.raises(RegraDeNegocioError, match="nova banca"):
            executar()

        assert estado.alteracoes == []

    def test_corrigir_entrega_ja_registrada_nao_passa_pela_trava(self, entregar_escopo):
        """⚠ A trava vale para a PRIMEIRA marcação, não para a correção.

        Sem este recorte, a diretoria não conseguiria acertar a data de um
        escopo já entregue — 422 sobre fato consumado, inclusive nos escopos
        entregues antes desta regra existir. Quem governa a correção é o §13
        (diretoria + justificativa), que já roda antes daqui.
        """
        executar, estado = entregar_escopo(QUI_15_10, resultado="nao_aprovada")

        executar(data=QUI_15_10.replace(day=16), quem=DANI, justificativa="Data errada no registro")

        assert estado.gravado["data_entrega_real"] == QUI_15_10.replace(day=16)
        assert len(estado.alteracoes) == 1

    def test_corrigir_sem_ser_diretor_continua_barrado(self, entregar_escopo):
        """O §13 não afrouxa junto: o recorte acima tira a trava da banca do
        caminho, não o gate da diretoria."""
        executar, _ = entregar_escopo(QUI_15_10, resultado="aprovada")

        with pytest.raises(RegraDeNegocioError):
            executar(data=QUI_15_10.replace(day=16))


class TestEntregaForaDaJanela:
    """A entrega pode cair DEPOIS do fim da janela do escopo — a banca não.

    O exemplo que a diretoria deu: escopo com janela até o dia 20, banca no dia
    20, entrega no dia 23. A janela mede o trabalho vendido; a apresentação ao
    cliente vem depois dela, e barrar isso obrigaria a mentir a data ou a
    "gastar" janela com uma reunião que não é trabalho.
    """

    def test_entrega_depois_do_fim_da_janela_passa(self, entregar_escopo):
        executar, estado = entregar_escopo()

        # A janela do dublê termina bem antes; nenhuma validação de janela
        # deve existir neste caminho.
        resposta = executar(data=date(2026, 12, 23))

        assert resposta["data_entrega_real"] == date(2026, 12, 23)
        # ⚠ A data grava, mas NÃO move o status — isso agora é da confirmação.
        assert "status" not in estado.gravado

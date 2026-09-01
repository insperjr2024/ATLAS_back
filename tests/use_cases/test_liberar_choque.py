"""⭐ A diretoria concedendo a exceção de choque (§8) dentro de outra decisão.

O desenho normal do §8 são dois atores: **quem marca pede**, **a diretoria
decide**. `liberar_choque` é a exceção a esse par, e ela existe porque numa
situação os dois atores são a MESMA pessoa: a diretoria decidindo um pedido de
banca fora da janela (§13) cuja data esbarra na banca de outro projeto. As duas
regras cobram `require_diretor_projetos`, então exigir que ela peça a si mesma
não protegia ninguém — só travava a decisão num beco sem saída.

O que este arquivo prende:

- **Grava uma linha de verdade**, com status `aprovada`, em vez de contornar o
  `checar_choque`. É essa linha que `get_aprovada` encontra depois, e é ela que
  deixa a exceção no histórico como qualquer outra.
- **Não inventa exceção para horário livre** — sem conflito, não há o que
  liberar.
- **Responde o pedido pendente**, quando quem marca já tinha pedido, em vez de
  deixar um órfão na fila sobre um choque já liberado.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch`,
mesmo idioma de `test_banca_fora_da_janela.py`.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import excecao_choque
from src.use_cases.banca.excecao_choque import liberar_choque

QUANDO = datetime(2026, 10, 8, 15, 0)

ANA = SimpleNamespace(id=10, nome="Ana Souza")
DANI = SimpleNamespace(id=1, nome="Dani Alves")

#: A banca que já ocupa o horário — o PIRATININGA I do caso real.
OUTRA = SimpleNamespace(id=41, nome_projeto="PIRATININGA I", excecao_choque_por=None)


@pytest.fixture
def liberar(monkeypatch):
    """Devolve `(executar, estado)` — `estado` mostra o que foi gravado."""

    def _montar(*, conflitantes=(OUTRA,), aprovada=None, pendente=None, banca_do_escopo=None):
        estado = SimpleNamespace(criados=[], atualizados=[])

        class ExcecaoFake:
            def __init__(self, db):
                pass

            def get_aprovada(self, _escopo_id, _data_hora):
                return aprovada

            def get_pendente_do_par(self, _escopo_id, _data_hora):
                return pendente

            def create(self, **campos):
                estado.criados.append(campos)
                return SimpleNamespace(id=123, **campos)

            def update(self, pedido_id, **campos):
                estado.atualizados.append((pedido_id, campos))
                return SimpleNamespace(id=pedido_id, **campos)

        class BancaFake:
            def __init__(self, db):
                pass

            def get_por_data_hora(self, _data_hora):
                return list(conflitantes)

            def get_by_projeto_escopo(self, _escopo_id):
                return banca_do_escopo

        monkeypatch.setattr(excecao_choque, "BancaExcecaoChoqueRepository", ExcecaoFake)
        monkeypatch.setattr(excecao_choque, "BancaRepository", BancaFake)

        def executar(projeto_escopo_id=7):
            return liberar_choque(
                db=None,
                projeto_escopo_id=projeto_escopo_id,
                data_hora=QUANDO,
                solicitado_por=ANA.id,
                respondido_por=DANI.id,
                justificativa="Cronograma acordado com o cliente",
                resposta="Autorizado junto com a data fora da janela",
            )

        return executar, estado

    return _montar


class TestLiberarChoque:
    def test_grava_a_excecao_aprovada_apontando_a_banca_conflitante(self, liberar):
        executar, estado = liberar()

        executar()

        assert len(estado.criados) == 1
        criado = estado.criados[0]
        assert criado["status"] == "aprovada"
        assert criado["projeto_escopo_id"] == 7
        assert criado["data_hora_pretendida"] == QUANDO
        assert criado["banca_conflitante_id"] == OUTRA.id
        # Quem PEDIU é quem pediu a banca; quem RESPONDEU é a diretoria.
        assert criado["solicitado_por"] == ANA.id
        assert criado["respondido_por"] == DANI.id

    def test_horario_livre_nao_vira_excecao(self, liberar):
        """⚠ Sem conflito não há o que liberar — escrever a linha inventaria
        uma exceção para um horário que nunca precisou dela."""
        executar, estado = liberar(conflitantes=())

        assert executar() is None
        assert estado.criados == []

    def test_escopo_ausente_nao_libera_nada(self, liberar):
        """Banca legada, sem escopo vendido: não há par de quem derivar a
        exceção. Mesma postura conservadora do `checar_choque`."""
        executar, estado = liberar()

        assert executar(projeto_escopo_id=None) is None
        assert estado.criados == []

    def test_ja_liberado_nao_grava_de_novo(self, liberar):
        ja = SimpleNamespace(id=55, status="aprovada")
        executar, estado = liberar(aprovada=ja)

        assert executar() is ja
        assert estado.criados == []

    def test_pedido_pendente_e_respondido_em_vez_de_duplicado(self, liberar):
        """⭐ Sem isto, a fila da diretoria ficaria com um pendente órfão sobre
        um choque que ela mesma acabou de liberar."""
        executar, estado = liberar(pendente=SimpleNamespace(id=88, status="pendente"))

        executar()

        assert estado.criados == []
        assert len(estado.atualizados) == 1
        pedido_id, campos = estado.atualizados[0]
        assert pedido_id == 88
        assert campos["status"] == "aprovada"
        assert campos["respondido_por"] == DANI.id

    def test_a_propria_banca_do_escopo_nao_choca_consigo_mesma(self, liberar):
        """Remarcar a banca do escopo para o mesmo horário não é choque."""
        propria = SimpleNamespace(id=41, nome_projeto="LOTEAMENTOS I", excecao_choque_por=None)
        executar, estado = liberar(conflitantes=(propria,), banca_do_escopo=propria)

        assert executar() is None
        assert estado.criados == []

    def test_banca_com_excecao_legada_nao_conta_como_conflito(self, liberar):
        """A flag antiga segue respeitada, como no `checar_choque` — nada novo
        a escreve, mas as liberações já concedidas continuam valendo."""
        legada = SimpleNamespace(id=42, nome_projeto="ANTIGO", excecao_choque_por=DANI.id)
        executar, estado = liberar(conflitantes=(legada,))

        assert executar() is None
        assert estado.criados == []

"""⭐ Editar os escopos de uma banca já criada (2026-09-01).

Antes só a marcação pelo cronograma escolhia quais escopos uma banca cobre; a
tela de Bancas editava nome, data e coordenador e nada mais. Quem juntasse os
escopos errados tinha de excluir a banca e remarcar do zero.

A lista SUBSTITUI a atual — o que não vem é removido. Três coisas são
protegidas aqui:

- **As frentes acompanham os escopos.** A banca é das frentes do trabalho que
  ela avalia (§8), e é isso que decide o piso que a composição cobra. Sem
  remover a frente do escopo que saiu, a banca ficaria impossível de fechar.
- **Escopo com banca própria não é roubado** — a regra compartilhada com a
  marcação (`utils/escopos_da_banca`), que existe porque o escopo tem no
  máximo uma banca.
- **Banca com escopos não fica sem nenhum**: esvaziá-la a deixaria órfã.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.banca.update_banca import UpdateBancaRequest, UpdateBancaUseCase
from src.utils.exceptions import RegraDeNegocioError

BUSINESS, DIREITO, TECH = 1, 2, 3


def escopo(id_, frente_id, projeto_id=7, nome="Escopo"):
    return SimpleNamespace(
        id=id_,
        projeto_id=projeto_id,
        frente_id=frente_id,
        nome_customizado=nome,
        escopo_id=None,
    )


@pytest.fixture
def editar(monkeypatch):
    """`(executar, estado)` com os repositórios trocados por dublês.

    O mundo: projeto 7 com Análise e Diagnóstico (Business), Contratual
    (Direito) e Plataforma (Tech). A banca 50 cobre Análise e Contratual. O
    escopo 99 é de OUTRO projeto; o 30 já tem a banca 60.
    """

    def _montar(escopos_da_banca=(10, 20), frentes_da_banca=(BUSINESS, DIREITO)):
        mundo = {
            10: escopo(10, BUSINESS, nome="Análise"),
            15: escopo(15, BUSINESS, nome="Diagnóstico"),
            20: escopo(20, DIREITO, nome="Contratual"),
            25: escopo(25, TECH, nome="Plataforma"),
            30: escopo(30, BUSINESS, nome="Já tem banca"),
            99: escopo(99, BUSINESS, projeto_id=8, nome="De outro projeto"),
        }
        estado = SimpleNamespace(
            escopos=list(escopos_da_banca),
            frentes=[
                SimpleNamespace(id=100 + f, frente_id=f) for f in frentes_da_banca
            ],
            notificados=[],
        )
        banca = SimpleNamespace(
            id=50, nome_projeto="BLEND", escopo_id=None, coordenador_id=None,
            data_hora=None, realizado_em=None, resultado=None,
            piso_minimo_override=None,
        )

        class BancaFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return banca if _id == banca.id else None
            def update(self, _id, **campos):
                for k, v in campos.items():
                    setattr(banca, k, v)
                return banca

        class BancaEscopoFake:
            def __init__(self, db): pass
            def get_escopo_ids(self, _id): return list(estado.escopos)
            def get_banca_id(self, escopo_id):
                if escopo_id == 30:
                    return 60
                return banca.id if escopo_id in estado.escopos else None
            def definir(self, _id, ids): estado.escopos = list(ids)

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return mundo.get(_id)

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None

        class BancaFrenteFake:
            def __init__(self, db): pass
            def get_by_banca(self, _id): return list(estado.frentes)
            def create(self, banca_id, frente_id):
                novo = SimpleNamespace(id=100 + frente_id, frente_id=frente_id)
                estado.frentes.append(novo)
                return novo
            def delete(self, vinculo_id):
                estado.frentes = [f for f in estado.frentes if f.id != vinculo_id]
                return True

        from src.use_cases.banca import update_banca as mod
        monkeypatch.setattr(mod, "BancaRepository", BancaFake)
        monkeypatch.setattr(mod, "BancaEscopoRepository", BancaEscopoFake)
        monkeypatch.setattr(mod, "ProjetoEscopoRepository", EscopoProjetoFake)
        monkeypatch.setattr(mod, "EscopoRepository", CatalogoFake)
        monkeypatch.setattr(mod, "BancaFrenteRepository", BancaFrenteFake)
        monkeypatch.setattr(mod, "notificar_alocados",
                            lambda db, b, msg: estado.notificados.append(msg))

        def executar(**campos):
            return UpdateBancaUseCase(db=None).execute(50, UpdateBancaRequest(**campos))

        estado.frente_ids = lambda: sorted(f.frente_id for f in estado.frentes)
        return executar, estado

    return _montar


class TestAdicionarERemover:
    def test_adicionar_um_escopo(self, editar):
        executar, estado = editar()

        executar(projeto_escopo_ids=[10, 20, 25])

        assert estado.escopos == [10, 20, 25]

    def test_remover_um_escopo(self, editar):
        executar, estado = editar()

        executar(projeto_escopo_ids=[10])

        assert estado.escopos == [10]

    def test_a_lista_substitui_e_nao_soma(self, editar):
        """Mandar só o 25 troca os dois antigos por ele — não vira [10,20,25]."""
        executar, estado = editar()

        executar(projeto_escopo_ids=[25])

        assert estado.escopos == [25]

    def test_repetido_no_pedido_entra_uma_vez(self, editar):
        executar, estado = editar()

        executar(projeto_escopo_ids=[10, 10, 20])

        assert estado.escopos == [10, 20]

    def test_sem_o_campo_os_escopos_nao_sao_tocados(self, editar):
        """Editar só o nome não pode mexer no vínculo."""
        executar, estado = editar()

        executar(nome_projeto="BLEND II")

        assert estado.escopos == [10, 20]


class TestAsFrentesAcompanham:
    def test_remover_o_escopo_de_direito_tira_a_frente(self, editar):
        """⭐ Sem isto a banca continuaria cobrando o piso de Direito de uma
        banca que não avalia mais nada de Direito — impossível de fechar."""
        executar, estado = editar()

        executar(projeto_escopo_ids=[10])

        assert estado.frente_ids() == [BUSINESS]

    def test_adicionar_escopo_de_tech_traz_a_frente(self, editar):
        executar, estado = editar()

        executar(projeto_escopo_ids=[10, 20, 25])

        assert estado.frente_ids() == [BUSINESS, DIREITO, TECH]

    def test_trocar_de_frente_de_uma_vez(self, editar):
        executar, estado = editar()

        executar(projeto_escopo_ids=[25])

        assert estado.frente_ids() == [TECH]

    def test_dois_escopos_da_mesma_frente_nao_duplicam_o_vinculo(self, editar):
        executar, estado = editar()

        executar(projeto_escopo_ids=[10, 15])

        assert estado.frente_ids() == [BUSINESS]
        assert estado.escopos == [10, 15]


class TestOQueNaoPassa:
    def test_escopo_de_outro_projeto(self, editar):
        executar, estado = editar()

        with pytest.raises(RegraDeNegocioError, match="mesmo projeto"):
            executar(projeto_escopo_ids=[10, 99])

        assert estado.escopos == [10, 20]

    def test_escopo_que_ja_tem_outra_banca(self, editar):
        """A mesma regra da marcação: o escopo tem no máximo uma banca."""
        executar, estado = editar()

        with pytest.raises(RegraDeNegocioError, match="já tem banca marcada"):
            executar(projeto_escopo_ids=[10, 30])

        assert estado.escopos == [10, 20]

    def test_escopo_inexistente(self, editar):
        executar, _ = editar()

        with pytest.raises(RegraDeNegocioError, match="não encontrado"):
            executar(projeto_escopo_ids=[10, 4242])

    def test_esvaziar_a_banca_nao_passa(self, editar):
        executar, estado = editar()

        with pytest.raises(RegraDeNegocioError, match="ao menos um escopo"):
            executar(projeto_escopo_ids=[])

        assert estado.escopos == [10, 20]

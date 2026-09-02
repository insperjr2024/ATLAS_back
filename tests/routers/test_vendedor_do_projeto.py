"""O vendedor: enxerga o que vendeu, e só de leitura.

Vendedor não é posição — é vínculo por projeto (`projeto_vendedor`). Quem
vende é um consultor, ou um coordenador comercial, que para a plataforma é a
mesma coisa. O que ele ganha é VISÃO; o que ele não ganha é escrita.

⭐ **O caso central é a assimetria entre ver e escrever.** As permissões da
plataforma são globais por posição: um consultor-vendedor tem
`pode_criar_tarefa` em qualquer projeto que enxergue. Se o acesso por venda
fosse igual aos outros, vender um projeto daria escrita nele — e ninguém
notaria, porque nenhuma tela mudaria de aparência.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.middlewares import authorization as auth


class ConsultaFake:
    """Devolve as linhas que o teste mandou, ignorando o filtro."""

    def __init__(self, linhas):
        self._linhas = list(linhas)

    def filter(self, *_):
        return self

    def first(self):
        return self._linhas[0] if self._linhas else None

    def all(self):
        return list(self._linhas)


class DbFake:
    """`query(Modelo)` devolve o que o mundo do teste registrou para ele."""

    def __init__(self, por_modelo):
        self._por_modelo = por_modelo

    def query(self, *alvos):
        chave = getattr(alvos[0], "class_", None) or alvos[0]
        nome = getattr(chave, "__name__", None) or getattr(
            getattr(alvos[0], "parent", None), "class_", type("x", (), {})
        ).__name__
        return ConsultaFake(self._por_modelo.get(nome, []))


@pytest.fixture
def mundo(monkeypatch):
    """Monta quem é da equipe, quem vendeu e de que frente é o projeto."""

    def _mundo(*, na_equipe=False, vendeu=False, do_gerente=False, ve_tudo=False):
        from src.models.projeto_frente_model import ProjetoFrenteModel
        from src.models.projeto_membro_model import ProjetoMembroModel
        from src.models.projeto_vendedor_model import ProjetoVendedorModel

        linha = SimpleNamespace(id=1)
        db = DbFake({
            ProjetoMembroModel.__name__: [linha] if na_equipe else [],
            ProjetoVendedorModel.__name__: [linha] if vendeu else [],
            ProjetoFrenteModel.__name__: [linha] if do_gerente else [],
        })
        monkeypatch.setattr(auth, "usuario_tem_permissao", lambda *a, **k: ve_tudo)
        monkeypatch.setattr(auth, "frentes_do_usuario", lambda *a, **k: [7])
        return db

    return _mundo


def quem(posicao="consultor"):
    return SimpleNamespace(id=42, nome="Vendedora", posicao=posicao)


class TestQuemEntraSoPelaVenda:
    def test_vendeu_e_nao_esta_na_equipe(self, mundo):
        db = mundo(vendeu=True)
        assert auth.acesso_somente_por_venda(1, quem(), db) is True

    def test_vendeu_E_esta_na_equipe_nao_e_somente_leitura(self, mundo):
        """A porta mais forte vence. Quem executa o projeto continua podendo
        escrever nele, tendo vendido ou não."""
        db = mundo(vendeu=True, na_equipe=True)
        assert auth.acesso_somente_por_venda(1, quem(), db) is False

    def test_gerente_da_frente_que_tambem_vendeu_nao_e_somente_leitura(self, mundo):
        db = mundo(vendeu=True, do_gerente=True)
        assert auth.acesso_somente_por_venda(1, quem("gerente"), db) is False

    @pytest.mark.parametrize("cargo", ["diretor_projetos", "diretor_pessoas", "diretor"])
    def test_diretoria_nunca_e_somente_leitura(self, mundo, cargo):
        """A diretoria enxerga tudo por outro motivo; a venda não a rebaixa."""
        db = mundo(vendeu=True)
        assert auth.acesso_somente_por_venda(1, quem(cargo), db) is False

    def test_quem_ve_tudo_pela_caixa_tambem_nao(self, mundo):
        db = mundo(vendeu=True, ve_tudo=True)
        assert auth.acesso_somente_por_venda(1, quem(), db) is False

    def test_quem_nao_vendeu_nada_nao_entra_por_aqui(self, mundo):
        db = mundo(na_equipe=True)
        assert auth.acesso_somente_por_venda(1, quem(), db) is False


class TestAPortaDeEscrita:
    """`exigir_acesso_ao_projeto` recusa o vendedor POR PADRÃO."""

    def _porta(self, monkeypatch, somente_por_venda: bool, enxerga: bool = True):
        monkeypatch.setattr(auth, "pode_ver_projeto", lambda *a, **k: enxerga)
        monkeypatch.setattr(
            auth, "acesso_somente_por_venda", lambda *a, **k: somente_por_venda
        )

    def test_escrita_recusa_o_vendedor(self, monkeypatch):
        self._porta(monkeypatch, somente_por_venda=True)
        with pytest.raises(HTTPException) as e:
            auth.exigir_acesso_ao_projeto(1, quem(), None)
        assert e.value.status_code == 403
        assert "leitura" in e.value.detail

    def test_leitura_aceita_o_vendedor(self, monkeypatch):
        self._porta(monkeypatch, somente_por_venda=True)
        auth.exigir_acesso_ao_projeto(1, quem(), None, somente_leitura_ok=True)

    def test_quem_nao_e_so_vendedor_escreve_normalmente(self, monkeypatch):
        self._porta(monkeypatch, somente_por_venda=False)
        auth.exigir_acesso_ao_projeto(1, quem(), None)

    def test_quem_nao_enxerga_leva_404_mesmo_na_leitura(self, monkeypatch):
        """404, não 403: quem não enxerga o projeto não deve saber que existe.
        A liberação de leitura não pode virar um oráculo de existência."""
        self._porta(monkeypatch, somente_por_venda=False, enxerga=False)
        with pytest.raises(HTTPException) as e:
            auth.exigir_acesso_ao_projeto(1, quem(), None, somente_leitura_ok=True)
        assert e.value.status_code == 404


class TestEditarMetadadosDoProjeto:
    """Nome, descrição, cliente, link e anexo da proposta: quem vendeu edita,
    mesmo sem estar na equipe. O resto do projeto segue leitura para ele."""

    def _cenario(self, monkeypatch, *, vendeu: bool, tem_permissao: bool, somente_por_venda: bool = True):
        monkeypatch.setattr(auth, "vendeu_o_projeto", lambda *a, **k: vendeu)
        monkeypatch.setattr(auth, "usuario_tem_permissao", lambda *a, **k: tem_permissao)
        monkeypatch.setattr(auth, "pode_ver_projeto", lambda *a, **k: True)
        monkeypatch.setattr(auth, "acesso_somente_por_venda", lambda *a, **k: somente_por_venda)

    def test_vendedor_passa_mesmo_sem_pode_editar_equipe(self, monkeypatch):
        self._cenario(monkeypatch, vendeu=True, tem_permissao=False)
        auth.exigir_pode_editar_metadados_do_projeto(1, quem(), None)

    def test_quem_tem_pode_editar_equipe_passa_sem_ter_vendido(self, monkeypatch):
        self._cenario(monkeypatch, vendeu=False, tem_permissao=True, somente_por_venda=False)
        auth.exigir_pode_editar_metadados_do_projeto(1, quem("gerente"), None)

    def test_quem_nao_vendeu_nem_tem_permissao_leva_403(self, monkeypatch):
        self._cenario(monkeypatch, vendeu=False, tem_permissao=False, somente_por_venda=False)
        with pytest.raises(HTTPException) as e:
            auth.exigir_pode_editar_metadados_do_projeto(1, quem(), None)
        assert e.value.status_code == 403

    def test_vendedor_que_nao_enxerga_o_projeto_leva_404(self, monkeypatch):
        self._cenario(monkeypatch, vendeu=True, tem_permissao=False)
        monkeypatch.setattr(auth, "pode_ver_projeto", lambda *a, **k: False)
        with pytest.raises(HTTPException) as e:
            auth.exigir_pode_editar_metadados_do_projeto(1, quem(), None)
        assert e.value.status_code == 404


class TestVendedorNaBanca:
    """O vendedor NÃO conta como grupo da banca (reversão de 2026-09-01).

    Entre 2026-08-20 e 2026-09-01 ele entrava em `membros_da_banca` e ficava
    barrado de avaliar a banca do que vendeu. O núcleo reverteu: vender não
    executa o projeto, então para efeito de banca ele é um consultor comum.
    """

    def _monta(self, membros_do_projeto):
        from src.utils.equipe_banca import membros_da_banca

        banca = SimpleNamespace(id=1, coordenador_id=None)
        escopos = SimpleNamespace(get_escopo_ids=lambda _id: [10])
        catalogo = SimpleNamespace(get_by_id=lambda _id: SimpleNamespace(projeto_id=3))
        membros = SimpleNamespace(
            get_by_projeto=lambda pid, apenas_atuais=False: [
                SimpleNamespace(usuario_id=u) for u in membros_do_projeto
            ]
        )
        return membros_da_banca(banca, escopos, catalogo, membros, None)

    def test_membro_real_do_projeto_ainda_entra(self):
        assert 7 in self._monta([7])

    def test_quem_nao_e_do_projeto_nao_entra(self):
        assert 42 not in self._monta([7])

    def test_membros_da_banca_nao_aceita_mais_vendedor_repository(self):
        """A assinatura perdeu o parâmetro: passar um sexto argumento estoura."""
        from src.utils.equipe_banca import membros_da_banca

        banca = SimpleNamespace(id=1, coordenador_id=None)
        with pytest.raises(TypeError):
            membros_da_banca(
                banca,
                SimpleNamespace(get_escopo_ids=lambda _id: []),
                SimpleNamespace(get_by_id=lambda _id: None),
                SimpleNamespace(get_by_projeto=lambda pid, apenas_atuais=False: []),
                None,
                SimpleNamespace(get_by_projeto=lambda pid: []),
            )

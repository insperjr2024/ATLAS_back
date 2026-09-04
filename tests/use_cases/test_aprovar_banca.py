"""⭐ Quem aprova a banca é diretoria de projetos OU gerente de qualquer
frente dela (§5.5, §8) — a pedido explícito do usuário (2026-09-03), no lugar
do voto dos avaliadores.

⭐ **Qualquer um decide sozinho.** O usuário mudou de ideia durante a
implementação: a primeira versão exigia diretoria E gerente concordando; esta
é a versão final — o primeiro que decidir já fecha o resultado.

Mesmo idioma dos outros testes de use case: dublês à mão, com as classes de
repositório e as funções de `authorization` trocadas no MÓDULO
`aprovar_banca`, porque é lá que o use case as referencia.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.banca import aprovar_banca as mod
from src.use_cases.banca.aprovar_banca import (
    RegistrarAprovacaoBancaRequest,
    RegistrarAprovacaoBancaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def usuario(id, posicao):
    return SimpleNamespace(id=id, posicao=posicao)


DIRETOR = usuario(1, "diretor_projetos")
GERENTE_TECH = usuario(2, "gerente")
GERENTE_BUSINESS = usuario(3, "gerente")
CONSULTOR = usuario(4, "consultor")

FRENTE_TECH = 10
FRENTE_BUSINESS = 20


@pytest.fixture
def mundo(monkeypatch):
    """Monta a banca e o que gira em volta dela.

    `frentes_da_banca`: quais frentes a banca tem (`banca_frente`).
    `gerentes_por_frente`: {frente_id: [usuario_id, ...]} — quem é gerente
    ATIVO de cada frente; frente ausente daqui não tem gerente cadastrado.
    `minhas_frentes`: o que `frentes_do_usuario` devolve para quem chama.
    """

    def _mundo(
        *,
        realizado_em="2026-09-01",
        resultado=None,
        frentes_da_banca=(FRENTE_TECH,),
        gerentes_por_frente=None,
        minhas_frentes=(),
        frentes_por_usuario=None,
        possiveis_gerentes_sistema=(),
    ):
        gerentes_por_frente = gerentes_por_frente or {}
        # `frentes_por_usuario` permite que gerentes DIFERENTES, na mesma
        # banca sinérgica, respondam por frentes diferentes — sem ele, todo
        # gerente enxergaria as mesmas frentes de `minhas_frentes`.
        frentes_por_usuario = frentes_por_usuario or {}
        banca = SimpleNamespace(id=1, realizado_em=realizado_em, resultado=resultado)
        aprovacoes: list = []

        class BancaFake:
            def __init__(self, db): pass
            def get_by_id(self, banca_id):
                return banca if banca_id == banca.id else None
            def update(self, banca_id, **kwargs):
                for k, v in kwargs.items():
                    setattr(banca, k, v)
                return banca

        class BancaFrenteFake:
            def __init__(self, db): pass
            def get_by_banca(self, banca_id):
                return [SimpleNamespace(frente_id=f) for f in frentes_da_banca]

        class UsuarioFrenteFake:
            def __init__(self, db): pass
            def get_by_frente(self, frente_id):
                return [
                    SimpleNamespace(usuario_id=u)
                    for u in gerentes_por_frente.get(frente_id, [])
                ]

        class UsuarioFake:
            def __init__(self, db): pass
            def get_by_id(self, usuario_id):
                todos = {DIRETOR.id: DIRETOR, GERENTE_TECH.id: GERENTE_TECH, GERENTE_BUSINESS.id: GERENTE_BUSINESS}
                u = todos.get(usuario_id)
                if u is None:
                    return None
                return SimpleNamespace(id=u.id, posicao=u.posicao, ativo=True, nome=f"Usuário {u.id}")
            def get_por_posicao(self, posicao):
                # O fallback de "possíveis gerentes" quando a frente não tem
                # ninguém vinculado ainda — vazio por padrão nos testes que não
                # mexem nisso de propósito.
                return [
                    SimpleNamespace(id=nome, posicao="gerente", ativo=True, nome=nome)
                    for nome in possiveis_gerentes_sistema
                ]

        class FrenteFake:
            def __init__(self, db): pass
            def get_by_id(self, frente_id):
                return SimpleNamespace(id=frente_id, nome=f"Frente {frente_id}")

        class BancaAprovacaoFake:
            def __init__(self, db): pass
            def get_by_banca(self, banca_id, sessao=None):
                return [
                    a for a in aprovacoes
                    if a.banca_id == banca_id and (sessao is None or a.sessao == sessao)
                ]
            def registrar(self, banca_id, papel, frente_id, sessao, usuario_id, aprovado, nota):
                for a in aprovacoes:
                    if (
                        a.banca_id == banca_id and a.papel == papel
                        and a.frente_id == frente_id and a.sessao == sessao
                    ):
                        a.usuario_id, a.aprovado, a.nota = usuario_id, aprovado, nota
                        return a
                linha = SimpleNamespace(
                    banca_id=banca_id, papel=papel, frente_id=frente_id, sessao=sessao,
                    usuario_id=usuario_id, aprovado=aprovado, nota=nota, criado_em=None,
                )
                aprovacoes.append(linha)
                return linha

        class SessaoFake:
            def __init__(self, db): pass
            def get_corrente(self, banca_id): return SimpleNamespace(id=1, numero=1)
            def get_by_banca(self, banca_id): return []
            def update(self, sessao_id, **kwargs): pass

        for nome, dublê in (
            ("BancaRepository", BancaFake),
            ("BancaFrenteRepository", BancaFrenteFake),
            ("UsuarioFrenteRepository", UsuarioFrenteFake),
            ("UsuarioRepository", UsuarioFake),
            ("FrenteRepository", FrenteFake),
            ("BancaAprovacaoRepository", BancaAprovacaoFake),
            ("BancaSessaoRepository", SessaoFake),
        ):
            monkeypatch.setattr(mod, nome, dublê)

        monkeypatch.setattr(mod, "eh_diretoria_de_projetos", lambda u: u.posicao == "diretor_projetos")
        monkeypatch.setattr(
            mod,
            "frentes_do_usuario",
            lambda u, db: list(frentes_por_usuario.get(u.id, minhas_frentes)),
        )

        return RegistrarAprovacaoBancaUseCase(db=None), banca

    return _mundo


def decidir(uc, aprovado, usuario, nota=None):
    return uc.execute(1, RegistrarAprovacaoBancaRequest(aprovado=aprovado, nota=nota), usuario)


class TestPreCondicoes:
    def test_banca_nao_realizada_e_recusada(self, mundo):
        uc, _ = mundo(realizado_em=None)
        with pytest.raises(RegraDeNegocioError, match="realizada"):
            decidir(uc, True, DIRETOR)

    def test_banca_com_resultado_fechado_e_imutavel(self, mundo):
        uc, _ = mundo(resultado="aprovada")
        with pytest.raises(RegraDeNegocioError, match="já tem resultado"):
            decidir(uc, True, DIRETOR)

    def test_quem_nao_e_diretoria_nem_gerente_e_recusado(self, mundo):
        uc, _ = mundo()
        with pytest.raises(RegraDeNegocioError, match="diretoria de projetos ou gerente"):
            decidir(uc, True, CONSULTOR)

    def test_gerente_de_frente_alheia_e_recusado(self, mundo):
        """Ele é gerente de verdade — só não desta banca."""
        uc, _ = mundo(frentes_da_banca=(FRENTE_TECH,), minhas_frentes=(FRENTE_BUSINESS,))
        with pytest.raises(RegraDeNegocioError, match="Você não é gerente"):
            decidir(uc, True, GERENTE_BUSINESS)


class TestQualquerUmDecideSozinho:
    """⭐ O primeiro que decidir já fecha — diretoria e gerente têm o mesmo
    peso, e nenhum dos dois precisa esperar o outro."""

    def test_diretoria_aprova_sozinha_fecha_aprovada(self, mundo):
        uc, banca = mundo(gerentes_por_frente={FRENTE_TECH: [GERENTE_TECH.id]})
        resultado = decidir(uc, True, DIRETOR)

        assert resultado["resultado"] == "aprovada"
        assert banca.resultado == "aprovada"

    def test_diretoria_reprova_sozinha_fecha_nao_aprovada(self, mundo):
        uc, banca = mundo()
        resultado = decidir(uc, False, DIRETOR)

        assert resultado["resultado"] == "nao_aprovada"
        assert banca.resultado == "nao_aprovada"

    def test_gerente_aprova_sozinho_fecha_aprovada_sem_a_diretoria(self, mundo):
        uc, banca = mundo(gerentes_por_frente={FRENTE_TECH: [GERENTE_TECH.id]}, minhas_frentes=(FRENTE_TECH,))
        resultado = decidir(uc, True, GERENTE_TECH)

        assert resultado["resultado"] == "aprovada"
        assert banca.resultado == "aprovada"

    def test_gerente_reprova_sozinho_fecha_nao_aprovada_sem_a_diretoria(self, mundo):
        uc, banca = mundo(gerentes_por_frente={FRENTE_TECH: [GERENTE_TECH.id]}, minhas_frentes=(FRENTE_TECH,))
        resultado = decidir(uc, False, GERENTE_TECH)

        assert resultado["resultado"] == "nao_aprovada"
        assert banca.resultado == "nao_aprovada"

    def test_frente_sem_gerente_cadastrado_nao_impede_a_diretoria(self, mundo):
        """Não é mais "dispensa" nem "trava" — é irrelevante: a diretoria
        decide sozinha de qualquer forma, com ou sem gerente cadastrado."""
        uc, banca = mundo(gerentes_por_frente={})
        resultado = decidir(uc, True, DIRETOR)

        assert resultado["resultado"] == "aprovada"
        assert banca.resultado == "aprovada"

    def test_banca_sem_frente_nenhuma_so_diretoria_pode(self, mundo):
        """Banca legada, sem `banca_frente`: não há frente nenhuma para um
        gerente reivindicar, então só a diretoria decide."""
        uc, banca = mundo(frentes_da_banca=())
        resultado = decidir(uc, True, DIRETOR)

        assert resultado["resultado"] == "aprovada"
        assert banca.resultado == "aprovada"


class TestProjetoSinergico:
    """Banca com duas frentes, cada uma com seu próprio gerente — qualquer
    um dos dois gerentes decide pela banca inteira, sozinho."""

    def _mundo_sinergico(self, mundo):
        return mundo(
            frentes_da_banca=(FRENTE_TECH, FRENTE_BUSINESS),
            gerentes_por_frente={
                FRENTE_TECH: [GERENTE_TECH.id],
                FRENTE_BUSINESS: [GERENTE_BUSINESS.id],
            },
            frentes_por_usuario={
                GERENTE_TECH.id: (FRENTE_TECH,),
                GERENTE_BUSINESS.id: (FRENTE_BUSINESS,),
            },
        )

    def test_gerente_de_uma_das_frentes_aprova_e_ja_fecha(self, mundo):
        uc, banca = self._mundo_sinergico(mundo)
        resultado = decidir(uc, True, GERENTE_TECH)

        assert resultado["resultado"] == "aprovada"
        assert banca.resultado == "aprovada"

    def test_gerente_de_qualquer_uma_das_frentes_reprova_e_ja_fecha(self, mundo):
        uc, banca = self._mundo_sinergico(mundo)
        resultado = decidir(uc, False, GERENTE_BUSINESS)

        assert resultado["resultado"] == "nao_aprovada"
        assert banca.resultado == "nao_aprovada"

    def test_gerente_responsavel_pelas_duas_frentes_decide_uma_vez_so(self, mundo):
        """Mesma pessoa gerencia as duas frentes do projeto sinérgico: uma
        decisão só, registrada nas duas, já fecha o resultado."""
        uc, banca = mundo(
            frentes_da_banca=(FRENTE_TECH, FRENTE_BUSINESS),
            gerentes_por_frente={
                FRENTE_TECH: [GERENTE_TECH.id],
                FRENTE_BUSINESS: [GERENTE_TECH.id],
            },
            minhas_frentes=(FRENTE_TECH, FRENTE_BUSINESS),
        )
        resultado = decidir(uc, True, GERENTE_TECH)

        assert resultado["resultado"] == "aprovada"
        assert banca.resultado == "aprovada"
        assert {g["frente_id"] for g in resultado["aprovacao_gerente"] if g["aprovado"]} == {
            FRENTE_TECH,
            FRENTE_BUSINESS,
        }


class TestSituacaoAntesDeDecidir:
    """`montar_situacao_aprovacao` enquanto ninguém decidiu ainda — o que a
    fila "Esperando aprovação" mostra."""

    def test_mostra_quem_pode_aprovar_por_cada_frente(self, mundo):
        uc, banca = mundo(gerentes_por_frente={FRENTE_TECH: [GERENTE_TECH.id]})
        from src.use_cases.banca.aprovar_banca import montar_situacao_aprovacao

        situacao = montar_situacao_aprovacao(uc.db, banca)

        assert situacao["resultado"] is None
        assert situacao["aprovacao_diretoria"] is None
        assert situacao["aprovacao_gerente"][0]["aprovado"] is None
        assert situacao["aprovacao_gerente"][0]["possiveis_gerentes"] == ["Usuário 2"]

    def test_frente_sem_gerente_cai_no_fallback_do_sistema(self, mundo):
        uc, banca = mundo(gerentes_por_frente={}, possiveis_gerentes_sistema=("Fulano", "Beltrano"))
        from src.use_cases.banca.aprovar_banca import montar_situacao_aprovacao

        situacao = montar_situacao_aprovacao(uc.db, banca)

        assert situacao["aprovacao_gerente"][0]["possiveis_gerentes"] == ["Fulano", "Beltrano"]

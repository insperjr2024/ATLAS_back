"""`serializar_documento_contratual_completo` — o link de aprovação embutido
(§ Contratos, 2026-09-23).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório
trocadas no MÓDULO `get_documento`.

⚠ Existe por causa de um pedido real: o card de "copiar link"/"enviar por
WhatsApp" só existia no retorno de `POST .../exportar-aprovacao` — uma
visualização única que sumia ao sair e voltar da página do documento. Agora
o GET reconstrói o link a partir do token ainda não usado.
"""

from types import SimpleNamespace

import src.use_cases.documento_contratual.get_documento as mod


def _documento(projeto_id=7, projeto_nome="Projeto X", aprovado_internamente_por=None):
    projeto = SimpleNamespace(id=projeto_id, nome=projeto_nome, cliente=None)
    return SimpleNamespace(
        id=1,
        projeto_id=projeto_id,
        projeto=projeto,
        nome_projeto_externo=None,
        cliente_externo=None,
        tipo="contrato",
        status="aguardando_aprovacao_cliente",
        dados={},
        confirmado=True,
        gestao_id=None,
        criado_em="2026-09-23",
        atualizado_em="2026-09-23",
        aprovado_internamente_por=aprovado_internamente_por,
        aprovado_internamente_em=None,
    )


def _montar(monkeypatch, *, token=None, frentes=(), usuario=None):
    class TokenRepoFake:
        def __init__(self, db): pass
        def get_ativo_por_documento(self, documento_id):
            return token

    class FrenteRepoFake:
        def __init__(self, db): pass
        def get_by_projeto(self, _projeto_id):
            return [SimpleNamespace(frente_id=f) for f in frentes]

    class UsuarioRepoFake:
        def __init__(self, db): pass
        def get_by_id(self, _uid):
            return usuario

    monkeypatch.setattr(mod, "TokenAprovacaoContratualRepository", TokenRepoFake)
    monkeypatch.setattr(mod, "ProjetoFrenteRepository", FrenteRepoFake)
    monkeypatch.setattr(mod, "UsuarioRepository", UsuarioRepoFake)
    monkeypatch.setattr(
        mod, "get_settings", lambda: SimpleNamespace(FRONTEND_URL="https://atlas.insperjr.com.br")
    )


class TestLinkAprovacaoAtivo:
    def test_sem_token_ativo_link_e_nulo(self, monkeypatch):
        _montar(monkeypatch, token=None)

        serializado = mod.serializar_documento_contratual_completo(None, _documento())

        assert serializado["link_aprovacao"] is None

    def test_com_token_ativo_reconstroi_o_link(self, monkeypatch):
        token = SimpleNamespace(token="abc123", usado=False)
        _montar(monkeypatch, token=token)

        serializado = mod.serializar_documento_contratual_completo(
            None, _documento(projeto_nome="Projeto Y")
        )

        link = serializado["link_aprovacao"]
        assert link is not None
        assert link["token"] == "abc123"
        assert link["link_aprovacao"] == "https://atlas.insperjr.com.br/aprovacao/abc123"
        assert "Projeto Y" in link["mensagem_whatsapp"]
        assert "abc123" in link["mensagem_whatsapp"]

    def test_repositorio_so_devolve_token_nao_usado(self, monkeypatch):
        """A régua de "some quando o cliente responde" mora no próprio
        repositório (`usado=False`), não é reconferida aqui — este teste só
        garante que o serializer não segura nenhum token que o repositório
        já não devolveria."""
        _montar(monkeypatch, token=None)

        serializado = mod.serializar_documento_contratual_completo(None, _documento())

        assert serializado["link_aprovacao"] is None

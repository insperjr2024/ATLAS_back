"""Quem é notificado em cada gatilho do documento jurídico (§ Contratos,
2026-09-21).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório e
`registrar` trocados no MÓDULO `notificar_documento_contratual`.
"""

from types import SimpleNamespace

import src.utils.notificar_documento_contratual as mod


def usuario(id):
    return SimpleNamespace(id=id, nome=f"Usuário {id}")


VENDEDOR = usuario(10)
DIRETOR = usuario(20)
COORDENADOR = usuario(30)
CRIADOR = usuario(40)


def documento(tipo, projeto_id=7, criado_por=CRIADOR.id):
    projeto = SimpleNamespace(id=projeto_id, nome="Projeto X", criado_por=criado_por)
    return SimpleNamespace(id=1, tipo=tipo, projeto_id=projeto_id, projeto=projeto)


def montar(monkeypatch, vendedores=(), diretores=(), membros=()):
    class UsuarioFake:
        def __init__(self, db): pass
        def get_by_id(self, uid):
            todos = {VENDEDOR.id: VENDEDOR, DIRETOR.id: DIRETOR, COORDENADOR.id: COORDENADOR, CRIADOR.id: CRIADOR}
            return todos.get(uid)
        def get_por_posicao(self, posicao):
            return list(diretores) if posicao == "diretor_projetos" else []

    class VendedorFake:
        def __init__(self, db): pass
        def get_by_projeto(self, _projeto_id):
            return [SimpleNamespace(usuario_id=v.id) for v in vendedores]

    class MembroFake:
        def __init__(self, db): pass
        def get_by_projeto(self, _projeto_id, apenas_atuais=False):
            return membros

    monkeypatch.setattr(mod, "UsuarioRepository", UsuarioFake)
    monkeypatch.setattr(mod, "ProjetoVendedorRepository", VendedorFake)
    monkeypatch.setattr(mod, "ProjetoMembroRepository", MembroFake)


class TestDestinatariosEnvio:
    def test_contrato_notifica_os_vendedores_do_projeto(self, monkeypatch):
        montar(monkeypatch, vendedores=[VENDEDOR])

        destinatarios = mod._destinatarios_envio(None, documento("contrato"))

        assert {u.id for u in destinatarios} == {VENDEDOR.id}

    def test_tep_notifica_diretoria_e_coordenador_do_projeto(self, monkeypatch):
        membros = [SimpleNamespace(usuario_id=COORDENADOR.id, papel="coordenador")]
        montar(monkeypatch, diretores=[DIRETOR], membros=membros)

        destinatarios = mod._destinatarios_envio(None, documento("tep"))

        assert {u.id for u in destinatarios} == {DIRETOR.id, COORDENADOR.id}

    def test_tep_nao_notifica_membro_que_nao_e_coordenador(self, monkeypatch):
        membros = [SimpleNamespace(usuario_id=COORDENADOR.id, papel="consultor")]
        montar(monkeypatch, diretores=[DIRETOR], membros=membros)

        destinatarios = mod._destinatarios_envio(None, documento("tep"))

        assert {u.id for u in destinatarios} == {DIRETOR.id}

    def test_outros_tipos_cai_no_criador_do_projeto(self, monkeypatch):
        montar(monkeypatch)

        destinatarios = mod._destinatarios_envio(None, documento("nda"))

        assert {u.id for u in destinatarios} == {CRIADOR.id}


class TestDisparosUsamDestinatariosEnvio:
    def test_aprovado_internamente_notifica_o_vendedor_nao_o_criador(self, monkeypatch):
        montar(monkeypatch, vendedores=[VENDEDOR])
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        mod.documento_aprovado_internamente(None, documento("contrato", criado_por=CRIADOR.id))

        assert chamadas == [VENDEDOR.id]

    def test_liberado_para_cliente_notifica_quem_manda_nao_o_criador(self, monkeypatch):
        membros = [SimpleNamespace(usuario_id=COORDENADOR.id, papel="coordenador")]
        montar(monkeypatch, diretores=[DIRETOR], membros=membros)
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        mod.documento_liberado_para_cliente(None, documento("tep", criado_por=CRIADOR.id))

        assert set(chamadas) == {DIRETOR.id, COORDENADOR.id}

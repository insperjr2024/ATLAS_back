"""Quem é notificado em cada gatilho do documento jurídico (§ Contratos,
2026-09-21).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório e
`registrar` trocados no MÓDULO `notificar_documento_contratual`.
"""

from types import SimpleNamespace

import src.utils.notificar_documento_contratual as mod
import src.utils.notificar_projeto as notificar_projeto_mod


def usuario(id):
    return SimpleNamespace(id=id, nome=f"Usuário {id}")


VENDEDOR = usuario(10)
DIRETOR = usuario(20)
COORDENADOR = usuario(30)
CRIADOR = usuario(40)
GERENTE = usuario(50)
JURIDICO = usuario(60)


def documento(tipo, projeto_id=7, criado_por=CRIADOR.id, confirmado_por=None):
    projeto = SimpleNamespace(id=projeto_id, nome="Projeto X", criado_por=criado_por)
    return SimpleNamespace(
        id=1, tipo=tipo, projeto_id=projeto_id, projeto=projeto, confirmado_por=confirmado_por
    )


def montar(monkeypatch, vendedores=(), diretores=(), membros=(), gerentes=(), juridicos=(), qualquer_contrato=()):
    todos = {
        VENDEDOR.id: VENDEDOR, DIRETOR.id: DIRETOR, COORDENADOR.id: COORDENADOR,
        CRIADOR.id: CRIADOR, GERENTE.id: GERENTE, JURIDICO.id: JURIDICO,
    }

    class UsuarioFake:
        def __init__(self, db): pass
        def get_by_id(self, uid):
            return todos.get(uid)
        def get_por_posicao(self, posicao):
            if posicao == "diretor_projetos":
                return list(diretores)
            if posicao == "gerente":
                return list(gerentes)
            return []

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
    # `diretoria_e_gerentes` mora em `notificar_projeto.py` — patcheia lá,
    # não aqui, senão o `mod.UsuarioRepository` não vale pra ela.
    monkeypatch.setattr(notificar_projeto_mod, "UsuarioRepository", UsuarioFake)
    def usuarios_com_permissao_fake(db, campo):
        if campo == "pode_aprovar_contrato_internamente":
            return list(juridicos)
        if campo == "pode_elaborar_qualquer_contrato":
            return list(qualquer_contrato)
        return []

    monkeypatch.setattr(mod, "usuarios_com_permissao", usuarios_com_permissao_fake)


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


class TestQuemGereDocumento:
    """⭐ 2026-09-23 — a pedido: gerente de frente tem `pode_elaborar_
    qualquer_contrato` (acesso e edição de qualquer contrato é visão geral
    proposital), mas não deve entrar na notificação de "documento pronto
    para geração" — vira notificação em massa pra gente que não vai
    gerar/revisar o documento."""

    def test_notifica_diretor_projetos(self, monkeypatch):
        montar(monkeypatch, diretores=[DIRETOR])

        destinatarios = mod._quem_gere_documento(None, documento("contrato"))

        assert {u.id for u in destinatarios} == {DIRETOR.id}

    def test_notifica_quem_tem_qualquer_contrato_mas_nao_e_gerente(self, monkeypatch):
        juridico_com_caixa = SimpleNamespace(id=JURIDICO.id, nome="Jurídico", posicao="adm_juridico")
        montar(monkeypatch, qualquer_contrato=[juridico_com_caixa])

        destinatarios = mod._quem_gere_documento(None, documento("contrato"))

        assert {u.id for u in destinatarios} == {JURIDICO.id}

    def test_nao_notifica_gerente_mesmo_com_qualquer_contrato(self, monkeypatch):
        gerente_com_caixa = SimpleNamespace(id=GERENTE.id, nome="Gerente", posicao="gerente")
        montar(monkeypatch, qualquer_contrato=[gerente_com_caixa])

        destinatarios = mod._quem_gere_documento(None, documento("contrato"))

        assert destinatarios == []


class TestDisparosUsamDestinatariosEnvio:
    def test_aprovado_internamente_notifica_o_vendedor_nao_o_criador(self, monkeypatch):
        montar(monkeypatch, vendedores=[VENDEDOR])
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        mod.documento_aprovado_internamente(None, documento("contrato", criado_por=CRIADOR.id))

        assert chamadas == [VENDEDOR.id]

    def test_aprovado_internamente_notifica_tambem_quem_elaborou(self, monkeypatch):
        montar(monkeypatch, vendedores=[VENDEDOR])
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        # COORDENADOR aqui só representa "quem elaborou" (confirmou o
        # preenchimento) — nada a ver com coordenação de projeto neste teste.
        doc = documento("contrato", confirmado_por=COORDENADOR.id)
        mod.documento_aprovado_internamente(None, doc)

        assert set(chamadas) == {VENDEDOR.id, COORDENADOR.id}

    def test_liberado_para_cliente_notifica_quem_manda_nao_o_criador(self, monkeypatch):
        membros = [SimpleNamespace(usuario_id=COORDENADOR.id, papel="coordenador")]
        montar(monkeypatch, diretores=[DIRETOR], membros=membros)
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        mod.documento_liberado_para_cliente(None, documento("tep", criado_por=CRIADOR.id))

        assert set(chamadas) == {DIRETOR.id, COORDENADOR.id}


class TestDocumentoContratoConfirmado:
    def test_notifica_diretoria_gerentes_e_vendedor(self, monkeypatch):
        montar(monkeypatch, vendedores=[VENDEDOR], diretores=[DIRETOR], gerentes=[GERENTE])
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        mod.documento_contrato_confirmado(None, documento("contrato"))

        assert set(chamadas) == {DIRETOR.id, GERENTE.id, VENDEDOR.id}


class TestDocumentoProntoParaRevisaoInterna:
    def test_notifica_quem_pode_aprovar_internamente(self, monkeypatch):
        montar(monkeypatch, juridicos=[JURIDICO])
        chamadas = []
        monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))

        mod.documento_pronto_para_revisao_interna(None, documento("contrato"))

        assert chamadas == [JURIDICO.id]

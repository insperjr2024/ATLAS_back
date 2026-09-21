"""Notificações de projeto criado/vendido (§ Contratos, 2026-09-21).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório e
`registrar` trocados no MÓDULO `notificar_projeto`.
"""

from types import SimpleNamespace

import src.utils.notificar_projeto as mod


def usuario(id):
    return SimpleNamespace(id=id, nome=f"Usuário {id}")


DIRETOR = usuario(1)
GERENTE = usuario(2)
VENDEDOR = usuario(3)


def montar(monkeypatch, diretores=(), gerentes=(), vendedores=()):
    class UsuarioFake:
        def __init__(self, db): pass
        def get_por_posicao(self, posicao):
            if posicao == "diretor_projetos":
                return list(diretores)
            if posicao == "gerente":
                return list(gerentes)
            return []
        def get_by_id(self, uid):
            return next((u for u in vendedores if u.id == uid), None)

    class VendedorFake:
        def __init__(self, db): pass
        def get_by_projeto(self, _projeto_id):
            return [SimpleNamespace(usuario_id=v.id) for v in vendedores]

    monkeypatch.setattr(mod, "UsuarioRepository", UsuarioFake)
    monkeypatch.setattr(mod, "ProjetoVendedorRepository", VendedorFake)

    chamadas = []
    monkeypatch.setattr(mod, "registrar", lambda db, **kw: chamadas.append(kw["usuario_id"]))
    return chamadas


def projeto(id=7, nome="Projeto Alfa"):
    return SimpleNamespace(id=id, nome=nome)


class TestProjetoCriado:
    def test_notifica_diretoria_gerentes_e_vendedores(self, monkeypatch):
        chamadas = montar(monkeypatch, diretores=[DIRETOR], gerentes=[GERENTE], vendedores=[VENDEDOR])

        mod.projeto_criado(None, projeto())

        assert set(chamadas) == {DIRETOR.id, GERENTE.id, VENDEDOR.id}

    def test_sem_vendedor_ainda_notifica_so_diretoria_e_gerentes(self, monkeypatch):
        chamadas = montar(monkeypatch, diretores=[DIRETOR], gerentes=[GERENTE])

        mod.projeto_criado(None, projeto())

        assert set(chamadas) == {DIRETOR.id, GERENTE.id}


class TestProjetoVendido:
    def test_notifica_diretoria_e_gerentes(self, monkeypatch):
        chamadas = montar(monkeypatch, diretores=[DIRETOR], gerentes=[GERENTE], vendedores=[VENDEDOR])

        mod.projeto_vendido(None, projeto())

        assert set(chamadas) == {DIRETOR.id, GERENTE.id}

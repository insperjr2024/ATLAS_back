"""Notificações de projeto criado/vendido (§ Contratos, 2026-09-21).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório e
`registrar` trocados no MÓDULO `notificar_projeto`.
"""

from types import SimpleNamespace

import src.utils.notificar_projeto as mod


def usuario(id, posicao="consultor", status="ativo", ativo=True):
    return SimpleNamespace(id=id, nome=f"Usuário {id}", posicao=posicao, status=status, ativo=ativo)


DIRETOR = usuario(1, posicao="diretor_projetos")
GERENTE = usuario(2, posicao="gerente")
VENDEDOR = usuario(3)


def montar(
    monkeypatch,
    diretores=(),
    gerentes=(),
    vendedores=(),
    consultores_por_frente=None,
    frentes_do_projeto=None,
):
    """`consultores_por_frente` é o mapa GLOBAL frente_id -> membros (quem
    está em cada frente, na plataforma inteira); `frentes_do_projeto` é
    quais dessas frentes o projeto testado tem — default: todas as chaves
    de `consultores_por_frente`, pra quem não precisa testar a interseção."""
    consultores_por_frente = consultores_por_frente or {}
    if frentes_do_projeto is None:
        frentes_do_projeto = list(consultores_por_frente)
    todos = {u.id: u for u in [*diretores, *gerentes, *vendedores]}
    for lista in consultores_por_frente.values():
        for u in lista:
            todos[u.id] = u

    class UsuarioFake:
        def __init__(self, db): pass
        def get_por_posicao(self, posicao):
            if posicao == "diretor_projetos":
                return list(diretores)
            if posicao == "gerente":
                return list(gerentes)
            return []
        def get_by_id(self, uid):
            return todos.get(uid)

    class VendedorFake:
        def __init__(self, db): pass
        def get_by_projeto(self, _projeto_id):
            return [SimpleNamespace(usuario_id=v.id) for v in vendedores]

    class ProjetoFrenteFake:
        def __init__(self, db): pass
        def get_by_projeto(self, _projeto_id):
            return [SimpleNamespace(frente_id=fid) for fid in frentes_do_projeto]

    class UsuarioFrenteFake:
        def __init__(self, db): pass
        def get_by_frente(self, frente_id):
            return [SimpleNamespace(usuario_id=u.id) for u in consultores_por_frente.get(frente_id, [])]

    monkeypatch.setattr(mod, "UsuarioRepository", UsuarioFake)
    monkeypatch.setattr(mod, "ProjetoVendedorRepository", VendedorFake)
    monkeypatch.setattr(mod, "ProjetoFrenteRepository", ProjetoFrenteFake)
    monkeypatch.setattr(mod, "UsuarioFrenteRepository", UsuarioFrenteFake)

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


class TestVagasAbertas:
    def test_notifica_so_consultores_ativos_das_frentes_do_projeto(self, monkeypatch):
        consultor_da_frente = usuario(10)
        consultor_de_outra_frente = usuario(11)
        chamadas = montar(
            monkeypatch,
            diretores=[DIRETOR],
            gerentes=[GERENTE],
            consultores_por_frente={1: [consultor_da_frente], 2: [consultor_de_outra_frente]},
            frentes_do_projeto=[1],
        )

        mod.vagas_abertas(None, projeto())

        # Só quem está na frente 1 (a única frente DESTE projeto) — não
        # diretoria/gerentes, não quem é só da frente 2.
        assert set(chamadas) == {consultor_da_frente.id}

    def test_nao_notifica_coordenador_gerente_ou_diretor_da_mesma_frente(self, monkeypatch):
        coordenador_da_frente = usuario(20, posicao="coordenador")
        gerente_da_frente = usuario(21, posicao="gerente")
        consultor_da_frente = usuario(22)
        chamadas = montar(
            monkeypatch,
            consultores_por_frente={1: [coordenador_da_frente, gerente_da_frente, consultor_da_frente]},
        )

        mod.vagas_abertas(None, projeto())

        assert set(chamadas) == {consultor_da_frente.id}

    def test_nao_notifica_consultor_inativo(self, monkeypatch):
        consultor_inativo = usuario(30, status="ex_membro", ativo=False)
        chamadas = montar(monkeypatch, consultores_por_frente={1: [consultor_inativo]})

        mod.vagas_abertas(None, projeto())

        assert chamadas == []

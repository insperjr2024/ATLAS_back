"""O atalho "Novo projeto" é a caixa `pode_criar_projeto_atalho`, não o cargo (2026-10-13)."""

from types import SimpleNamespace

from src.routers import projetos as router


class _UseCase:
    chamadas: list[bool] = []

    def __init__(self, db):
        pass

    def execute(self, request, criado_por, direto_para_vendido=False):
        _UseCase.chamadas.append(direto_para_vendido)
        return {"id": 1}


def _criar(monkeypatch, tem_caixa, pediu_atalho, posicao="gerente"):
    _UseCase.chamadas.clear()
    monkeypatch.setattr(router, "CreateProjetoUseCase", _UseCase)
    monkeypatch.setattr(
        router,
        "usuario_tem_permissao",
        lambda usuario, db, campo: campo == "pode_criar_projeto_atalho" and tem_caixa,
    )
    request = router.CreateProjetoRequest(nome="X", frente_ids=[1], equipe=[], atalho_direto_vendido=pediu_atalho)
    router.create_projeto(request, current_user=SimpleNamespace(id=7, posicao=posicao), db=None)
    return _UseCase.chamadas[0]


def test_com_a_caixa_e_pedindo_nasce_vendido(monkeypatch):
    assert _criar(monkeypatch, tem_caixa=True, pediu_atalho=True) is True


def test_sem_a_caixa_nao_e_atalho_nem_pra_diretor_de_projetos(monkeypatch):
    assert _criar(monkeypatch, tem_caixa=False, pediu_atalho=True, posicao="diretor_projetos") is False


def test_com_a_caixa_mas_pelo_fluxo_normal_nao_e_atalho(monkeypatch):
    assert _criar(monkeypatch, tem_caixa=True, pediu_atalho=False) is False

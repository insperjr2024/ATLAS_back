"""Trocas automáticas de projeto.status (§ Contratos, 2026-09-21)."""

from types import SimpleNamespace

from src.utils.mudar_status_projeto_automatico import mudar_status_projeto_automaticamente


class FakeProjetoRepo:
    def __init__(self, projeto):
        self._projeto = projeto
        self.atualizado_com = None

    def get_by_id(self, _id):
        return self._projeto

    def update(self, _id, **kwargs):
        self.atualizado_com = kwargs
        for chave, valor in kwargs.items():
            setattr(self._projeto, chave, valor)
        return self._projeto


class FakeHistoricoRepo:
    def __init__(self):
        self.criado = None

    def create(self, **kwargs):
        self.criado = kwargs
        return SimpleNamespace(**kwargs)


def montar(monkeypatch, projeto):
    import src.utils.mudar_status_projeto_automatico as mod

    projeto_repo = FakeProjetoRepo(projeto)
    historico_repo = FakeHistoricoRepo()
    monkeypatch.setattr(mod, "ProjetoRepository", lambda _db: projeto_repo)
    monkeypatch.setattr(mod, "ProjetoStatusHistoricoRepository", lambda _db: historico_repo)
    return projeto_repo, historico_repo


def test_muda_o_status_e_grava_historico_sem_autor(monkeypatch):
    projeto = SimpleNamespace(id=7, status="em_andamento")
    projeto_repo, historico_repo = montar(monkeypatch, projeto)

    mudar_status_projeto_automaticamente(None, 7, "envio_tep")

    assert projeto_repo.atualizado_com == {"status": "envio_tep"}
    assert historico_repo.criado == {
        "projeto_id": 7,
        "status_anterior": "em_andamento",
        "status_novo": "envio_tep",
        "alterado_por": None,
    }


def test_nao_faz_nada_se_ja_esta_no_status(monkeypatch):
    projeto = SimpleNamespace(id=7, status="envio_tep")
    projeto_repo, historico_repo = montar(monkeypatch, projeto)

    mudar_status_projeto_automaticamente(None, 7, "envio_tep")

    assert projeto_repo.atualizado_com is None
    assert historico_repo.criado is None


def test_nao_mexe_em_projeto_pausado(monkeypatch):
    projeto = SimpleNamespace(id=7, status="pausado")
    projeto_repo, historico_repo = montar(monkeypatch, projeto)

    mudar_status_projeto_automaticamente(None, 7, "envio_tep")

    assert projeto_repo.atualizado_com is None
    assert historico_repo.criado is None


def test_nao_quebra_com_projeto_inexistente(monkeypatch):
    projeto_repo, historico_repo = montar(monkeypatch, None)

    mudar_status_projeto_automaticamente(None, 999, "envio_tep")

    assert projeto_repo.atualizado_com is None
    assert historico_repo.criado is None

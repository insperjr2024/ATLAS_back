"""Abrir a declaração de interesse à mão avisa os consultores (2026-10-14)."""

from types import SimpleNamespace

from src.use_cases.projeto import update_configuracoes as mod


def _uc(monkeypatch, aberta_hoje, avisos):
    uc = mod.UpdateVagasAbertasUseCase.__new__(mod.UpdateVagasAbertasUseCase)
    uc.db = None
    estado = SimpleNamespace(id=1, vagas_abertas=aberta_hoje)

    def update(pid, **kw):
        estado.vagas_abertas = kw["vagas_abertas"]
        return estado

    uc.repository = SimpleNamespace(get_by_id=lambda pid: estado, update=update)
    monkeypatch.setattr(mod.notificar_projeto, "vagas_abertas", lambda db, projeto: avisos.append(projeto.id))
    return uc


def test_fechado_para_aberto_avisa(monkeypatch):
    avisos = []
    resposta = _uc(monkeypatch, False, avisos).execute(1, mod.UpdateVagasAbertasRequest(vagas_abertas=True))
    assert resposta == {"id": 1, "vagas_abertas": True}
    assert avisos == [1]


def test_aberto_de_novo_nao_repete(monkeypatch):
    avisos = []
    _uc(monkeypatch, True, avisos).execute(1, mod.UpdateVagasAbertasRequest(vagas_abertas=True))
    assert avisos == []


def test_fechar_nao_avisa(monkeypatch):
    avisos = []
    _uc(monkeypatch, True, avisos).execute(1, mod.UpdateVagasAbertasRequest(vagas_abertas=False))
    assert avisos == []

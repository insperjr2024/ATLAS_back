"""Gestão adiciona alguém numa banca JÁ REALIZADA (`CreateCandidaturaUseCase`,
`eh_gestao=True`) — corrige a ficha depois do fato, dentro da janela de
`PRAZO_AVALIACAO_DIAS`.

⭐ 2026-09-16, a pedido: a pessoa nasce PRESENTE (`confirmado=True`), não
"faltou". Desde que o botão manual de "Registrar realização" saiu
(2026-09-04), ninguém mais marca presença à mão — a finalização automática
já presume presente todo mundo que era candidato na hora
(`finalizacao_automatica.py`), e essa banca já passou por ela. Sem o default
aqui, a pessoa ficava com `confirmado=False` pra sempre: aparecia "· faltou"
na ficha e contava errado nas estatísticas de presença, mesmo continuando
livre pra preencher a avaliação (isso nunca foi bloqueado por `confirmado`).
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.candidatura import create_candidatura as mod
from src.use_cases.candidatura.create_candidatura import (
    CreateCandidaturaRequest,
    CreateCandidaturaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def montar(monkeypatch, *, realizado_em, candidaturas_existentes=()):
    # A conta de teto (`calcular_vagas_banca`) consulta a combinação de
    # frentes no banco — sem sessão de verdade aqui, fixamos um teto folgado
    # (o assunto deste arquivo é o default de `confirmado`, não o teto).
    monkeypatch.setattr(mod, "calcular_vagas_banca", lambda *a, **k: 10)
    banca = SimpleNamespace(
        id=1,
        nome_projeto="ATLAS I",
        data_hora=realizado_em,
        realizado_em=realizado_em,
        coordenador_id=None,
    )

    class FakeCandidaturaRepo:
        def __init__(self, existentes):
            self._existentes = list(existentes)
            self.criadas = []

        def get_by_banca(self, _):
            return [SimpleNamespace(usuario_id=uid) for uid in self._existentes]

        def create(self, **kw):
            self.criadas.append(kw)
            return SimpleNamespace(id=1, **kw)

    uc = CreateCandidaturaUseCase.__new__(CreateCandidaturaUseCase)
    uc.db = None
    repo = FakeCandidaturaRepo(candidaturas_existentes)
    uc.repository = repo
    uc.banca_repository = SimpleNamespace(get_by_id=lambda _: banca)
    # Banca sem frente vinculada: a reserva de vaga (testada à parte em
    # test_vaga_reservada_pro_piso.py) não entra aqui, de propósito — o
    # assunto deste arquivo é só o default de `confirmado`.
    uc.banca_frente_repository = SimpleNamespace(get_by_banca=lambda _: [])
    uc.frente_repository = SimpleNamespace(get_by_id=lambda fid: None)
    uc.configuracao_repository = SimpleNamespace(
        get=lambda: SimpleNamespace(vagas_por_banca=10)
    )
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _: [])
    uc.escopo_repository = SimpleNamespace(get_by_id=lambda _: None)
    uc.membro_repository = SimpleNamespace(get_by_projeto=lambda *a, **k: [])
    uc.equipe_projeto_repository = SimpleNamespace(get_by_banca=lambda _: [])
    return uc, repo


def test_gestao_adiciona_apos_realizada_nasce_presente(monkeypatch):
    uc, repo = montar(monkeypatch, realizado_em=datetime.now() - timedelta(days=1))

    uc.execute(
        CreateCandidaturaRequest(banca_id=1, usuario_id=13),
        usuario_id=13,
        eh_gestao=True,
    )

    assert repo.criadas[0]["confirmado"] is True


def test_autoinscricao_normal_continua_sem_presenca_por_padrao(monkeypatch):
    """Fora do caso "gestão + já realizada", nada muda: quem se inscreve numa
    banca que ainda vai acontecer não é presumido presente."""
    uc, repo = montar(monkeypatch, realizado_em=None)
    uc.banca_repository = SimpleNamespace(
        get_by_id=lambda _: SimpleNamespace(
            id=1, nome_projeto="ATLAS I", data_hora=datetime.now() + timedelta(days=3),
            realizado_em=None, coordenador_id=None,
        )
    )

    uc.execute(CreateCandidaturaRequest(banca_id=1), usuario_id=13, eh_gestao=False)

    assert repo.criadas[0]["confirmado"] is False


def test_gestao_apos_prazo_de_avaliacao_e_recusado(monkeypatch):
    from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS

    uc, repo = montar(
        monkeypatch, realizado_em=datetime.now() - timedelta(days=PRAZO_AVALIACAO_DIAS + 1)
    )

    with pytest.raises(RegraDeNegocioError, match="prazo"):
        uc.execute(
            CreateCandidaturaRequest(banca_id=1, usuario_id=13),
            usuario_id=13,
            eh_gestao=True,
        )
    assert repo.criadas == []

"""Criar projeto institucional (Agro etc.) — só nome, sem frente/equipe/
escopo (§ Contratos, 2026-09-21).

Mesmo idioma dos vizinhos: `__new__` + repositórios fake, notificação
trocada por espião.
"""

from datetime import datetime
from types import SimpleNamespace

import src.use_cases.projeto.create_projeto_institucional as mod
from src.use_cases.projeto.create_projeto_institucional import (
    CreateProjetoInstitucionalRequest,
    CreateProjetoInstitucionalUseCase,
)


class FakeProjetoRepo:
    def __init__(self, db): pass
    def create(self, **kwargs):
        # Simula os defaults de coluna que a linha real ganharia no banco
        # (o use case só passa nome/cliente/institucional/status/criado_por).
        padroes = dict(
            cliente=None,
            criado_em=datetime.now(),
            max_consultores=3,
            data_kickoff=None,
            data_inicio_ambientacao=None,
            arquivado_em=None,
            historico_oculto_ate=None,
        )
        padroes.update(kwargs)
        return SimpleNamespace(id=1, **padroes)


class FakeHistoricoRepo:
    def __init__(self, db): pass
    def create(self, **kwargs):
        self.criado = kwargs
        return SimpleNamespace(**kwargs)


class FakeFrenteRepo:
    def __init__(self, db): pass
    def get_by_projeto(self, _projeto_id):
        return []


class FakeMembroRepo:
    def __init__(self, db): pass
    def get_by_projeto(self, _projeto_id, apenas_atuais=False):
        return []


def montar(monkeypatch):
    monkeypatch.setattr(mod, "ProjetoRepository", FakeProjetoRepo)
    monkeypatch.setattr(mod, "ProjetoStatusHistoricoRepository", FakeHistoricoRepo)
    monkeypatch.setattr(mod, "ProjetoFrenteRepository", FakeFrenteRepo)
    monkeypatch.setattr(mod, "ProjetoMembroRepository", FakeMembroRepo)

    chamadas_notificacao = []
    monkeypatch.setattr(mod, "projeto_criado", lambda db, projeto: chamadas_notificacao.append(projeto.id))

    return CreateProjetoInstitucionalUseCase(db=None), chamadas_notificacao


class TestExecute:
    def test_cria_so_com_nome_marcado_institucional_em_contrato_em_elaboracao(self, monkeypatch):
        uc, _ = montar(monkeypatch)

        resultado = uc.execute(CreateProjetoInstitucionalRequest(nome="Parceria Agro"), criado_por=9)

        assert resultado["nome"] == "Parceria Agro"
        assert resultado["status"] == "contrato_em_elaboracao"
        assert resultado["frente_ids"] == []

    def test_aceita_cliente_opcional(self, monkeypatch):
        uc, _ = montar(monkeypatch)

        resultado = uc.execute(
            CreateProjetoInstitucionalRequest(nome="Parceria Agro", cliente="Agro Insper"),
            criado_por=9,
        )

        assert resultado["cliente"] == "Agro Insper"

    def test_dispara_notificacao_de_projeto_criado(self, monkeypatch):
        uc, chamadas = montar(monkeypatch)

        uc.execute(CreateProjetoInstitucionalRequest(nome="Parceria Agro"), criado_por=9)

        assert chamadas == [1]

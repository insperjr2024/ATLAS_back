"""A mesma pessoa não pode virar candidata duas vezes da mesma banca
(2026-09-16).

Nada barrava isso antes: um duplo-clique em "Alocar-se", ou a gestão
adicionando quem já estava lá, criava outra linha `candidatura` igual, sem
erro nenhum — foi assim que uma consultora apareceu 4x na ficha do GELATTO,
e alguém teve que apagar as duplicatas à mão.

Mesmo padrão dos vizinhos: `__new__` + repositórios fake, sem sessão de
banco. `test_alocacao_sem_teto_por_frente.py` e `test_vaga_reservada_pro_
piso.py` cobrem as regras de vaga/composição; aqui o que se prende é só a
duplicata.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from src.use_cases.candidatura import create_candidatura as mod
from src.use_cases.candidatura.create_candidatura import (
    CreateCandidaturaRequest,
    CreateCandidaturaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def montar(monkeypatch, *, alocados):
    monkeypatch.setattr(mod, "calcular_vagas_banca", lambda *a, **k: 10)
    monkeypatch.setattr(
        "src.use_cases.configuracao.composicao_banca.ResolverComposicaoUseCase.para",
        lambda self, ids: [],
    )
    monkeypatch.setattr(
        "src.utils.composicao_banca.ComposicaoBancaChecker.verificar",
        lambda self, banca, regras, ids: SimpleNamespace(deficits=[]),
    )

    class FakeCandidaturaRepo:
        def __init__(self):
            self.criadas = []

        def get_by_banca(self, _banca_id):
            return [SimpleNamespace(usuario_id=uid) for uid in alocados]

        def create(self, **kwargs):
            self.criadas.append(kwargs["usuario_id"])
            return SimpleNamespace(id=1, **kwargs)

    banca = SimpleNamespace(
        id=1,
        nome_projeto="GELATTO",
        data_hora=datetime.now() + timedelta(days=3),
        realizado_em=None,
        coordenador_id=None,
    )

    uc = CreateCandidaturaUseCase.__new__(CreateCandidaturaUseCase)
    uc.db = None
    repo = FakeCandidaturaRepo()
    uc.repository = repo
    uc.banca_repository = SimpleNamespace(get_by_id=lambda _id: banca)
    uc.configuracao_repository = SimpleNamespace(get=lambda: SimpleNamespace(vagas_por_banca=10))
    uc.banca_frente_repository = SimpleNamespace(get_by_banca=lambda _id: [])
    uc.frente_repository = SimpleNamespace(get_by_id=lambda fid: None)
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _id: [])
    uc.escopo_repository = SimpleNamespace(get_by_id=lambda _id: None)
    uc.membro_repository = SimpleNamespace(get_by_projeto=lambda *a, **k: [])
    uc.equipe_projeto_repository = SimpleNamespace(get_by_banca=lambda _id: [])
    return uc, repo


def alocar(uc, usuario_id, eh_gestao=False):
    return uc.execute(
        CreateCandidaturaRequest(banca_id=1), usuario_id=usuario_id, eh_gestao=eh_gestao
    )


class TestNaoDuplica:
    def test_recusa_autoinscricao_de_quem_ja_e_candidato(self, monkeypatch):
        uc, repo = montar(monkeypatch, alocados=(10, 11))

        with pytest.raises(RegraDeNegocioError, match="já é candidata"):
            alocar(uc, 10)

        assert repo.criadas == []

    def test_recusa_mesmo_quando_e_a_gestao_adicionando(self, monkeypatch):
        """Não existe motivo legítimo pra duas candidaturas da mesma pessoa
        na mesma banca — vale pra gestão também, não só pra autoinscrição."""
        uc, repo = montar(monkeypatch, alocados=(10, 11))

        with pytest.raises(RegraDeNegocioError, match="já é candidata"):
            alocar(uc, 10, eh_gestao=True)

        assert repo.criadas == []

    def test_pessoa_nova_continua_entrando_normalmente(self, monkeypatch):
        uc, repo = montar(monkeypatch, alocados=(10, 11))

        alocar(uc, 12)

        assert repo.criadas == [12]


class TestRedeDeSegurancaDoRepositorio:
    """A checagem do use case olha `candidaturas_existentes` já carregada —
    dois cliques quase simultâneos podem passar por ela antes de qualquer um
    commitar. A constraint `uq_candidatura_banca_usuario` é quem garante de
    verdade; o repositório traduz o `IntegrityError` dela num erro de
    negócio, não deixa estourar cru pro chamador."""

    def test_integrity_error_vira_erro_de_negocio(self, monkeypatch):
        from src.repositories.candidatura_repository import CandidaturaRepository

        repo = CandidaturaRepository.__new__(CandidaturaRepository)

        class FakeSessionQueBate(SimpleNamespace):
            def add(self, _obj):
                pass

            def commit(self):
                raise IntegrityError("INSERT", {}, Exception("duplicate key"))

            def rollback(self):
                self.rolled_back = True

        sessao = FakeSessionQueBate(rolled_back=False)
        repo.db = sessao

        with pytest.raises(RegraDeNegocioError, match="já é candidata"):
            repo.create(banca_id=1, usuario_id=10, criado_em=datetime.now())

        assert sessao.rolled_back is True

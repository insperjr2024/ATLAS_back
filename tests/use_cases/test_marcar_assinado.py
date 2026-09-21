"""Marcar como assinado / arquivar / aceite tácito do TEP (§ Contratos, 2026-09-18).

Mesmo idioma dos vizinhos: `__new__` + repositórios fake.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import src.use_cases.documento_contratual.marcar_assinado as marcar_assinado_mod
from src.use_cases.documento_contratual.marcar_assinado import (
    MarcarAssinadoDocumentoContratualUseCase,
    dias_restantes_aceite_tacito,
)
from src.utils.exceptions import RegraDeNegocioError


@pytest.fixture(autouse=True)
def _mudanca_de_status_automatica(monkeypatch):
    # A lógica de dentro (idempotência, projeto pausado etc.) tem teste
    # próprio em test_mudar_status_projeto_automatico.py — aqui exigiria um
    # ProjetoRepository de verdade, que este arquivo não monta. O que ESTE
    # arquivo cobre é só: pra qual status cada TIPO de documento manda o
    # projeto (ou se manda) — daí o espião em vez de um no-op silencioso.
    chamadas = []
    monkeypatch.setattr(
        marcar_assinado_mod,
        "mudar_status_projeto_automaticamente",
        lambda db, projeto_id, status_novo: chamadas.append((projeto_id, status_novo)),
    )
    # Idem pra notificação de "virou vendido" — tem teste próprio em
    # test_notificar_projeto.py.
    monkeypatch.setattr(marcar_assinado_mod, "projeto_vendido", lambda *a, **k: None)
    return chamadas


class FakeDocumentoRepo:
    def __init__(self, documento):
        self._documento = documento

    def get_by_id(self, _id):
        return self._documento

    def update(self, _id, **kwargs):
        for chave, valor in kwargs.items():
            setattr(self._documento, chave, valor)
        return self._documento


class FakeVersaoRepo:
    def __init__(self, versao):
        self._versao = versao
        self.marcada = None

    def ultima_versao_obj(self, _documento_id):
        return self._versao

    def marcar_final(self, versao, gestao_id):
        versao.status_arquivo = "final_assinado"
        versao.gestao_id = gestao_id
        self.marcada = versao
        return versao


class FakeSemestreRepo:
    def __init__(self, semestre):
        self._semestre = semestre

    def get_por_data(self, _data):
        return self._semestre

    def get_ativo(self):
        return self._semestre


def documento(tipo="contrato", status="aprovado_pelo_cliente", atualizado_em=None):
    return SimpleNamespace(
        id=1, projeto_id=7, tipo=tipo, status=status, atualizado_em=atualizado_em or datetime.now(),
        projeto=SimpleNamespace(id=7, nome="Projeto Alfa"),
    )


_PADRAO = object()


def montar(doc, versao=_PADRAO, semestre=_PADRAO):
    uc = MarcarAssinadoDocumentoContratualUseCase.__new__(MarcarAssinadoDocumentoContratualUseCase)
    uc.db = None
    uc.documentos = FakeDocumentoRepo(doc)
    uc.versoes = FakeVersaoRepo(SimpleNamespace(id=9) if versao is _PADRAO else versao)
    uc.semestres = FakeSemestreRepo(SimpleNamespace(id=5) if semestre is _PADRAO else semestre)
    return uc


class TestExecute:
    def test_marca_assinado_e_arquiva_a_ultima_versao(self):
        doc = documento()
        uc = montar(doc)

        atualizado = uc.execute(1)

        assert atualizado.status == "assinado_e_arquivado"
        assert atualizado.gestao_id == 5
        assert uc.versoes.marcada.status_arquivo == "final_assinado"

    def test_contrato_assinado_move_o_projeto_pra_vendido(self, _mudanca_de_status_automatica):
        doc = documento(tipo="contrato")
        uc = montar(doc)

        uc.execute(1)

        assert _mudanca_de_status_automatica == [(7, "vendido")]

    def test_tep_assinado_move_o_projeto_pra_periodo_de_ajustes(self, _mudanca_de_status_automatica):
        doc = documento(tipo="tep")
        uc = montar(doc)

        uc.execute(1)

        assert _mudanca_de_status_automatica == [(7, "periodo_ajustes")]

    def test_outros_tipos_nao_movem_o_projeto(self, _mudanca_de_status_automatica):
        for tipo in ("nda", "uso_imagem", "aditivo"):
            doc = documento(tipo=tipo)
            uc = montar(doc)

            uc.execute(1)

        assert _mudanca_de_status_automatica == []

    def test_recusa_fora_de_aprovado_pelo_cliente(self):
        doc = documento(status="em_revisao_interna")
        uc = montar(doc)

        with pytest.raises(RegraDeNegocioError, match="aprovado_pelo_cliente"):
            uc.execute(1)

    def test_funciona_mesmo_sem_semestre_ativo(self):
        doc = documento()
        uc = montar(doc, semestre=None)

        atualizado = uc.execute(1)

        assert atualizado.gestao_id is None


class TestConsiderarAceitoPorPrazo:
    def test_so_se_aplica_ao_tep(self):
        doc = documento(tipo="contrato")
        uc = montar(doc)

        with pytest.raises(RegraDeNegocioError, match="só se aplica ao TEP"):
            uc.considerar_aceito_por_prazo(1)

    def test_recusa_com_prazo_ainda_nao_vencido(self):
        doc = documento(tipo="tep", atualizado_em=datetime.now())
        uc = montar(doc)

        with pytest.raises(RegraDeNegocioError, match="Ainda faltam"):
            uc.considerar_aceito_por_prazo(1)

    def test_aceita_com_prazo_vencido(self):
        doc = documento(tipo="tep", atualizado_em=datetime.now() - timedelta(days=6))
        uc = montar(doc)

        atualizado = uc.considerar_aceito_por_prazo(1)

        assert atualizado.status == "assinado_e_arquivado"


class TestDiasRestantesAceiteTacito:
    def test_none_fora_do_tep(self):
        assert dias_restantes_aceite_tacito(documento(tipo="contrato")) is None

    def test_none_fora_de_aprovado_pelo_cliente(self):
        assert dias_restantes_aceite_tacito(documento(tipo="tep", status="em_revisao_interna")) is None

    def test_conta_a_partir_da_aprovacao(self):
        doc = documento(tipo="tep", atualizado_em=datetime.now() - timedelta(days=2))
        assert dias_restantes_aceite_tacito(doc) == 3

    def test_negativo_quando_vencido(self):
        doc = documento(tipo="tep", atualizado_em=datetime.now() - timedelta(days=10))
        assert dias_restantes_aceite_tacito(doc) < 0

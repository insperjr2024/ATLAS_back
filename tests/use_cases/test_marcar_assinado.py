"""Marcar como assinado / arquivar / aceite tácito do TEP (§ Contratos, 2026-09-18).

Mesmo idioma dos vizinhos: `__new__` + repositórios fake.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.documento_contratual.marcar_assinado import (
    MarcarAssinadoDocumentoContratualUseCase,
    dias_restantes_aceite_tacito,
)
from src.utils.exceptions import RegraDeNegocioError


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
        id=1, tipo=tipo, status=status, atualizado_em=atualizado_em or datetime.now()
    )


_PADRAO = object()


def montar(doc, versao=_PADRAO, semestre=_PADRAO):
    uc = MarcarAssinadoDocumentoContratualUseCase.__new__(MarcarAssinadoDocumentoContratualUseCase)
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

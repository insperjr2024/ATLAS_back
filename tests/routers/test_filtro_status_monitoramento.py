"""O filtro de status do Monitoramento — o que a rota aceita e o que ela recusa.

O filtro nasceu multi-valor (`?status=ambientacao&status=em_andamento`) porque
"o que está tocando agora?" é uma pergunta só, e responder com duas requisições
obrigaria a tela a somar KPI de dois payloads — o placar de gestão e os
percentuais são médias sobre bases diferentes, não somam.

Os dois casos que este arquivo protege são os dois jeitos de o filtro MENTIR:

- valor desconhecido ignorado em silêncio, que devolveria o portfólio inteiro
  com o seletor marcado na tela;
- lista vazia virando `IN ()`, que esvaziaria a tela sem ninguém ter escolhido.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routers.monitoramento import filtro_status
from src.use_cases.monitoramento import monitoramento as mod
from src.utils.status_projeto import STATUS_VALIDOS


class TestFiltroStatusValida:
    def test_sem_parametro_e_none(self):
        """Ausente = todas as etapas. `None` é o que o use case lê como
        "não filtre", e é diferente de lista vazia."""
        assert filtro_status(None) is None

    def test_lista_vazia_tambem_e_none(self):
        """`?status=` sem valor não pode virar `IN ()`: a tela ficaria vazia
        sem a pessoa ter escolhido nenhuma etapa."""
        assert filtro_status([]) is None

    @pytest.mark.parametrize("status", STATUS_VALIDOS)
    def test_todo_status_do_ciclo_passa(self, status):
        """Inclusive `pausado`, que não está em `STATUS_ORDEM` por ser estado
        à parte, mas é um valor real da coluna `projeto.status`."""
        assert filtro_status([status]) == [status]

    def test_varios_de_uma_vez(self):
        assert filtro_status(["ambientacao", "em_andamento"]) == [
            "ambientacao",
            "em_andamento",
        ]

    def test_repetido_sai_uma_vez_na_ordem_marcada(self):
        """`set` resolveria o duplicado mas embaralharia a URL entre duas
        requisições idênticas."""
        assert filtro_status(["em_andamento", "ambientacao", "em_andamento"]) == [
            "em_andamento",
            "ambientacao",
        ]

    def test_desconhecido_da_422(self):
        """Não pode ser ignorado: filtro ignorado devolve o núcleo inteiro e
        quem olha lê o número do núcleo achando que é o da etapa."""
        with pytest.raises(HTTPException) as erro:
            filtro_status(["em_progresso"])
        assert erro.value.status_code == 422
        assert "em_progresso" in erro.value.detail

    def test_um_invalido_no_meio_derruba_a_consulta_inteira(self):
        """Descartar só o inválido e seguir com o resto daria um recorte que
        ninguém pediu, sem nenhum aviso na tela."""
        with pytest.raises(HTTPException):
            filtro_status(["ambientacao", "etapa_que_nao_existe"])

    def test_status_e_case_sensitive(self):
        """O valor é a chave do Enum da coluna, não o rótulo da tela."""
        with pytest.raises(HTTPException):
            filtro_status(["Ambientacao"])


class QueryFake:
    """Registra cada `.filter()` — é o único jeito de ver se o `IN` de status
    entrou ou não, sem subir banco."""

    def __init__(self):
        self.criterios = []

    def filter(self, criterio):
        self.criterios.append(str(criterio))
        return self

    def all(self):
        return []

    @property
    def sql_dos_filtros(self) -> str:
        return " | ".join(self.criterios)


@pytest.fixture
def base(monkeypatch):
    """`_BaseMonitoramento` com o recorte de visão neutralizado: aqui o assunto
    é só o `WHERE` de status que `_projetos_visiveis` acrescenta."""
    query = QueryFake()
    monkeypatch.setattr(mod, "aplicar_recorte_visao", lambda q, *a, **k: q)

    class DbFake:
        def query(self, *_):
            return query

    instancia = mod._BaseMonitoramento.__new__(mod._BaseMonitoramento)
    instancia.db = DbFake()
    return instancia, query


class TestProjetosVisiveisAplicaOStatus:
    def test_sem_status_nao_acrescenta_where(self, base):
        instancia, query = base
        instancia._projetos_visiveis(SimpleNamespace(), None, None, None)
        assert "status IN" not in query.sql_dos_filtros

    def test_lista_vazia_nao_acrescenta_where(self, base):
        """A defesa de dentro, irmã da `filtro_status([]) is None`: mesmo que
        uma lista vazia escape da rota, ela não pode virar `IN ()`."""
        instancia, query = base
        instancia._projetos_visiveis(SimpleNamespace(), None, None, [])
        assert "status IN" not in query.sql_dos_filtros

    def test_com_status_filtra_no_banco(self, base):
        """No banco, e não em Python depois: a Alocação recorta a população
        por esta mesma lista, e um filtro aplicado só na saída de uma aba
        divergiria da outra."""
        instancia, query = base
        instancia._projetos_visiveis(
            SimpleNamespace(), None, None, ["ambientacao", "em_andamento"]
        )
        assert "status IN" in query.sql_dos_filtros

    def test_arquivado_continua_fora_mesmo_com_status(self, base):
        """Projeto arquivado é histórico (§12) — o filtro de status não pode
        ser um jeito de trazê-lo de volta para os KPIs da gestão atual."""
        instancia, query = base
        instancia._projetos_visiveis(SimpleNamespace(), None, None, ["finalizado"])
        assert "arquivado_em IS NULL" in query.sql_dos_filtros

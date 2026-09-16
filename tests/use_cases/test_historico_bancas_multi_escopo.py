"""2026-09-16, a pedido — banca pode cobrir MAIS de um escopo do projeto de
uma sentada (`banca_escopo`). `escopo_id` sozinho é só o campo legado de UM,
e o histórico mandava só ele — uma banca como a BLEND I, com Análise
Mercadológica E Pesquisa Legislativa, aparecia no Dashboard Bancas como se
só cobrisse a primeira.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.use_cases.banca.get_historico_bancas import GetHistoricoBancasUseCase

ONTEM = datetime.now() - timedelta(days=1)


def banca(id, *, escopo_id=None):
    return SimpleNamespace(
        id=id,
        nome_projeto=f"Projeto {id}",
        escopo_id=escopo_id,
        coordenador_id=1,
        data_hora=ONTEM,
        realizado_em=ONTEM,
        cancelada_em=None,
        descricao_coordenador=None,
        descricao_coordenador_enviada_em=None,
        resultado=None,
    )


def projeto_escopo(id, nome):
    return SimpleNamespace(id=id, nome_customizado=nome, escopo_id=None)


def _uc(*, bancas, escopo_ids_por_banca, projetos_escopo, escopo_legado=None):
    uc = GetHistoricoBancasUseCase.__new__(GetHistoricoBancasUseCase)
    uc.banca_repository = SimpleNamespace(get_all=lambda: bancas)
    uc.equipe_projeto_repository = SimpleNamespace(get_all=lambda: [])
    uc.semestre_repository = SimpleNamespace(get_all=lambda: [])
    uc.avaliacao_nota_repository = SimpleNamespace(get_by_banca=lambda _id: [])
    uc.banca_escopo_repository = SimpleNamespace(
        get_escopo_ids_por_banca=lambda _ids: escopo_ids_por_banca
    )
    uc.escopo_repository = SimpleNamespace(
        get_by_ids=lambda ids: [pe for pe in projetos_escopo if pe.id in ids]
    )
    uc.catalogo_repository = SimpleNamespace(
        get_by_id=lambda _id: escopo_legado
    )
    return uc


def test_banca_com_dois_escopos_mostra_os_dois():
    uc = _uc(
        bancas=[banca(1)],
        escopo_ids_por_banca={1: [10, 11]},
        projetos_escopo=[
            projeto_escopo(10, "Análise Mercadológica"),
            projeto_escopo(11, "Pesquisa Legislativa"),
        ],
    )

    resultado = uc.execute()

    assert resultado[0]["escopos"] == ["Análise Mercadológica", "Pesquisa Legislativa"]


def test_banca_legada_sem_banca_escopo_usa_o_catalogo():
    uc = _uc(
        bancas=[banca(1, escopo_id=5)],
        escopo_ids_por_banca={},
        projetos_escopo=[],
        escopo_legado=SimpleNamespace(id=5, nome="Direito Tributário"),
    )

    resultado = uc.execute()

    assert resultado[0]["escopos"] == ["Direito Tributário"]


def test_banca_sem_escopo_nenhum_devolve_lista_vazia():
    uc = _uc(bancas=[banca(1)], escopo_ids_por_banca={}, projetos_escopo=[])

    resultado = uc.execute()

    assert resultado[0]["escopos"] == []

"""2026-10-12, corrigido: a Avaliação do Escopo nunca pode cair na visão por
pessoa do painel como "Fulano avaliou Fulano". A marca `eh_escopo` vem
sempre que o formulário é de escopo, mesmo quando não dá pra saber QUAL
escopo foi avaliado (`escopo` ausente).
"""

from types import SimpleNamespace

import src.use_cases.desempenho_avaliacao.get_avaliacao as mod
from src.use_cases.desempenho_avaliacao.get_avaliacao import ListDesempenhoAvaliacoesUseCase

FORM_ESCOPO = 50
FORM_PARES = 10


def avaliacao(id, avaliador, avaliado, formulario, lote=1, projeto_escopo_id=None):
    return SimpleNamespace(
        id=id, lote_id=lote, formulario_id=formulario, avaliador_id=avaliador, avaliado_id=avaliado,
        projeto_escopo_id=projeto_escopo_id, nota_geral=4.0, comentarios=None, criado_em=None,
    )


def _uc(monkeypatch, avaliacoes, escopos_do_lote):
    monkeypatch.setattr(mod, "ids_dos_formularios_de_escopo", lambda repo: {FORM_ESCOPO})
    uc = ListDesempenhoAvaliacoesUseCase.__new__(ListDesempenhoAvaliacoesUseCase)
    uc.repository = SimpleNamespace(get_all=lambda: avaliacoes)
    uc.formulario_repo = None
    uc.usuario_frente_repo = SimpleNamespace(get_all=lambda: [SimpleNamespace(usuario_id=7, frente_id=99)])
    uc._escopos_por_lote = lambda lote_ids: {1: escopos_do_lote}
    return uc


def escopo(id, frente):
    return {"escopo_id": id, "nome": f"Escopo {id}", "frente_id": frente, "projeto_nome": "CONEXÕES I"}


def test_escopo_nao_identificado_continua_marcado_como_escopo(monkeypatch):
    # Dois escopos no lote, nenhum da frente da avaliadora: não dá pra
    # desambiguar, `escopo` fica de fora, mas a marca vem.
    uc = _uc(monkeypatch, [avaliacao(1, 7, 7, FORM_ESCOPO)], [escopo(1, 1), escopo(2, 2)])

    (linha,) = uc.execute()

    assert linha["eh_escopo"] is True
    assert "escopo" not in linha


def test_escopo_identificado_vem_marcado_e_com_o_escopo(monkeypatch):
    uc = _uc(monkeypatch, [avaliacao(1, 7, 7, FORM_ESCOPO)], [escopo(1, 99), escopo(2, 2)])

    (linha,) = uc.execute()

    assert linha["eh_escopo"] is True
    assert linha["escopo"]["escopo_id"] == 1


def test_avaliacao_entre_pessoas_nao_e_escopo(monkeypatch):
    uc = _uc(
        monkeypatch,
        [avaliacao(1, 7, 8, FORM_PARES), avaliacao(2, 7, 7, FORM_ESCOPO)],
        [escopo(1, 99)],
    )

    pares, auto = uc.execute()

    assert pares["eh_escopo"] is False
    assert auto["eh_escopo"] is True


# ---------------------------------------------------------------- escopo "Outro"
#
# 2026-10-12: Pesquisa Legislativa de CONEXÕES I foi vendido como "Outro"
# (nome digitado, sem `escopo_id`). A listagem descartava esse escopo, e a
# avaliação da pessoa ficava sem escopo identificado.

CATALOGO = {
    17: SimpleNamespace(id=17, nome="Pesquisa Legislativa", frente_id=3),
    14: SimpleNamespace(id=14, nome="Plano Operacional", frente_id=1),
}


def _uc_escopos(vendidos):
    uc = ListDesempenhoAvaliacoesUseCase.__new__(ListDesempenhoAvaliacoesUseCase)
    uc.projeto_escopo_repo = SimpleNamespace(get_by_id=lambda i: vendidos.get(i))
    uc.escopo_repo = SimpleNamespace(get_by_id=lambda i: CATALOGO.get(i), get_all=lambda: list(CATALOGO.values()))
    uc.projeto_repo = SimpleNamespace(get_by_id=lambda i: SimpleNamespace(nome="CONEXÕES I"))
    return uc


def vendido(id, escopo_id=None, nome_customizado=None, frente_id=3):
    return SimpleNamespace(id=id, projeto_id=1, escopo_id=escopo_id, nome_customizado=nome_customizado, frente_id=frente_id)


def test_outro_com_nome_do_catalogo_vira_a_entrada_do_catalogo():
    uc = _uc_escopos({57: vendido(57, nome_customizado="  pesquisa  legislativa ")})

    assert uc._escopo_do_catalogo(57) == {
        "escopo_id": 17,
        "nome": "Pesquisa Legislativa",
        "projeto_nome": "CONEXÕES I",
    }


def test_outro_sem_par_no_catalogo_usa_o_nome_digitado():
    uc = _uc_escopos({60: vendido(60, nome_customizado="Due Diligence Societária")})

    assert uc._escopo_do_catalogo(60) == {
        "escopo_id": None,
        "nome": "Due Diligence Societária",
        "projeto_nome": "CONEXÕES I",
    }


def test_escopo_do_catalogo_continua_igual():
    uc = _uc_escopos({56: vendido(56, escopo_id=14, frente_id=1)})

    assert uc._escopo_do_catalogo(56)["escopo_id"] == 14


def test_outro_entra_nos_escopos_do_lote_pra_desambiguar_pela_frente():
    """Lote sem banca, avaliação antiga sem `projeto_escopo_id`: os escopos
    do lote precisam incluir o "Outro", senão a frente de Direito não acha
    o dela."""
    vendidos = {56: vendido(56, escopo_id=14, frente_id=1), 57: vendido(57, nome_customizado="Pesquisa Legislativa")}
    uc = _uc_escopos(vendidos)
    uc.lote_repo = SimpleNamespace(get_by_id=lambda i: SimpleNamespace(id=i, banca_id=None))
    uc.lote_projeto_repo = SimpleNamespace(get_projeto_ids=lambda i: [1])
    for pe in vendidos.values():
        pe.status = mod.STATUS_ESCOPO_EM_ANDAMENTO
    uc.projeto_escopo_repo.get_by_projetos = lambda ids: list(vendidos.values())

    escopos = uc._escopos_por_lote({1})[1]

    assert {(e["escopo_id"], e["frente_id"]) for e in escopos} == {(14, 1), (17, 3)}

"""Resultados da banca sem autor (2026-10-16): o que sai e o que fica."""

from src.utils.resultado_banca import anonimizar_resultados, ocultar_resultados


def ficha():
    return {
        "id": 35,
        "nota_final": 4.2,
        "avaliadores": [
            {"usuario_id": 7, "nome": "Ana", "ja_enviou": True, "comentario_feedback": "texto da Ana"},
            {"usuario_id": 8, "nome": "Bia", "ja_enviou": True, "comentario_feedback": "texto da Bia"},
            {"usuario_id": 9, "nome": "Caio", "ja_enviou": False, "comentario_feedback": None},
        ],
        "avaliacoes": [
            {"id": 101, "avaliador": "Ana", "avaliador_id": 7, "sessao": 1, "comentario_feedback": "texto da Ana", "submetida_em": "2026-10-10T10:00:00", "notas": [{"pergunta": "Clareza", "ordem": 1, "nota": 4.0, "resposta_texto": None}]},
            {"id": 102, "avaliador": "Bia", "avaliador_id": 8, "sessao": 1, "comentario_feedback": "texto da Bia", "submetida_em": "2026-10-11T10:00:00", "notas": []},
            {"id": 103, "avaliador": "Dudu", "avaliador_id": 10, "sessao": 2, "comentario_feedback": None, "submetida_em": None, "notas": []},
        ],
    }


def test_anonimizar_tira_autor_e_mantem_nota_e_comentario():
    resultado = anonimizar_resultados(ficha(), leitor_id=99)

    assert resultado["avaliacoes_anonimas"] is True
    assert resultado["nota_final"] == 4.2
    assert len(resultado["avaliacoes"]) == 3
    for a in resultado["avaliacoes"]:
        assert a["avaliador"] is None
        assert a["avaliador_id"] is None
        assert a["submetida_em"] is None
    assert sorted(a["comentario_feedback"] or "" for a in resultado["avaliacoes"]) == ["", "texto da Ana", "texto da Bia"]
    assert [a["notas"] for a in resultado["avaliacoes"] if a["notas"]] == [[{"pergunta": "Clareza", "ordem": 1, "nota": 4.0, "resposta_texto": None}]]


def test_anonimizar_nao_vaza_o_id_original_e_separa_por_sessao():
    resultado = anonimizar_resultados(ficha(), leitor_id=99)

    assert [a["id"] for a in resultado["avaliacoes"]] == [1, 2, 3]
    assert [a["sessao"] for a in resultado["avaliacoes"]] == [1, 1, 2]


def test_anonimizar_e_estavel_entre_duas_chamadas():
    assert anonimizar_resultados(ficha(), 99)["avaliacoes"] == anonimizar_resultados(ficha(), 99)["avaliacoes"]


def test_anonimizar_some_com_o_comentario_dos_outros_em_avaliadores_mas_nao_o_meu():
    """`avaliadores[].comentario_feedback` ligaria nome a texto; só o da
    própria pessoa fica, pra aba mostrar "Sua avaliação"."""
    resultado = anonimizar_resultados(ficha(), leitor_id=8)

    por_id = {a["usuario_id"]: a for a in resultado["avaliadores"]}
    assert por_id[8]["comentario_feedback"] == "texto da Bia"
    assert por_id[7]["comentario_feedback"] is None
    assert por_id[7]["ja_enviou"] is True, "quem já enviou continua vindo: a tela só o mostra pra quem tem o dashboard"


def test_ocultar_tira_tudo_menos_o_meu_comentario():
    resultado = ocultar_resultados(ficha(), leitor_id=7)

    assert resultado["avaliacoes"] == []
    assert resultado["nota_final"] is None
    assert resultado["avaliacoes_anonimas"] is False
    por_id = {a["usuario_id"]: a for a in resultado["avaliadores"]}
    assert por_id[7]["comentario_feedback"] == "texto da Ana"
    assert por_id[8]["comentario_feedback"] is None


def test_aceita_ficha_sem_avaliacoes():
    vazia = {"id": 1, "nota_final": None, "avaliadores": [], "avaliacoes": []}
    assert anonimizar_resultados(dict(vazia), 1)["avaliacoes"] == []
    assert ocultar_resultados(dict(vazia), 1)["avaliacoes"] == []

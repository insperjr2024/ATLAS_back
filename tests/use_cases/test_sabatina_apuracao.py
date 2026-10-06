"""A conta da sabatina (`utils/sabatina_apuracao.py`): peso por posição,
percentual sobre os votos dados, "mais um" estrito, branco e falta."""

from types import SimpleNamespace

from src.utils.sabatina_apuracao import apurar, peso_da_posicao, peso_do_usuario, peso_padrao


def _c(id, usuario_id):
    return SimpleNamespace(id=id, usuario_id=usuario_id)


def _v(candidato_id, peso):
    return SimpleNamespace(candidato_id=candidato_id, peso=peso)


ANA, BIA = _c(1, 10), _c(2, 20)


def test_peso_padrao_por_posicao():
    assert peso_padrao("consultor") == 1
    assert peso_padrao("coordenador") == 2
    assert peso_padrao("gerente") == 2
    assert peso_padrao("diretor_projetos") == 3
    assert peso_padrao("diretor") == 3
    assert peso_padrao("presidente") == 3
    assert peso_padrao("bdr") == 1
    assert peso_padrao(None) == 1


def test_peso_gravado_vence_o_padrao():
    assert peso_da_posicao("consultor", {"consultor": 2}) == 2
    assert peso_da_posicao("gerente", {}) == 2


def test_cargo_extra_usa_o_maior_peso():
    # Consultor 2 + BDR 1 vota com 2; consultor 1 + BDR 2 também vota com 2.
    assert peso_do_usuario("consultor", "bdr", {"consultor": 2, "bdr": 1}) == 2
    assert peso_do_usuario("consultor", "bdr", {"consultor": 1, "bdr": 2}) == 2
    assert peso_do_usuario("consultor", None, {"consultor": 1, "bdr": 2}) == 1
    assert peso_do_usuario("coordenador", "bdr", {}) == 2


def test_candidato_unico_eleito_com_mais_da_metade():
    # 3 votos de consultor na Ana (3) e 1 em branco de diretor (3): 50% exato NÃO passa.
    votos = [_v(1, 1), _v(1, 1), _v(1, 1), _v(None, 3)]
    r = apurar([ANA], votos, 50)
    assert r["situacao"] == "ninguem_eleito"
    assert r["candidatos"][0]["percentual"] == 50.0
    assert r["candidatos"][0]["eleito"] is False

    # Mais um consultor na Ana: 4 de 7, passa.
    r = apurar([ANA], votos + [_v(1, 1)], 50)
    assert r["situacao"] == "eleito"
    assert r["eleito_candidato_id"] == 1
    assert r["candidatos"][0]["eleito"] is True


def test_ponderacao_muda_o_resultado():
    # Contagem crua: Ana 2 x Bia 1. Ponderado: Ana 2 (consultores) x Bia 3 (diretor).
    votos = [_v(1, 1), _v(1, 1), _v(2, 3)]
    r = apurar([ANA, BIA], votos, 50)
    linhas = {d["candidato_id"]: d for d in r["candidatos"]}
    assert linhas[1]["votos"] == 2 and linhas[1]["ponderado"] == 2
    assert linhas[2]["votos"] == 1 and linhas[2]["ponderado"] == 3
    assert r["eleito_candidato_id"] == 2
    assert r["candidatos"][0]["candidato_id"] == 2  # ordenado por ponderado


def test_percentual_configuravel_setenta():
    votos = [_v(1, 1)] * 7 + [_v(None, 1)] * 3  # Ana 70% exato
    assert apurar([ANA], votos, 70)["situacao"] == "ninguem_eleito"
    assert apurar([ANA], votos + [_v(1, 1)], 70)["situacao"] == "eleito"


def test_branco_conta_no_total_e_aparece_separado():
    r = apurar([ANA], [_v(1, 1), _v(None, 2)], 50)
    assert r["total_votos"] == 2
    assert r["total_ponderado"] == 3
    assert r["brancos"] == {"votos": 1, "ponderado": 2, "percentual": 66.7}
    assert r["situacao"] == "ninguem_eleito"


def test_sem_votos():
    r = apurar([ANA, BIA], [], 50)
    assert r["situacao"] == "sem_votos"
    assert r["eleito_candidato_id"] is None
    assert all(d["percentual"] == 0.0 and d["eleito"] is False for d in r["candidatos"])


def test_dois_passam_fica_o_mais_votado():
    # Percentual baixo de propósito: os dois passam de 30%, só o maior é eleito.
    votos = [_v(1, 1)] * 4 + [_v(2, 1)] * 5 + [_v(None, 1)]
    r = apurar([ANA, BIA], votos, 30)
    assert r["eleito_candidato_id"] == 2
    assert [d["eleito"] for d in r["candidatos"]] == [True, False]

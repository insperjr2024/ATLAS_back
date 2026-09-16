"""2026-09-15, a pedido — expõe pra diretoria/gerência o mesmo dado que o
push automático usa pra rodízio (`contagem_bancas_por_usuario`), sem
nenhuma tela pra conferir quem está sobrecarregado antes disto existir.
"""

from types import SimpleNamespace

from src.use_cases.banca.get_carga_bancas import GetCargaBancasUseCase


def usuario(id, nome, posicao="consultor"):
    return SimpleNamespace(id=id, nome=nome, posicao=posicao)


def _uc(*, ativos, contagem):
    uc = GetCargaBancasUseCase.__new__(GetCargaBancasUseCase)
    uc.candidatura_repository = SimpleNamespace(
        contagem_bancas_por_usuario=lambda: contagem
    )
    uc.usuario_repository = SimpleNamespace(get_ativos=lambda: ativos)
    return uc


def test_ordena_por_quantidade_decrescente():
    uc = _uc(
        ativos=[usuario(1, "Ana"), usuario(2, "Bia"), usuario(3, "Caio")],
        contagem={1: 2, 2: 5, 3: 0},
    )

    resultado = uc.execute()

    assert [r["usuario_id"] for r in resultado] == [2, 1, 3]


def test_quem_nunca_foi_alocado_entra_com_zero():
    uc = _uc(ativos=[usuario(1, "Ana")], contagem={})

    resultado = uc.execute()

    assert resultado == [{"usuario_id": 1, "nome": "Ana", "posicao": "consultor", "quantidade_bancas": 0}]


def test_diretoria_e_diretor_de_pessoas_ficam_de_fora():
    """Só quem realmente avalia banca entra na lista — diretor_projetos,
    diretor e diretor_pessoas não são escalados pelo push nem fazem
    sentido nessa conta de carga."""
    uc = _uc(
        ativos=[
            usuario(1, "Ana", "consultor"),
            usuario(2, "Bia", "coordenador"),
            usuario(3, "Caio", "gerente"),
            usuario(4, "Duda", "diretor_projetos"),
            usuario(5, "Eva", "diretor"),
            usuario(6, "Fabio", "diretor_pessoas"),
        ],
        contagem={},
    )

    resultado = uc.execute()

    assert {r["usuario_id"] for r in resultado} == {1, 2, 3}


def test_empate_desempata_por_nome():
    uc = _uc(
        ativos=[usuario(1, "Zeca"), usuario(2, "Ana")],
        contagem={1: 3, 2: 3},
    )

    resultado = uc.execute()

    assert [r["nome"] for r in resultado] == ["Ana", "Zeca"]

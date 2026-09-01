"""Os use cases de banca guardam a SESSÃO, e não só os repositórios.

⚠ Este teste existe porque o mesmo erro aconteceu duas vezes na mesma classe.
`ListBancasUseCase` e `GetBancaUseCase` vivem no mesmo arquivo e compartilham
helpers; quando um helper passa a precisar de algo novo, é fácil acrescentar no
`__init__` de um e esquecer do outro — e o sintoma é `GET /bancas` devolvendo
500 em produção, não um teste vermelho.

Da primeira vez foi `vendedor_repository` (2026-08-20). Da segunda, `self.db`,
que `calcular_piso_banca` passou a exigir para ler a matriz de composição
(2026-09-01).

O teste é grosseiro de propósito: não exercita comportamento, só afirma que os
atributos que os dois usam existem nos dois. É a forma barata de fechar uma
porta que já se abriu duas vezes.
"""

import inspect

import pytest

from src.use_cases.banca import get_banca as mod


class FakeSessao:
    """Basta existir: nenhum repositório é usado na construção."""


@pytest.mark.parametrize(
    "classe", [mod.ListBancasUseCase, mod.GetBancaUseCase]
)
def test_guarda_a_sessao(classe):
    uc = classe(FakeSessao())

    assert hasattr(uc, "db"), (
        f"{classe.__name__} não guarda `self.db` — `calcular_piso_banca` "
        "precisa da sessão para ler a matriz de composição"
    )


@pytest.mark.parametrize(
    "atributo",
    ["repository", "candidatura_repository", "configuracao_repository", "db"],
)
def test_as_duas_classes_tem_os_mesmos_atributos_de_base(atributo):
    """O que uma usa, a outra também usa: elas dividem os mesmos helpers."""
    lista = mod.ListBancasUseCase(FakeSessao())
    detalhe = mod.GetBancaUseCase(FakeSessao())

    assert hasattr(lista, atributo) and hasattr(detalhe, atributo)


def test_o_piso_exige_a_sessao():
    """`calcular_piso_banca` ganhou um terceiro parâmetro em 2026-09-01. Sem
    ele a matriz de composição seria ignorada — e como o parâmetro não tem
    default, esquecê-lo estoura na hora em vez de silenciosamente."""
    assinatura = inspect.signature(mod.calcular_piso_banca)

    assert list(assinatura.parameters) == ["banca", "frentes_vinculadas", "db"]
    assert all(
        p.default is inspect.Parameter.empty for p in assinatura.parameters.values()
    ), "um default aqui faria a chamada esquecida passar batido"

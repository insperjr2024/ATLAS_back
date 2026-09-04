"""⭐ O resultado da banca sai da decisão de diretoria de projetos OU gerente
da frente (§5.5, §8) — qualquer um decide sozinho, sem esperar os demais.
"""

from src.utils.apuracao_banca import apurar_aprovacao


def test_aprovado_fecha_aprovada():
    assert apurar_aprovacao(True) == "aprovada"


def test_reprovado_fecha_nao_aprovada():
    assert apurar_aprovacao(False) == "nao_aprovada"

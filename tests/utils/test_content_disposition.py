"""O cabeçalho de download precisa caber em latin-1 (2026-10-13)."""

import unicodedata

from src.utils.content_disposition import content_disposition

CAPTURA_DO_MAC = unicodedata.normalize("NFD", "Captura de Tela 2026-10-13 às 10.25.29.png")


def test_nome_com_acento_separado_nao_estoura_o_cabecalho():
    cabecalho = content_disposition(CAPTURA_DO_MAC)

    cabecalho.encode("latin-1")  # era aqui que o Starlette estourava
    assert cabecalho.startswith('attachment; filename="Captura de Tela 2026-10-13 as 10.25.29.png"')
    assert "filename*=UTF-8''Captura%20de%20Tela%202026-10-13%20%C3%A0s%2010.25.29.png" in cabecalho


def test_nome_simples_continua_igual_e_aspas_saem():
    assert content_disposition('PDI "final".xlsx') == (
        'attachment; filename="PDI final.xlsx"; filename*=UTF-8\'\'PDI%20%22final%22.xlsx'
    )


def test_inline_e_nome_vazio():
    assert content_disposition("", inline=True).startswith('inline; filename="arquivo"')

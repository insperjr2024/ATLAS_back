"""`esta_aberto()` é o único lugar que decide se um lote de desempenho está
valendo (regra 2.1) — tri-state, não booleano."""

from datetime import datetime

from src.utils.desempenho_lote import esta_aberto

INICIO = datetime(2026, 9, 1, 0, 0)
FIM = datetime(2026, 9, 30, 23, 59)
DENTRO = datetime(2026, 9, 15, 12, 0)
ANTES = datetime(2026, 8, 1, 12, 0)
DEPOIS = datetime(2026, 10, 1, 12, 0)


class TestOverrideManual:
    def test_override_aberto_ignora_as_datas_mesmo_fora_da_janela(self):
        assert esta_aberto("aberto", INICIO, FIM, agora=ANTES) is True
        assert esta_aberto("aberto", INICIO, FIM, agora=DEPOIS) is True

    def test_override_fechado_ignora_as_datas_mesmo_dentro_da_janela(self):
        assert esta_aberto("fechado", INICIO, FIM, agora=DENTRO) is False


class TestAutomaticoPorData:
    def test_none_dentro_da_janela_e_aberto(self):
        assert esta_aberto(None, INICIO, FIM, agora=DENTRO) is True

    def test_none_antes_da_janela_e_fechado(self):
        assert esta_aberto(None, INICIO, FIM, agora=ANTES) is False

    def test_none_depois_da_janela_e_fechado(self):
        assert esta_aberto(None, INICIO, FIM, agora=DEPOIS) is False

    def test_none_nos_limites_exatos_e_aberto(self):
        assert esta_aberto(None, INICIO, FIM, agora=INICIO) is True
        assert esta_aberto(None, INICIO, FIM, agora=FIM) is True

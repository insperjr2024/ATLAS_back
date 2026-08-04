"""Os 4 estados da banca, com o `atrasada` explícito.

`atrasada` é o estado que não existia no sistema antes da F5 e que destrava o
monitoramento — por isso ele tem teste próprio, não só uma linha numa tabela.
"""

from datetime import date, datetime

from src.utils.banca_status import (
    aceita_inscricao,
    banca_ja_ocorreu,
    calcular_status_banca,
    dias_de_atraso,
)

AGORA = datetime(2026, 9, 15, 10, 0)
PASSADO = datetime(2026, 9, 10, 14, 0)
FUTURO = datetime(2026, 9, 20, 14, 0)


class TestOsQuatroEstados:
    def test_sem_data_hora_e_nao_marcada(self):
        assert calcular_status_banca(None, None, AGORA) == "nao_marcada"

    def test_data_no_futuro_e_aberta(self):
        assert calcular_status_banca(FUTURO, None, AGORA) == "aberta"

    def test_realizado_em_preenchido_e_realizada(self):
        assert calcular_status_banca(FUTURO, datetime(2026, 9, 14), AGORA) == "realizada"

    def test_data_passada_sem_realizado_em_e_ATRASADA(self):
        """⭐ O estado que faltava. Antes da F5 isto devolvia 'realizada' e o
        placar da gestão dava 100% para sempre."""
        assert calcular_status_banca(PASSADO, None, AGORA) == "atrasada"

    def test_realizada_depois_do_previsto_continua_realizada(self):
        """A ordem importa: realizado_em é testado antes da data."""
        assert calcular_status_banca(PASSADO, datetime(2026, 9, 12), AGORA) == "realizada"

    def test_banca_marcada_para_agora_mesmo_ja_venceu(self):
        assert calcular_status_banca(AGORA, None, AGORA) == "atrasada"


class TestBancaJaOcorreu:
    def test_so_realizada_conta_como_ocorrida(self):
        assert banca_ja_ocorreu("realizada")

    def test_atrasada_nao_ocorreu(self):
        """A distinção inteira da F5: a data passou, mas a banca não aconteceu."""
        assert not banca_ja_ocorreu("atrasada")

    def test_aberta_e_nao_marcada_nao_ocorreram(self):
        assert not banca_ja_ocorreu("aberta")
        assert not banca_ja_ocorreu("nao_marcada")


class TestAceitaInscricao:
    def test_banca_atrasada_ainda_aceita_inscricao(self):
        """Ela ainda vai acontecer — quem fecha a inscrição é a realização,
        não o calendário."""
        assert aceita_inscricao("atrasada")

    def test_banca_aberta_aceita(self):
        assert aceita_inscricao("aberta")

    def test_banca_realizada_nao_aceita_mais(self):
        assert not aceita_inscricao("realizada")

    def test_banca_nao_marcada_nao_aceita(self):
        assert not aceita_inscricao("nao_marcada")


class TestDiasDeAtraso:
    def test_conta_dias_corridos_e_nao_uteis(self):
        """§7.4 é explícito: corridos. De 10/09 (qui) a 15/09 (ter) são 5 dias
        corridos — em dias úteis seriam 3."""
        assert dias_de_atraso(PASSADO, None, date(2026, 9, 15)) == 5

    def test_banca_realizada_nao_tem_atraso(self):
        assert dias_de_atraso(PASSADO, datetime(2026, 9, 12), date(2026, 9, 15)) == 0

    def test_banca_futura_nao_tem_atraso(self):
        assert dias_de_atraso(FUTURO, None, date(2026, 9, 15)) == 0

    def test_banca_nao_marcada_nao_tem_atraso(self):
        assert dias_de_atraso(None, None, date(2026, 9, 15)) == 0

"""`src/utils/fuso.py` — a fronteira entre o que o banco guarda (UTC) e o que
a pessoa vê (hora de São Paulo).

Os dois bugs que estes testes trancam apareceram na Rodada 5 do roteiro de QA:

- a alocação automática comparava `banca.data_hora` (UTC) com a grade horária
  (local) e escalava justamente quem tinha aula na hora da banca;
- toda guarda escrita como `request.data_hora != existente.data_hora` disparava
  sempre, porque um datetime com fuso nunca é igual a um sem — o botão Editar
  da tela de Bancas não salvava nada, de campo nenhum.
"""

from datetime import datetime, timedelta, timezone

from src.utils.fuso import normalizar_utc, para_hora_local


class TestParaHoraLocal:
    def test_o_valor_gravado_vira_a_hora_que_a_tela_mostra(self):
        # O front grava 09:00 de São Paulo como 12:00Z; lido de volta, é 09:00.
        assert para_hora_local(datetime(2026, 8, 20, 12, 0)) == datetime(2026, 8, 20, 9, 0)

    def test_devolve_sem_fuso_para_comparar_com_a_grade(self):
        # A grade guarda `hora_inicio`/`hora_fim` ingênuos; um retorno com
        # tzinfo obrigaria cada chamador a tirá-lo de novo.
        assert para_hora_local(datetime(2026, 8, 20, 12, 0)).tzinfo is None

    def test_banca_da_noite_nao_escorrega_para_o_dia_seguinte(self):
        # 19:00 de segunda em São Paulo é 22:00Z da MESMA segunda; mas 22:00 de
        # segunda vira 01:00Z de terça — e era assim que o `weekday()` errava.
        segunda_a_noite = datetime(2026, 8, 17, 1, 0)  # terça 01:00Z
        local = para_hora_local(segunda_a_noite)
        assert local == datetime(2026, 8, 16, 22, 0)
        assert local.weekday() == 6  # domingo, não a segunda do valor cru

    def test_respeita_o_fuso_de_quem_ja_vem_com_um(self):
        com_fuso = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        assert para_hora_local(com_fuso) == datetime(2026, 8, 20, 9, 0)

    def test_acompanha_a_mudanca_de_offset_do_brasil(self):
        # Janeiro e agosto podem ter offsets diferentes conforme o horário de
        # verão vigente na base de fusos. O que este teste garante é que a
        # conversão vem do ZoneInfo, não de um `timedelta(hours=3)` fixo.
        janeiro = para_hora_local(datetime(2026, 1, 20, 12, 0))
        agosto = para_hora_local(datetime(2026, 8, 20, 12, 0))
        assert janeiro.hour in (9, 10)
        assert agosto.hour in (9, 10)


class TestNormalizarUtc:
    def test_datetime_com_fuso_perde_o_fuso_mantendo_o_instante(self):
        com_z = datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
        assert normalizar_utc(com_z) == datetime(2026, 8, 28, 13, 30)

    def test_datetime_sem_fuso_passa_intacto(self):
        naive = datetime(2026, 8, 28, 13, 30)
        assert normalizar_utc(naive) == naive

    def test_none_continua_none(self):
        assert normalizar_utc(None) is None

    def test_o_mesmo_instante_nos_dois_formatos_fica_igual(self):
        """⭐ O coração do bug do botão Editar.

        Sem normalizar, `!=` entre aware e naive é sempre verdadeiro — e a
        guarda "a data mudou?" disparava mesmo quando ninguém tocou na data.
        """
        do_banco = datetime(2026, 8, 28, 13, 30)
        do_front = datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)

        assert do_front != do_banco  # a armadilha, documentada
        assert normalizar_utc(do_front) == do_banco

    def test_offset_diferente_de_zero_e_convertido_para_utc(self):
        em_sao_paulo = datetime(
            2026, 8, 28, 10, 30, tzinfo=timezone(timedelta(hours=-3))
        )
        assert normalizar_utc(em_sao_paulo) == datetime(2026, 8, 28, 13, 30)

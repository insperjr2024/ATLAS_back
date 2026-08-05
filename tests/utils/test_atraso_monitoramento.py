"""O atraso do §7.4 — em dias ÚTEIS desde 2026-08-04.

Antes a régua aqui era dias corridos. A diretoria confirmou que são dias úteis,
pelo calendário do Insper: fim de semana, feriado e semana de provas não são
tempo que o time deixou passar. Vários testes comparam com a contagem corrida
de propósito, para o tamanho da diferença ficar explícito.
"""

from datetime import date, datetime
from types import SimpleNamespace

from src.utils.atraso_monitoramento import calcular_atraso_projeto

# Setembro de 2026: 11 é sexta, 12 sábado, 13 domingo, 14 segunda, 15 terça,
# 18 sexta.
SEX_11 = date(2026, 9, 11)
SEG_14 = date(2026, 9, 14)
TER_15 = date(2026, 9, 15)
SEX_18 = date(2026, 9, 18)

NOMES = {1: "Diagnóstico"}


def escopo(
    escopo_id=1,
    status="em_andamento",
    entrega_planejada=None,
    entrega_real=None,
    tipo_atraso="interno",
):
    return SimpleNamespace(
        id=escopo_id,
        status=status,
        data_entrega_planejada=entrega_planejada,
        data_entrega_real=entrega_real,
        tipo_atraso_entrega=tipo_atraso,
    )


def banca(dia: date, hora=10, realizado_em=None):
    return SimpleNamespace(
        data_hora=datetime.combine(dia, datetime.min.time()).replace(hour=hora),
        realizado_em=realizado_em,
    )


def calcular(escopos, bancas=None, referencia=SEG_14, nao_letivos=None):
    return calcular_atraso_projeto(
        1, escopos, bancas or {}, NOMES, referencia, nao_letivos or []
    )


class TestBancaAtrasada:
    def test_fim_de_semana_nao_conta(self):
        """O ponto da mudança: venceu na sexta, hoje é segunda.

        São 3 dias corridos, mas o time só teve 1 dia de trabalho.
        """
        r = calcular([escopo()], {1: banca(SEX_11)})
        assert r.atrasado
        assert r.dias_totais == 1
        assert (SEG_14 - SEX_11).days == 3

    def test_dia_nao_letivo_no_meio_nao_conta(self):
        r = calcular([escopo()], {1: banca(SEG_14)}, referencia=SEX_18, nao_letivos=[TER_15])
        assert r.dias_totais == 3

    def test_banca_realizada_nao_gera_motivo(self):
        realizada = banca(SEX_11, realizado_em=datetime(2026, 9, 11, 11))
        assert not calcular([escopo()], {1: realizada}).atrasado

    def test_banca_no_futuro_nao_gera_motivo(self):
        assert not calcular([escopo()], {1: banca(SEX_18)}).atrasado

    def test_o_motivo_e_do_tipo_banca(self):
        motivo = calcular([escopo()], {1: banca(SEX_11)}).motivos[0]
        assert motivo.tipo == "banca"
        assert motivo.escopo_nome == "Diagnóstico"
        assert motivo.data_referencia == SEX_11
        assert "dias úteis" in motivo.descricao

    def test_referencia_manda_no_status_e_nao_o_relogio_real(self):
        """Com `referencia` antes da banca, ela ainda não venceu.

        A função checava o status sem repassar a `referencia`, então caía no
        relógio real e discordava da data pedida.
        """
        assert not calcular([escopo()], {1: banca(SEX_18)}, referencia=SEX_11).atrasado


class TestEntregaAtrasada:
    def test_conta_em_dias_uteis(self):
        r = calcular([escopo(entrega_planejada=SEX_11)])
        assert r.dias_totais == 1

    def test_entrega_feita_nao_atrasa(self):
        e = escopo(entrega_planejada=SEX_11, entrega_real=SEG_14)
        assert not calcular([e]).atrasado

    def test_externo_vira_tipo_proprio(self):
        e = escopo(entrega_planejada=SEX_11, tipo_atraso="externo")
        assert calcular([e]).motivos[0].tipo == "entrega_externa"

    def test_interno_vira_tipo_proprio(self):
        e = escopo(entrega_planejada=SEX_11, tipo_atraso="interno")
        assert calcular([e]).motivos[0].tipo == "entrega_interna"


class TestAgregacao:
    def test_escopo_cancelado_e_ignorado(self):
        e = escopo(status="cancelado", entrega_planejada=SEX_11)
        assert not calcular([e], {1: banca(SEX_11)}).atrasado

    def test_banca_e_entrega_do_mesmo_escopo_somam(self):
        """Um escopo pode entrar duas vezes — pela banca e pela entrega."""
        r = calcular([escopo(entrega_planejada=SEX_11)], {1: banca(SEX_11)})
        assert len(r.motivos) == 2
        assert r.dias_totais == 2

    def test_projeto_sem_marco_nao_esta_atrasado(self):
        r = calcular([escopo()])
        assert not r.atrasado
        assert r.dias_totais == 0

    def test_atrasado_por_banca_ignora_entrega(self):
        """O placar da gestão só olha a banca — a entrega depende do cliente."""
        r = calcular([escopo(entrega_planejada=SEX_11)])
        assert r.atrasado
        assert not r.atrasado_por_banca

    def test_zero_dias_uteis_ainda_e_atraso(self):
        """Venceu na sexta, hoje é sábado: atrasado, mas sem dia útil decorrido.

        Quem decide SE está atrasado é a data; a contagem só mede o tamanho.
        """
        r = calcular([escopo()], {1: banca(SEX_11)}, referencia=date(2026, 9, 12))
        assert r.atrasado
        assert r.dias_totais == 0

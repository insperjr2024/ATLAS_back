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
    data_inicio=date(2026, 8, 3),
):
    """⚠ `data_inicio` entrou com valor padrão em 2026-08-13.

    Sem reunião inicial a janela não abriu e a data da banca é rascunho (§20.4)
    — cobrar dela é cobrar de um escopo que não começou. O dublê antigo não
    tinha o campo, então modelava um escopo que na prática não existe: com
    banca marcada e sem ter começado.
    """
    return SimpleNamespace(
        id=escopo_id,
        status=status,
        data_inicio=data_inicio,
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


class TestEntregaNaoGeraMaisAtraso:
    """⚠ A entrega ao cliente SAIU dos insights (2026-08-12).

    Esta classe testava o "Pilar 2": entrega planejada vencida virava motivo,
    com a distinção interno/externo. A diretoria tirou a métrica — ela media a
    agenda do cliente e não o trabalho do time, e deixava vermelho um projeto
    cuja banca tinha acontecido no prazo.

    Os testes ficam invertidos, e não apagados, porque a regra em vigor é
    justamente esta: entrega vencida **não** é atraso. Sem eles, alguém
    reintroduz o pilar sem perceber que foi uma decisão.
    """

    def test_entrega_vencida_nao_gera_motivo(self):
        assert not calcular([escopo(entrega_planejada=SEX_11)]).atrasado

    def test_entrega_feita_tambem_nao(self):
        e = escopo(entrega_planejada=SEX_11, entrega_real=SEG_14)
        assert not calcular([e]).atrasado

    def test_a_classificacao_interno_externo_deixou_de_pesar(self):
        """`tipo_atraso_entrega` continua no banco e na rota que o grava — o
        que sumiu foi o motivo derivado dele."""
        for tipo in ("interno", "externo"):
            e = escopo(entrega_planejada=SEX_11, tipo_atraso=tipo)
            assert calcular([e]).motivos == []


class TestAgregacao:
    def test_escopo_cancelado_e_ignorado(self):
        e = escopo(status="cancelado", entrega_planejada=SEX_11)
        assert not calcular([e], {1: banca(SEX_11)}).atrasado

    def test_so_a_banca_gera_motivo(self):
        """Era "banca e entrega do mesmo escopo somam", com 2 motivos. Com o
        pilar da entrega removido, o mesmo escopo entra UMA vez só."""
        r = calcular([escopo(entrega_planejada=SEX_11)], {1: banca(SEX_11)})
        assert [m.tipo for m in r.motivos] == ["banca"]
        assert r.dias_totais == 1

    def test_projeto_sem_marco_nao_esta_atrasado(self):
        r = calcular([escopo()])
        assert not r.atrasado
        assert r.dias_totais == 0

    def test_entrega_vencida_sozinha_nao_atrasa_o_projeto(self):
        """Era: `atrasado` sim, `atrasado_por_banca` não — o projeto ficava
        vermelho por causa da agenda do cliente. Hoje os dois são falsos, e o
        placar da gestão e a lista de atrasos passaram a concordar."""
        r = calcular([escopo(entrega_planejada=SEX_11)])
        assert not r.atrasado
        assert not r.atrasado_por_banca

    def test_zero_dias_uteis_ainda_e_atraso(self):
        """Venceu na sexta, hoje é sábado: atrasado, mas sem dia útil decorrido.

        Quem decide SE está atrasado é a data; a contagem só mede o tamanho.
        """
        r = calcular([escopo()], {1: banca(SEX_11)}, referencia=date(2026, 9, 12))
        assert r.atrasado
        assert r.dias_totais == 0


class TestOsQuatroRecortes:
    """⭐ Quem NÃO deve ser cobrado — o "aparecem projetos que não deveriam".

    Cada um destes gerava motivo de banca que crescia um dia útil por dia, sem
    limite, e enchia a fila da diretoria com o que ela não tinha como cobrar.
    """

    def test_escopo_sem_reuniao_inicial_nao_atrasa(self):
        """§20.4: sem reunião inicial a janela nem abriu."""
        r = calcular_atraso_projeto(
            1, [escopo(data_inicio=None)], {1: banca(SEX_11)}, NOMES, referencia=SEX_18
        )

        assert not r.atrasado

    def test_escopo_entregue_nao_atrasa(self):
        """O escopo acabou: o que falta é registro, não trabalho."""
        r = calcular_atraso_projeto(
            1,
            [escopo(status="entregue", entrega_real=SEG_14)],
            {1: banca(SEX_11)},
            NOMES,
            referencia=SEX_18,
        )

        assert not r.atrasado

    def test_escopo_com_entrega_marcada_nao_atrasa(self):
        """A data da entrega basta, mesmo que o status ainda não tenha virado —
        são dois passos separados desde a confirmação da entrega."""
        r = calcular_atraso_projeto(
            1, [escopo(entrega_real=SEG_14)], {1: banca(SEX_11)}, NOMES, referencia=SEX_18
        )

        assert not r.atrasado

    def test_banca_de_HOJE_ainda_nao_atrasou(self):
        """⭐ O dia da banca é dela.

        ⚠ A referência era 23:59 de hoje, então uma banca marcada para hoje às
        16h já contava como atrasada às 8h da manhã — com "0 dias" — e derrubava
        o placar da gestão. Pior: a MESMA banca aparecia em "bancas próximas" da
        Visão geral. Era agenda da semana e motivo de atraso ao mesmo tempo.
        """
        r = calcular_atraso_projeto(
            1, [escopo()], {1: banca(SEX_18, hora=16)}, NOMES, referencia=SEX_18
        )

        assert not r.atrasado

    def test_banca_de_ontem_atrasou(self):
        """O contraponto do teste acima: o corte é no dia seguinte, não em dois."""
        r = calcular_atraso_projeto(
            1, [escopo()], {1: banca(TER_15)}, NOMES, referencia=SEX_18
        )

        assert r.atrasado
        assert r.dias_totais == 3


class TestPausaNaoEhAtraso:
    """⏸ A parada foi decisão de quem cobra o atraso.

    ⚠ A régua da JANELA já descontava a pausa; a da BANCA não conhecia o
    conceito. As duas metades da mesma tela discordavam sobre o mesmo projeto
    parado — e a que mais aparecia era a errada.
    """

    def test_dias_de_pausa_saem_da_conta(self):
        # Banca venceu na sexta 11; hoje é sexta 18. Sem pausa são 5 dias úteis.
        sem_pausa = calcular_atraso_projeto(
            1, [escopo()], {1: banca(SEX_11)}, NOMES, referencia=SEX_18
        )
        assert sem_pausa.dias_totais == 5

        # Pausado de segunda 14 a quarta 16 (semiaberto): 2 dias úteis parados.
        com_pausa = calcular_atraso_projeto(
            1,
            [escopo()],
            {1: banca(SEX_11)},
            NOMES,
            referencia=SEX_18,
            janelas_pausa=[(SEG_14, date(2026, 9, 16))],
        )
        assert com_pausa.dias_totais == 3

"""⭐ A janela do escopo — vendidos · ajustados · atraso.

Três regras dominam estes testes, e as três existem para impedir que os
números se misturem:

- **Vendidos nunca muda.** Ganhar 10 dias de ajuste NÃO transforma um escopo
  de 20 em um de 30 — ele continua sendo "20 vendidos + 10 ajustados". A
  diferença entre vender 30 e estourar 20 é a informação inteira.
- **Atraso é derivado, nunca autorizado.** É o que passou de vendidos +
  ajustados, e não existe caminho no código que o conceda.
- **Correção não é atraso, nem dia de ajuste.** O que é pintado depois da banca
  tem métrica própria e não contamina nenhuma das outras.

O calendário é o real do seed (2026.2): feriado de 07/09 e semana de provas de
28/09 a 02/10 — o mesmo de `test_contagem_dias.py`, e vários testes trazem a
asserção-irmã com o calendário vazio para provar que é o feriado que faz a
diferença, não o acaso.

Os números vêm do **exemplo vivo do §5**: "Elaboração Contratual" do Projeto
Alfa, vendido por 20 dias, reunião inicial em 03/09 (quinta), +10 aprovados.
"""

from datetime import date, datetime, timedelta

from src.utils.janela_escopo import (
    calcular_janela,
    dentro_da_janela,
    prazo_pelo_kickoff,
    primeiro_escopo_id,
    dias_de_atraso,
    dias_de_correcao,
    marco_das_correcoes,
    dias_parados,
    dias_uteis_ate_a_banca,
)

FERIADOS = [date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 15)]
PROVAS = [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)]
CALENDARIO = FERIADOS + PROVAS

QUI_03_09 = date(2026, 9, 3)  # a reunião inicial do exemplo
TER_08_09 = date(2026, 9, 8)  # o 3º dia útil a partir dela (07/09 é feriado)
QUA_09_09 = date(2026, 9, 9)
QUI_08_10 = date(2026, 10, 8)  # o 20º dia útil — fim da janela vendida
SEX_23_10 = date(2026, 10, 23)  # o 30º dia útil — fim da janela ajustada


class _Etapa:
    """Dublê de `CronogramaEtapaModel` — só o intervalo importa aqui."""

    def __init__(self, data_inicio, data_fim):
        self.data_inicio = data_inicio
        self.data_fim = data_fim


def janela(vendidos=20, ajustados=0, inicio=QUI_03_09, calendario=CALENDARIO, hoje=QUI_03_09):
    return calcular_janela(inicio, vendidos, ajustados, calendario, referencia=hoje)


class TestJanela:
    def test_fim_da_janela_pula_o_feriado(self):
        """20 dias úteis a partir de 03/09 caem em 08/10 — e não em 30/09,
        porque o feriado de 07/09 e a semana de provas empurram a conta."""
        assert janela().fim == QUI_08_10
        # A asserção-irmã: sem calendário, os mesmos 20 dias fecham antes.
        assert janela(calendario=[]).fim == date(2026, 9, 30)

    def test_ajuste_estica_a_janela_sem_mexer_no_vendido(self):
        """⭐ O exemplo do §5: +10 e a banca passa a caber até o 30º dia. O
        sistema continua dizendo *vendidos 20 · ajustados 10*."""
        j = janela(ajustados=10)

        assert j.fim == SEX_23_10
        assert j.dias_vendidos == 20
        assert j.dias_ajustados == 10
        assert j.dias_totais == 30

    def test_escopo_sem_reuniao_inicial_nao_tem_janela(self):
        """§20.4: sem reunião inicial não há janela, não consome dias e não
        pode ter banca."""
        j = calcular_janela(None, 20, 0, CALENDARIO, referencia=QUI_03_09)

        assert j.aberta is False
        assert j.fim is None
        assert dentro_da_janela(QUI_08_10, j) is False

    def test_calendario_carregado_errado_nao_derruba_a_tela(self):
        """O ano inteiro como não letivo faz `somar_dias_uteis` levantar. Aqui
        isso vira janela sem fim — a faixa some, o resto da tela segue."""
        ano_inteiro = [date(2026, 1, 1) + _dias(n) for n in range(365 * 6)]

        assert janela(calendario=ano_inteiro).fim is None


class TestPrazoDoPedido:
    def test_prazo_e_o_3o_dia_util_contando_a_reuniao_como_dia_1(self):
        """§20.2. 03/09 é o dia 1, 04/09 o dia 2, 07/09 é feriado, então o
        dia 3 é 08/09."""
        assert janela().prazo_pedido_ajuste == TER_08_09

    def test_no_dia_do_prazo_ainda_da_para_pedir(self):
        assert janela(hoje=TER_08_09).pedido_ajuste_aberto is True

    def test_depois_do_prazo_acabou(self):
        """§8: depois do prazo não existe mais pedido para aquele escopo —
        todo dia além da janela é atraso, sem autorização envolvida."""
        assert janela(hoje=QUA_09_09).pedido_ajuste_aberto is False

    def test_escopo_nao_iniciado_nao_tem_prazo_correndo(self):
        j = calcular_janela(None, 20, 0, CALENDARIO, referencia=QUI_03_09)
        assert j.pedido_ajuste_aberto is False


class TestPrazoPeloKickoff:
    """⭐ A régua do PRIMEIRO escopo: o prazo é o último dia da ambientação.

    Quem decide que ela se aplica é quem chama (`primeiro_escopo_id`); aqui se
    mede o efeito dela na janela — inclusive o caso que a régua antiga não
    sabia representar, o de um prazo que existe ANTES de a janela abrir.
    """

    def test_substitui_os_3_dias_uteis_da_reuniao_inicial(self):
        """Mesmo escopo do exemplo, mas ele é o primeiro do projeto: o prazo
        deixa de ser 08/09 e passa a ser o fim da ambientação, 02/09."""
        j = calcular_janela(
            QUI_03_09, 20, 0, CALENDARIO,
            referencia=QUI_03_09,
            prazo_do_kickoff=date(2026, 9, 2),
        )

        assert j.prazo_pedido_ajuste == date(2026, 9, 2)
        assert j.pedido_ajuste_aberto is False
        # A JANELA não muda — o prazo do pedido é outra conta.
        assert j.fim == QUI_08_10

    def test_ha_prazo_mesmo_sem_reuniao_inicial(self):
        """⭐ O caso normal do primeiro escopo: o pedido nasce na ambientação,
        antes de a largada abrir a janela dele."""
        j = calcular_janela(
            None, 20, 0, CALENDARIO,
            referencia=date(2026, 9, 1),
            prazo_do_kickoff=date(2026, 9, 2),
        )

        assert j.aberta is False
        assert j.prazo_pedido_ajuste == date(2026, 9, 2)
        assert j.pedido_ajuste_aberto is True

    def test_o_ultimo_dia_da_ambientacao_ainda_vale(self):
        j = calcular_janela(
            None, 20, 0, CALENDARIO,
            referencia=date(2026, 9, 2),
            prazo_do_kickoff=date(2026, 9, 2),
        )

        assert j.pedido_ajuste_aberto is True

    def test_projeto_vendido_nao_tem_prazo_pelo_kickoff(self):
        """O STATUS decide a entrada: antes da ambientação não há equipe em
        campo, e o kickoff ainda pode mudar de lugar."""
        assert prazo_pelo_kickoff("vendido", date(2026, 8, 28), 5, CALENDARIO) is None

    def test_ambientacao_de_5_dias_conta_o_kickoff_como_o_1o(self):
        assert prazo_pelo_kickoff("ambientacao", date(2026, 8, 28), 5, CALENDARIO) == QUI_03_09

    def test_projeto_sem_ambientacao_cai_nos_3_dias_uteis(self):
        """Sem kickoff, ou com zero dias, não há "último dia" nenhum — e quem
        chama recebe `None`, que é o sinal de usar a régua da reunião inicial."""
        assert prazo_pelo_kickoff("em_andamento", None, 5, CALENDARIO) is None
        assert prazo_pelo_kickoff("em_andamento", date(2026, 8, 28), 0, CALENDARIO) is None


class TestPrimeiroEscopo:
    """Qual escopo é o primeiro da lista *Escopos vendidos* — a mesma ordem
    que as setinhas do cadastro definem."""

    def _escopo(self, id, ordem):
        return type("E", (), {"id": id, "ordem": ordem})()

    def test_ordem_manda_sobre_o_id(self):
        escopos = [self._escopo(7, 1), self._escopo(9, 0)]
        assert primeiro_escopo_id(escopos) == 9

    def test_id_desempata_quem_nunca_foi_reordenado(self):
        """Todo mundo nasce com `ordem` 0: aí vale a ordem de criação."""
        escopos = [self._escopo(9, 0), self._escopo(7, 0)]
        assert primeiro_escopo_id(escopos) == 7

    def test_projeto_sem_escopo_nao_tem_primeiro(self):
        assert primeiro_escopo_id([]) is None


class TestDentroDaJanela:
    def test_o_ultimo_dia_da_janela_cabe(self):
        """A banca pode ser marcada ATÉ o último dia — fronteira fechada."""
        assert dentro_da_janela(QUI_08_10, janela()) is True

    def test_o_dia_seguinte_ao_fim_nao_cabe(self):
        assert dentro_da_janela(date(2026, 10, 9), janela()) is False

    def test_antes_da_reuniao_inicial_nao_cabe(self):
        assert dentro_da_janela(date(2026, 9, 2), janela()) is False

    def test_aceita_datetime_porque_banca_tem_hora(self):
        assert dentro_da_janela(datetime(2026, 10, 8, 14, 30), janela()) is True


class TestAtraso:
    def test_banca_realizada_dentro_da_janela_da_atraso_zero(self):
        """§10, o caso que o time quer: entrou no prazo, atraso nenhum."""
        assert dias_de_atraso(janela(), datetime(2026, 10, 7, 10, 0), CALENDARIO) == 0

    def test_atraso_conta_do_fim_da_janela_ate_a_banca_acontecer(self):
        """A banca aconteceu em 13/10. Do dia seguinte ao fim da janela até lá
        são 2 dias úteis — 09/10 (sexta) e 13/10 (terça); 10 e 11 são fim de
        semana e 12/10 é feriado."""
        assert dias_de_atraso(janela(), datetime(2026, 10, 13, 10, 0), CALENDARIO) == 2

    def test_enquanto_a_banca_nao_acontece_o_atraso_corre_ate_hoje(self):
        """É o número que cresce sozinho na tela e cobra ação."""
        corrente = dias_de_atraso(janela(), None, CALENDARIO, referencia=date(2026, 10, 13))
        assert corrente == 2

    def test_ajuste_aprovado_apaga_o_atraso_que_existia(self):
        """⭐ É para isso que o ajuste serve: a mesma banca que estava atrasada
        contra 20 dias passa a caber nos 30."""
        banca = datetime(2026, 10, 13, 10, 0)

        assert dias_de_atraso(janela(), banca, CALENDARIO) > 0
        assert dias_de_atraso(janela(ajustados=10), banca, CALENDARIO) == 0

    def test_escopo_sem_janela_nao_atrasa(self):
        sem_janela = calcular_janela(None, 20, 0, CALENDARIO, referencia=QUI_03_09)
        assert dias_de_atraso(sem_janela, None, CALENDARIO, referencia=date(2027, 1, 1)) == 0


class TestPausaDesloca:
    """⏸ Projeto pausado não gasta janela — nem o prazo do pedido, nem o atraso.

    `contagem_dias` sempre descontou a pausa dos dias CONSUMIDOS. Enquanto a
    janela não enxergava a mesma pausa, as duas contas divergiam: o contador
    congelava, mas o fim da janela ficava onde estava — a banca continuava
    barrada pela data antiga e o escopo ganhava atraso por uma parada que a
    própria diretoria decretou.

    Pausa de 09/09 (quarta) a 16/09 (quarta), semiaberta: são 5 dias úteis
    parados (09, 10, 11, 14, 15).
    """

    PAUSA = [(date(2026, 9, 9), date(2026, 9, 16))]

    def test_a_pausa_empurra_o_fim_da_janela(self):
        parada = calcular_janela(
            QUI_03_09, 20, 0, CALENDARIO, referencia=QUI_03_09, janelas_pausa=self.PAUSA
        )
        # Sem pausa o 20º dia útil é 08/10. Com 5 dias parados, o fim anda 5
        # dias ÚTEIS para a frente: 09/10 e 13 a 16/10 (10 e 11 são fim de
        # semana, 12/10 é feriado).
        assert janela().fim == QUI_08_10
        assert parada.fim == date(2026, 10, 16)

    def test_a_pausa_empurra_tambem_o_prazo_do_pedido(self):
        """Os 3 dias úteis para perceber que os dias vendidos não fecham não
        podem correr com o projeto parado — ninguém está trabalhando para
        perceber.

        Pausa de 04/09 a 09/09 (semiaberta): tira 04/09 e 08/09 da conta, e o
        3º dia útil vai de 08/09 para 10/09.
        """
        parada = calcular_janela(
            QUI_03_09,
            20,
            0,
            CALENDARIO,
            referencia=QUI_03_09,
            janelas_pausa=[(date(2026, 9, 4), date(2026, 9, 9))],
        )
        assert janela().prazo_pedido_ajuste == TER_08_09
        assert parada.prazo_pedido_ajuste == date(2026, 9, 10)

    def test_pausa_que_comeca_depois_do_prazo_nao_o_move(self):
        """A pausa do dia 09 é posterior aos 3 primeiros dias úteis — o prazo
        já tinha vencido no dia 08 e continua lá."""
        parada = calcular_janela(
            QUI_03_09, 20, 0, CALENDARIO, referencia=QUI_03_09, janelas_pausa=self.PAUSA
        )
        assert parada.prazo_pedido_ajuste == TER_08_09

    def test_sem_pausa_nada_muda(self):
        """A garantia de que o caminho novo não mexeu no de todo mundo."""
        assert calcular_janela(
            QUI_03_09, 20, 0, CALENDARIO, referencia=QUI_03_09, janelas_pausa=[]
        ) == janela()

    def test_dia_de_pausa_depois_do_fim_nao_conta_como_atraso(self):
        """Parou depois de a janela estourar: o relógio do atraso também para."""
        pausa_no_atraso = [(date(2026, 10, 9), date(2026, 10, 14))]
        sem_pausa = dias_de_atraso(janela(), None, CALENDARIO, referencia=date(2026, 10, 15))
        com_pausa = dias_de_atraso(
            janela(), None, CALENDARIO, referencia=date(2026, 10, 15),
            janelas_pausa=pausa_no_atraso,
        )
        # 09/10 e 13/10 caem na pausa (10 e 11 são fim de semana, 12 é feriado).
        assert sem_pausa == 4
        assert com_pausa == 2


class TestCorrecoes:
    """⭐ O marco é a BANCA REALIZADA, não a entrega — é entre uma e outra que
    as correções apontadas pela avaliação acontecem."""

    ENTREGA = QUI_08_10

    def test_o_marco_e_a_banca_realizada(self):
        banca = datetime(2026, 10, 1, 14, 0)
        assert marco_das_correcoes(banca, QUI_08_10) == date(2026, 10, 1)

    def test_sem_banca_realizada_a_entrega_serve_de_marco(self):
        """Escopo antigo, entregue antes de existir registro de realização."""
        assert marco_das_correcoes(None, QUI_08_10) == QUI_08_10

    def test_sem_banca_nem_entrega_o_escopo_nao_esta_em_correcoes(self):
        assert marco_das_correcoes(None, None) is None

    def test_etapa_toda_anterior_ao_marco_nao_e_correcao(self):
        etapas = [_Etapa(date(2026, 10, 5), date(2026, 10, 7))]
        assert dias_de_correcao(etapas, self.ENTREGA, CALENDARIO) == 0

    def test_etapa_posterior_ao_marco_conta_em_dias_uteis(self):
        """09/10 (sexta) e 13/10 (terça) — 10/10 e 11/10 são fim de semana e
        12/10 é feriado."""
        etapas = [_Etapa(date(2026, 10, 9), date(2026, 10, 13))]
        assert dias_de_correcao(etapas, self.ENTREGA, CALENDARIO) == 2

    def test_etapa_que_atravessa_o_marco_conta_so_a_metade_de_depois(self):
        etapas = [_Etapa(date(2026, 10, 6), date(2026, 10, 9))]
        assert dias_de_correcao(etapas, self.ENTREGA, CALENDARIO) == 1

    def test_duas_etapas_no_mesmo_dia_sao_um_dia_de_correcao(self):
        """⚠ Conta dias distintos, não a soma das etapas."""
        etapas = [
            _Etapa(date(2026, 10, 9), date(2026, 10, 9)),
            _Etapa(date(2026, 10, 9), date(2026, 10, 9)),
        ]
        assert dias_de_correcao(etapas, self.ENTREGA, CALENDARIO) == 1

    def test_sem_marco_nao_ha_correcao(self):
        """Enquanto o escopo não foi entregue, tudo que é pintado é trabalho
        normal — mesmo pintado além da janela."""
        etapas = [_Etapa(date(2026, 11, 3), date(2026, 11, 6))]
        assert dias_de_correcao(etapas, None, CALENDARIO) == 0


class TestDiasParados:
    KICKOFF = date(2026, 9, 1)  # terça

    def test_dia_util_sem_nenhuma_marcacao_conta_como_parado(self):
        """01 a 04/09 são 4 dias úteis; só 03/09 tem marcação."""
        parados = dias_parados(
            self.KICKOFF, [QUI_03_09], CALENDARIO, referencia=date(2026, 9, 4)
        )
        assert parados == 3

    def test_fim_de_semana_e_feriado_nao_sao_dias_parados(self):
        """Ninguém deveria estar trabalhando neles. De 01 a 08/09 são 5 dias
        úteis (05 e 06 são fim de semana, 07 é feriado); 4 sem marcação."""
        parados = dias_parados(
            self.KICKOFF, [QUI_03_09], CALENDARIO, referencia=TER_08_09
        )
        assert parados == 4

    def test_projeto_sem_kickoff_nao_tem_dia_parado(self):
        """Não largou — cobrar parada seria cobrar o que não começou."""
        assert dias_parados(None, [], CALENDARIO, referencia=date(2026, 12, 1)) == 0

    def test_aceita_datetime_porque_banca_marca_com_hora(self):
        parados = dias_parados(
            self.KICKOFF,
            [datetime(2026, 9, 3, 14, 0)],
            CALENDARIO,
            referencia=date(2026, 9, 4),
        )
        assert parados == 3


class TestFolgaDaBanca:
    """§20.3: os 5 dias úteis que decidem se remarcar precisa de diretoria."""

    def test_banca_de_amanha_esta_a_um_dia_util(self):
        assert dias_uteis_ate_a_banca(
            datetime(2026, 9, 4, 10, 0), CALENDARIO, referencia=QUI_03_09
        ) == 1

    def test_o_feriado_no_meio_aumenta_a_folga_em_dias_corridos(self):
        """De 03/09 até 10/09 são 4 dias úteis, não 7 corridos."""
        assert dias_uteis_ate_a_banca(
            datetime(2026, 9, 10, 10, 0), CALENDARIO, referencia=QUI_03_09
        ) == 4

    def test_banca_no_passado_da_zero(self):
        assert dias_uteis_ate_a_banca(
            datetime(2026, 9, 1, 10, 0), CALENDARIO, referencia=QUI_03_09
        ) == 0

    def test_banca_sem_data_nao_tem_folga_para_medir(self):
        assert dias_uteis_ate_a_banca(None, CALENDARIO, referencia=QUI_03_09) is None


def _dias(n):
    return timedelta(days=n)

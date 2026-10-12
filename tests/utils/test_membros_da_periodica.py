"""Avaliação periódica só com quem está em escopo em andamento (2026-10-12).

Escopo que não começou (zero dias, sem reunião inicial) ou que já foi
entregue não gera avaliação: a frente dele sai da conta do projeto. Quem é de
duas frentes continua pela que está ativa.
"""

from datetime import date, datetime
from types import SimpleNamespace

from src.utils.desempenho_escopo import em_andamento_em, membros_da_periodica
from src.utils.desempenho_fila import calcular_pares_lote

BUSINESS, DIREITO, TECH = 1, 2, 3
CONEXOES = 10

PERIODICA = SimpleNamespace(tipo="periodico", data_inicio=datetime(2026, 10, 12, 9, 0), criado_em=datetime(2026, 10, 11))
FINALIZACAO = SimpleNamespace(tipo="finalizacao", data_inicio=datetime(2026, 10, 12), criado_em=datetime(2026, 10, 12))


def escopo(frente, status="em_andamento", inicio=date(2026, 9, 1), entrega=None, projeto=CONEXOES, confirmada=None):
    return SimpleNamespace(projeto_id=projeto, frente_id=frente, status=status, data_inicio=inicio, data_entrega_real=entrega, entrega_confirmada_em=confirmada)


def membro(usuario_id, projeto=CONEXOES, papel="consultor"):
    return SimpleNamespace(usuario_id=usuario_id, projeto_id=projeto, papel=papel)


ANA, BIA, ANDRE, COORD, CAIO = 1, 2, 3, 4, 5
FRENTES = {ANA: {BUSINESS}, BIA: {TECH}, ANDRE: {BUSINESS, TECH}, COORD: {DIREITO}, CAIO: {TECH}}

CONEXOES_ESCOPOS = [
    escopo(BUSINESS),
    escopo(DIREITO),
    escopo(TECH, status="nao_iniciado", inicio=None),
]
TIME = [membro(ANA), membro(BIA), membro(ANDRE), membro(COORD, papel="coordenador"), membro(CAIO)]


def ids(membros):
    return {m.usuario_id for m in membros}


class TestConexoes:
    def test_tech_parado_sai_e_quem_e_de_duas_frentes_fica(self):
        ficam = membros_da_periodica(PERIODICA, TIME, CONEXOES_ESCOPOS, FRENTES)

        assert ids(ficam) == {ANA, ANDRE, COORD}

    def test_ninguem_avalia_nem_e_avaliado_por_tech(self):
        pares = calcular_pares_lote(membros_da_periodica(PERIODICA, TIME, CONEXOES_ESCOPOS, FRENTES))

        envolvidos = {p.avaliador_id for p in pares} | {p.avaliado_id for p in pares}
        assert BIA not in envolvidos and CAIO not in envolvidos
        assert (ANDRE, ANA) in {(p.avaliador_id, p.avaliado_id) for p in pares}

    def test_finalizacao_nao_muda_nada(self):
        assert membros_da_periodica(FINALIZACAO, TIME, CONEXOES_ESCOPOS, FRENTES) == TIME


class TestRecortes:
    def test_frente_com_um_escopo_parado_e_outro_rodando_continua(self):
        escopos = [escopo(BUSINESS, status="nao_iniciado", inicio=None), escopo(BUSINESS)]

        assert ids(membros_da_periodica(PERIODICA, [membro(ANA)], escopos, FRENTES)) == {ANA}

    def test_escopo_ja_entregue_antes_do_lote_tira_a_frente(self):
        escopos = [escopo(BUSINESS), escopo(DIREITO, entrega=date(2026, 9, 30))]
        time = [membro(ANA), membro(COORD)]

        assert ids(membros_da_periodica(PERIODICA, time, escopos, FRENTES)) == {ANA}

    def test_entregue_depois_da_abertura_do_lote_ainda_conta(self):
        escopos = [escopo(DIREITO, entrega=date(2026, 10, 20))]

        assert ids(membros_da_periodica(PERIODICA, [membro(COORD)], escopos, FRENTES)) == {COORD}

    def test_projeto_sem_escopo_cadastrado_fica_inteiro(self):
        assert ids(membros_da_periodica(PERIODICA, TIME, [], FRENTES)) == ids(TIME)

    def test_projeto_sem_nenhum_escopo_em_andamento_sai_inteiro(self):
        escopos = [escopo(BUSINESS, status="nao_iniciado", inicio=None), escopo(TECH, entrega=date(2026, 9, 1))]

        assert membros_da_periodica(PERIODICA, TIME, escopos, FRENTES) == []

    def test_quem_nao_tem_frente_ligada_a_escopo_do_projeto_continua(self):
        # Alocado de outra frente (ou sem frente cadastrada): não tem por que sumir.
        escopos = [escopo(BUSINESS)]
        time = [membro(ANA), membro(COORD), membro(99)]

        assert ids(membros_da_periodica(PERIODICA, time, escopos, FRENTES)) == {ANA, COORD, 99}

    def test_cada_projeto_do_lote_tem_a_sua_conta(self):
        outro = 20
        escopos = CONEXOES_ESCOPOS + [escopo(TECH, projeto=outro)]
        time = TIME + [membro(BIA, projeto=outro)]

        ficam = membros_da_periodica(PERIODICA, time, escopos, FRENTES)

        assert (BIA, outro) in {(m.usuario_id, m.projeto_id) for m in ficam}
        assert (BIA, CONEXOES) not in {(m.usuario_id, m.projeto_id) for m in ficam}


class TestEmAndamentoEm:
    DIA = date(2026, 10, 12)

    def test_sem_reuniao_inicial_nao_comecou(self):
        assert not em_andamento_em(escopo(TECH, status="nao_iniciado", inicio=None), self.DIA)

    def test_comeca_depois_da_abertura_do_lote_nao_conta(self):
        assert not em_andamento_em(escopo(TECH, inicio=date(2026, 10, 20)), self.DIA)

    def test_cancelado_nunca_conta(self):
        assert not em_andamento_em(escopo(TECH, status="cancelado"), self.DIA)

    def test_entregue_so_com_a_confirmacao_tambem_sai(self):
        e = escopo(TECH, status="entregue", confirmada=datetime(2026, 10, 1, 15, 0))

        assert not em_andamento_em(e, self.DIA)

    def test_rodando(self):
        assert em_andamento_em(escopo(TECH), self.DIA)

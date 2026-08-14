"""As 🔄 condições do §6.6 — e a propriedade que justifica o desenho inteiro.

O teste que mais importa aqui é `test_condicao_some_quando_o_problema_e_resolvido`:
a condição **não é gravada**, é derivada a cada leitura. É isso que faz o sino
parar de cobrar no instante em que a tarefa é concluída, sem job nenhum
apagando linha. Se algum dia alguém decidir gravar as condições, este teste é
o que vai quebrar — e é o que deve quebrar.

Os dublês são escritos à mão (`SimpleNamespace`), no idioma do repo: as
funções não tocam em banco, então não há o que mockar.
"""

from datetime import date, datetime
from types import SimpleNamespace

from src.utils.condicoes_alerta import (
    BANCA_HOJE,
    BANCA_NAO_MARCADA,
    KICKOFF_PENDENTE,
    PROJETO_SEM_REUNIAO,
    TAREFA_VENCIDA,
    detectar_condicoes,
    para_papel,
)

# Agosto de 2026: 3 é segunda, 5 quarta, 7 sexta.
SEG_03 = date(2026, 8, 3)
QUA_05 = date(2026, 8, 5)
SEX_07 = date(2026, 8, 7)


def projeto(id=1, nome="Projeto Alfa", kickoff=SEG_03, status="em_andamento", dia_reuniao=2):
    """⚠ `dia_reuniao` entrou em 2026-08-13 (terça, por padrão).

    A cobrança de reunião semanal passou a esperar o dia da reunião PASSAR —
    antes disparava a partir de segunda 00:00, e na manhã de segunda todos os
    projetos ativos apareciam sem reunião. Os testes desta classe usam quarta
    como "hoje", então terça é o dia que os mantém cobrando.
    """
    return SimpleNamespace(
        id=id,
        nome=nome,
        data_kickoff=kickoff,
        status=status,
        dia_reuniao_padrao=dia_reuniao,
    )


def tarefa(id=1, prazo=SEG_03, responsavel_id=5, coluna_id=1, titulo="Benchmark"):
    return SimpleNamespace(
        id=id, prazo=prazo, responsavel_id=responsavel_id, coluna_id=coluna_id, titulo=titulo
    )


def escopo(id=10, status="em_andamento", data_inicio=SEG_03):
    return SimpleNamespace(id=id, status=status, data_inicio=data_inicio)


def banca(id=100, data_hora=None, realizado_em=None):
    return SimpleNamespace(id=id, data_hora=data_hora, realizado_em=realizado_em)


def detectar(projetos, *, tarefas=None, escopos=None, bancas=None, com_reuniao=(), hoje=QUA_05):
    """Só para não repetir os 7 parâmetros nomeados em cada teste."""
    return detectar_condicoes(
        projetos,
        escopos_por_projeto=escopos or {},
        bancas_por_escopo=bancas or {},
        nomes_escopo={10: "Análise Mercadológica"},
        tarefas_por_projeto=tarefas or {},
        # Coluna 1 = aberta, coluna 9 = encerra a tarefa (kanban configurável).
        encerra_por_coluna={1: False, 9: True},
        projetos_com_reuniao=set(com_reuniao),
        hoje=hoje,
    )


def tipos(condicoes):
    return {c.tipo for c in condicoes}


class TestKickoffPendente:
    def test_projeto_sem_kickoff_gera_alerta(self):
        assert KICKOFF_PENDENTE in tipos(detectar([projeto(kickoff=None)], com_reuniao=[1]))

    def test_com_kickoff_nao_gera(self):
        assert KICKOFF_PENDENTE not in tipos(detectar([projeto()], com_reuniao=[1]))

    def test_projeto_finalizado_nao_gera_nada(self):
        """Cobrar kickoff de projeto encerrado é ruído puro."""
        assert detectar([projeto(kickoff=None, status="finalizado")]) == []


class TestTarefaVencida:
    def test_prazo_passado_em_coluna_aberta_gera(self):
        condicoes = detectar([projeto()], tarefas={1: [tarefa(prazo=SEG_03)]}, com_reuniao=[1])
        vencidas = [c for c in condicoes if c.tipo == TAREFA_VENCIDA]
        assert len(vencidas) == 1
        assert vencidas[0].dias == 2
        # O alerta é de UMA pessoa: o responsável, não a equipe.
        assert vencidas[0].usuario_alvo == 5

    def test_condicao_some_quando_o_problema_e_resolvido(self):
        """⭐ A propriedade central: nada precisa apagar a notificação.

        Mover a tarefa para uma coluna que encerra é o único ato necessário —
        a condição deixa de ser detectada na leitura seguinte. Se as condições
        virassem linha no banco, este teste passaria a exigir um segundo job.
        """
        vencida = tarefa(prazo=SEG_03, coluna_id=1)
        assert TAREFA_VENCIDA in tipos(detectar([projeto()], tarefas={1: [vencida]}, com_reuniao=[1]))

        concluida = tarefa(prazo=SEG_03, coluna_id=9)
        assert TAREFA_VENCIDA not in tipos(
            detectar([projeto()], tarefas={1: [concluida]}, com_reuniao=[1])
        )

    def test_prazo_futuro_nao_gera(self):
        condicoes = detectar([projeto()], tarefas={1: [tarefa(prazo=SEX_07)]}, com_reuniao=[1])
        assert TAREFA_VENCIDA not in tipos(condicoes)

    def test_uma_condicao_por_tarefa(self):
        """Por tarefa, não por projeto: concluir uma não pode calar as outras."""
        tarefas = [tarefa(id=1, prazo=SEG_03), tarefa(id=2, prazo=SEG_03)]
        condicoes = detectar([projeto()], tarefas={1: tarefas}, com_reuniao=[1])
        chaves = {c.chave_dedup for c in condicoes if c.tipo == TAREFA_VENCIDA}
        assert chaves == {"tarefa_vencida:tarefa=1", "tarefa_vencida:tarefa=2"}


class TestSemReuniao:
    def test_sem_reuniao_na_semana_gera(self):
        assert PROJETO_SEM_REUNIAO in tipos(detectar([projeto()]))

    def test_com_reuniao_nao_gera(self):
        assert PROJETO_SEM_REUNIAO not in tipos(detectar([projeto()], com_reuniao=[1]))

    def test_sem_kickoff_nao_cobra_reuniao(self):
        """O projeto ainda não começou (§5.2) — o alerta de kickoff já cobre."""
        condicoes = detectar([projeto(kickoff=None)])
        assert PROJETO_SEM_REUNIAO not in tipos(condicoes)

    def test_a_semana_entra_na_chave(self):
        """Dispensar esta semana não pode silenciar a próxima."""
        desta = detectar([projeto()], hoje=QUA_05)[0].chave_dedup
        da_outra = detectar([projeto()], hoje=date(2026, 8, 12))[0].chave_dedup
        assert desta != da_outra
        assert desta.endswith("2026-W32")


class TestOdiaDaReuniaoPrecisaPassar:
    """⭐ Cobrar reunião antes do dia dela é cobrar o futuro.

    ⚠ A condição disparava assim que a semana virava. Numa segunda de manhã o
    "Atenção agora" abria com uma linha para CADA projeto ativo, todas
    idênticas — e um card que sempre acusa tudo deixa de ser lido.
    """

    def test_antes_do_dia_nao_cobra(self):
        """Reunião na terça, hoje é segunda: ela ainda vai acontecer."""
        condicoes = detectar([projeto(dia_reuniao=2)], hoje=SEG_03)
        assert PROJETO_SEM_REUNIAO not in tipos(condicoes)

    def test_no_proprio_dia_nao_cobra(self):
        """Hoje É terça: a reunião das 18h ainda não perdeu a hora."""
        condicoes = detectar([projeto(dia_reuniao=2)], hoje=date(2026, 8, 4))
        assert PROJETO_SEM_REUNIAO not in tipos(condicoes)

    def test_depois_do_dia_cobra(self):
        condicoes = detectar([projeto(dia_reuniao=2)], hoje=QUA_05)
        assert PROJETO_SEM_REUNIAO in tipos(condicoes)

    def test_sem_dia_definido_espera_ate_quinta(self):
        """Quem não definiu dia ganha a semana quase inteira antes do alerta."""
        assert PROJETO_SEM_REUNIAO not in tipos(detectar([projeto(dia_reuniao=None)], hoje=QUA_05))
        assert PROJETO_SEM_REUNIAO in tipos(
            detectar([projeto(dia_reuniao=None)], hoje=date(2026, 8, 7))
        )

    def test_reuniao_na_sexta_nao_cobra_na_quinta(self):
        """A régua é do PROJETO, não do calendário: quem se reúne sexta não é
        cobrado quinta, mesmo com o padrão sendo quinta."""
        condicoes = detectar([projeto(dia_reuniao=5)], hoje=date(2026, 8, 6))
        assert PROJETO_SEM_REUNIAO not in tipos(condicoes)


class TestBanca:
    def test_escopo_iniciado_sem_banca_gera(self):
        condicoes = detectar([projeto()], escopos={1: [escopo()]}, com_reuniao=[1])
        assert BANCA_NAO_MARCADA in tipos(condicoes)

    def test_escopo_nao_iniciado_nao_cobra_banca(self):
        """Antes do `data_inicio` não há cronograma oficializado — §5.3 nem
        pede a data ainda."""
        condicoes = detectar(
            [projeto()], escopos={1: [escopo(data_inicio=None)]}, com_reuniao=[1]
        )
        assert BANCA_NAO_MARCADA not in tipos(condicoes)

    def test_escopo_entregue_nao_cobra_banca(self):
        condicoes = detectar([projeto()], escopos={1: [escopo(status="entregue")]}, com_reuniao=[1])
        assert BANCA_NAO_MARCADA not in tipos(condicoes)

    def test_banca_hoje_gera_lembrete(self):
        marcada = banca(data_hora=datetime(2026, 8, 5, 14, 0))
        condicoes = detectar(
            [projeto()], escopos={1: [escopo()]}, bancas={10: marcada}, com_reuniao=[1]
        )
        lembrete = next(c for c in condicoes if c.tipo == BANCA_HOJE)
        assert "14:00" in lembrete.titulo

    def test_banca_ja_realizada_nao_lembra(self):
        realizada = banca(
            data_hora=datetime(2026, 8, 5, 14, 0), realizado_em=datetime(2026, 8, 5, 15, 0)
        )
        condicoes = detectar(
            [projeto()], escopos={1: [escopo()]}, bancas={10: realizada}, com_reuniao=[1]
        )
        assert BANCA_HOJE not in tipos(condicoes)

    def test_banca_de_varios_escopos_lembra_uma_vez_so(self):
        """Uma banca que cobre 3 escopos aparece em 3 chaves do mapa — sem o
        cuidado, o consultor levaria o mesmo lembrete três vezes."""
        marcada = banca(data_hora=datetime(2026, 8, 5, 14, 0))
        escopos = [escopo(id=10), escopo(id=11), escopo(id=12)]
        condicoes = detectar(
            [projeto()],
            escopos={1: escopos},
            bancas={10: marcada, 11: marcada, 12: marcada},
            com_reuniao=[1],
        )
        assert len([c for c in condicoes if c.tipo == BANCA_HOJE]) == 1


class TestParaPapel:
    """A matriz de quem-recebe-o-quê, §5.2/§5.3/§6.4."""

    def _condicoes(self):
        return detectar(
            [projeto(kickoff=None)],
            tarefas={1: [tarefa(prazo=SEG_03, responsavel_id=5)]},
            escopos={1: [escopo()]},
        )

    def test_consultor_nao_recebe_o_que_nao_pode_resolver(self):
        recebidas = tipos(para_papel(self._condicoes(), "consultor", usuario_id=5))
        assert KICKOFF_PENDENTE in recebidas
        assert TAREFA_VENCIDA in recebidas
        # Marcar banca e registrar reunião são da coordenação.
        assert BANCA_NAO_MARCADA not in recebidas
        assert PROJETO_SEM_REUNIAO not in recebidas

    def test_coordenador_recebe_o_que_e_dele(self):
        recebidas = tipos(para_papel(self._condicoes(), "coordenador", usuario_id=3))
        assert BANCA_NAO_MARCADA in recebidas
        assert KICKOFF_PENDENTE in recebidas

    def test_tarefa_vencida_so_para_o_responsavel(self):
        """Nem o papel manda aqui: quem recebe é quem tem a tarefa."""
        do_dono = para_papel(self._condicoes(), "consultor", usuario_id=5)
        de_outro = para_papel(self._condicoes(), "consultor", usuario_id=99)
        assert TAREFA_VENCIDA in tipos(do_dono)
        assert TAREFA_VENCIDA not in tipos(de_outro)

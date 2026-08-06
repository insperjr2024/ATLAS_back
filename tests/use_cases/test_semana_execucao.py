"""A janela da semana da aba de Execução (§7.2).

Existe por causa de um bug que só apareceria quando a tela ganhasse navegação
entre semanas: `criadas_na_semana` filtrava por `>= inicio`, sem limite
superior. Com a semana sempre terminando em hoje, o erro era invisível — não
há tarefa criada no futuro. Ao voltar no tempo, porém, "distribuiu na semana"
passava a contar tudo que veio DEPOIS daquela segunda-feira.

Medido no banco de demonstração: 8 semanas atrás, a lógica antiga dizia que 15
projetos distribuíram tarefa; o correto era 0.
"""

from datetime import date, datetime, timedelta

from src.utils.tarefa_status import janela_semana

# Segunda 2026-07-06, domingo 2026-07-12.
SEG = date(2026, 7, 6)
DOM = date(2026, 7, 12)


def criada_em(dia: date):
    """Só o que o filtro olha: a data de criação da tarefa."""
    return datetime.combine(dia, datetime.min.time())


def distribuiu(datas_de_criacao, referencia):
    """Reproduz o filtro do use case, isolado do banco."""
    inicio, fim = janela_semana(referencia)
    return [d for d in datas_de_criacao if inicio <= d.date() <= fim]


class TestJanelaDaSemana:
    def test_a_janela_e_de_segunda_a_domingo(self):
        assert janela_semana(date(2026, 7, 8)) == (SEG, DOM)

    def test_qualquer_dia_da_semana_devolve_a_mesma_janela(self):
        """O front manda um dia qualquer; o servidor normaliza para a semana."""
        assert janela_semana(SEG) == janela_semana(DOM) == (SEG, DOM)


class TestCriadasNaSemana:
    def test_conta_o_que_foi_criado_dentro_da_janela(self):
        dentro = [criada_em(SEG), criada_em(date(2026, 7, 9)), criada_em(DOM)]
        assert len(distribuiu(dentro, SEG)) == 3

    def test_ignora_o_que_veio_ANTES_da_segunda(self):
        assert distribuiu([criada_em(SEG - timedelta(days=1))], SEG) == []

    def test_ignora_o_que_veio_DEPOIS_do_domingo(self):
        """O bug. Sem limite superior, tarefa criada semanas depois contava
        como se tivesse sido distribuída naquela semana."""
        depois = [
            criada_em(DOM + timedelta(days=1)),
            criada_em(DOM + timedelta(weeks=4)),
        ]
        assert distribuiu(depois, SEG) == []

    def test_semana_vazia_com_atividade_posterior_continua_vazia(self):
        """O caso real medido no banco: nada naquela semana, muita coisa
        depois. Antes dizia 'distribuiu'; agora diz a verdade."""
        so_depois = [criada_em(DOM + timedelta(days=n)) for n in (1, 5, 20, 60)]
        assert distribuiu(so_depois, SEG) == []
        # E cada semana seguinte enxerga só as suas: 13/07 e 17/07 caem juntas
        # na semana de 13 a 19; as outras duas, em semanas mais adiante.
        assert len(distribuiu(so_depois, DOM + timedelta(days=1))) == 2
        assert len(distribuiu(so_depois, DOM + timedelta(days=20))) == 1

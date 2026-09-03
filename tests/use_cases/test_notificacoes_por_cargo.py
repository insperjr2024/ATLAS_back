"""A matriz do §6.6: o que cada cargo vê no sino.

Duas regras dominam estes testes:

- **A liderança recebe somado.** O diretor enxerga todos os projetos; uma linha
  por tarefa vencida da consultoria inteira faria o sino ser silenciado na
  primeira semana — e sino ignorado não notifica ninguém.
- **O individual ganha do agregado.** A tarefa vencida que é da própria pessoa
  chega como item próprio e sai da conta do resumo. Sem isso ela apareceria
  duas vezes na mesma lista.

`montar` não toca em banco, então o teste a exercita direto — mesmo idioma de
`test_marco_sem_tarefa.py`, que instancia o use case sem `__init__`.
"""

from datetime import date
from types import SimpleNamespace

from src.use_cases.notificacao.listar_notificacoes import ListarNotificacoesUseCase
from src.utils.condicoes_alerta import Condicao

HOJE = date(2026, 8, 5)

CASO = ListarNotificacoesUseCase.__new__(ListarNotificacoesUseCase)


def condicao(tipo, projeto_id=1, chave=None, usuario_alvo=None, nome="Projeto Alfa"):
    return Condicao(
        tipo=tipo,
        projeto_id=projeto_id,
        projeto_nome=nome,
        titulo=f"{nome} — {tipo}",
        chave_dedup=chave or f"{tipo}:projeto={projeto_id}",
        rota=f"/projetos/{projeto_id}",
        usuarios_alvo=[usuario_alvo] if usuario_alvo is not None else [],
    )


def montar(condicoes, papeis=None, usuario_id=5, posicao="consultor", leituras=None):
    return CASO.montar(
        condicoes,
        papeis=papeis or {},
        usuario_id=usuario_id,
        posicao=posicao,
        leituras=leituras or {},
        hoje=HOJE,
    )


class TestConsultor:
    def test_recebe_item_a_item_do_projeto_dele(self):
        itens = montar(
            [condicao("kickoff_pendente")],
            papeis={1: "consultor"},
        )
        assert [i["titulo"] for i in itens] == ["Projeto Alfa — kickoff_pendente"]
        assert itens[0]["total"] is None

    def test_nao_recebe_nada_de_projeto_em_que_nao_esta(self):
        """O recorte do §3 aplicado ao sino: sem papel no projeto, sem alerta."""
        assert montar([condicao("kickoff_pendente", projeto_id=2)], papeis={1: "consultor"}) == []

    def test_nao_vira_agregado_para_quem_nao_e_lideranca(self):
        muitas = [
            condicao("tarefa_vencida", projeto_id=2, chave=f"t{i}", usuario_alvo=5)
            for i in range(11)
        ]
        assert montar(muitas, papeis={1: "consultor"}) == []


class TestDiretor:
    def _onze_vencidas_em_quatro_projetos(self):
        return [
            condicao(
                "tarefa_vencida",
                projeto_id=(i % 4) + 1,
                chave=f"tarefa_vencida:tarefa={i}",
                usuario_alvo=99,
            )
            for i in range(11)
        ]

    def test_onze_tarefas_viram_uma_linha(self):
        itens = montar(self._onze_vencidas_em_quatro_projetos(), posicao="diretor_projetos", usuario_id=1)
        assert len(itens) == 1
        assert itens[0]["titulo"] == "11 tarefas vencidas"
        assert itens[0]["total"] == 11
        # O detalhe já existe e é melhor do que qualquer lista no sino.
        assert itens[0]["rota"] == "/monitoramento"

    def test_o_agregado_e_por_tipo(self):
        condicoes = [
            condicao("kickoff_pendente", projeto_id=1),
            condicao("kickoff_pendente", projeto_id=2),
            condicao("projeto_sem_reuniao", projeto_id=3),
        ]
        itens = montar(condicoes, posicao="diretor_projetos", usuario_id=1)
        assert {i["titulo"] for i in itens} == {
            "2 projetos sem kickoff",
            "1 projeto sem reunião esta semana",
        }

    def test_singular_quando_e_um_so(self):
        itens = montar([condicao("kickoff_pendente")], posicao="diretor_projetos", usuario_id=1)
        assert itens[0]["titulo"] == "1 projeto sem kickoff"

    def test_individual_ganha_do_agregado(self):
        """A diretora também coordena o Alfa: o kickoff do Alfa chega a ela
        item a item e NÃO é contado outra vez no resumo."""
        condicoes = [
            condicao("kickoff_pendente", projeto_id=1, nome="Alfa"),
            condicao("kickoff_pendente", projeto_id=2, nome="Beta"),
            condicao("kickoff_pendente", projeto_id=3, nome="Gama"),
        ]
        itens = montar(condicoes, papeis={1: "coordenador"}, posicao="diretor_projetos", usuario_id=1)

        individuais = [i for i in itens if i["total"] is None]
        agregados = [i for i in itens if i["total"] is not None]
        assert [i["titulo"] for i in individuais] == ["Alfa — kickoff_pendente"]
        # 3 projetos, 1 entregue individualmente → o resumo conta os outros 2.
        assert agregados[0]["total"] == 2

    def test_a_data_entra_na_chave_do_agregado(self):
        """Dispensar "11 tarefas vencidas" hoje não pode silenciar as 20 de
        amanhã — o resumo da liderança é sempre o estado de HOJE."""
        itens = montar([condicao("kickoff_pendente")], posicao="diretor_projetos", usuario_id=1)
        assert itens[0]["chave"] == "agregado:kickoff_pendente:2026-08-05"


class TestLeitura:
    def test_condicao_sem_linha_no_banco_e_nao_lida(self):
        """A ausência de chave em `leituras` É o "não lida" — a condição não
        tem linha até alguém dispensá-la."""
        itens = montar([condicao("kickoff_pendente")], papeis={1: "consultor"})
        assert itens[0]["lida"] is False
        assert itens[0]["id"] is None

    def test_dispensada_aparece_como_lida(self):
        from datetime import datetime

        itens = montar(
            [condicao("kickoff_pendente")],
            papeis={1: "consultor"},
            leituras={"kickoff_pendente:projeto=1": datetime(2026, 8, 5, 9, 0)},
        )
        assert itens[0]["lida"] is True

    def test_marcar_como_lida_nao_resolve_o_problema(self):
        """A condição continua NA LISTA depois de lida — ela só sai da
        contagem do sino. Sumir daqui é responsabilidade de marcar o kickoff,
        não de clicar em "lida"."""
        from datetime import datetime

        itens = montar(
            [condicao("kickoff_pendente")],
            papeis={1: "consultor"},
            leituras={"kickoff_pendente:projeto=1": datetime(2026, 8, 5, 9, 0)},
        )
        assert len(itens) == 1

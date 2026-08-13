"""⭐ O resultado da banca sai do VOTO de quem assistiu (§8).

Antes era uma string digitada — e ninguém digitava: a função existia no front
sem chamador nenhum, e as 8 bancas realizadas da base estavam todas sem
veredito. A apuração fecha esse buraco.

Duas bordas mandam nestes testes, e as duas são DECISÕES de produto, não
detalhes de implementação:

- **empate reprova**, porque `resultado` é um gate que abre a entrega ao
  cliente, e o default seguro de um gate é fechado;
- **zero voto não decide**, porque silêncio não é veredito — nem a favor nem
  contra.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.utils.apuracao_banca import (
    AGUARDANDO,
    EMPATE,
    MAIORIA,
    SEM_VOTOS,
    apurar,
    eleitorado,
    votos_por_avaliador,
)


class TestMaioria:
    def test_maioria_aprova(self):
        r = apurar([True, True, False], esperados=3)

        assert (r.resultado, r.motivo) == ("aprovada", MAIORIA)
        assert (r.aprovacoes, r.reprovacoes) == (2, 1)

    def test_maioria_reprova(self):
        r = apurar([False, False, True], esperados=3)

        assert (r.resultado, r.motivo) == ("nao_aprovada", MAIORIA)

    def test_unanimidade_decide(self):
        assert apurar([True, True], esperados=2).resultado == "aprovada"

    def test_um_voto_so_decide_se_e_o_unico_esperado(self):
        assert apurar([True], esperados=1).resultado == "aprovada"


class TestEmpate:
    def test_empate_reprova(self):
        """⭐ O gate fecha por default.

        Empate não é "meio aprovado": é a banca não ter formado consenso de que
        o trabalho pode ir ao cliente. Aprovar aqui abriria a entrega por
        ausência de acordo.
        """
        r = apurar([True, False], esperados=2)

        assert (r.resultado, r.motivo) == ("nao_aprovada", EMPATE)

    def test_empate_grande_tambem_reprova(self):
        assert apurar([True, True, False, False], esperados=4).resultado == "nao_aprovada"


class TestSemVotos:
    def test_prazo_aberto_e_ninguem_votou_aguarda(self):
        r = apurar([], esperados=3)

        assert (r.resultado, r.motivo) == (None, AGUARDANDO)

    def test_prazo_vencido_sem_voto_nao_decide(self):
        """⭐ Silêncio não é veredito.

        Reprovar puniria o projeto pela omissão dos avaliadores; aprovar
        abriria a entrega sem ninguém ter dito que o trabalho presta. Fica
        pendente e a diretoria decide pelo override.
        """
        r = apurar([], esperados=3, prazo_vencido=True)

        assert (r.resultado, r.motivo) == (None, SEM_VOTOS)
        assert r.decidida is False


class TestQuorum:
    def test_nao_decide_com_meia_urna(self):
        """⚠ 2×0 com dois votos por vir pode virar 2×2 — decidir aqui seria
        decidir com metade dos votos."""
        r = apurar([True, True], esperados=4)

        assert (r.resultado, r.motivo) == (None, AGUARDANDO)

    def test_prazo_vencido_decide_com_quem_votou(self):
        """Depois do prazo, quem não votou abriu mão — não trava o projeto."""
        r = apurar([True, True], esperados=4, prazo_vencido=True)

        assert (r.resultado, r.motivo) == ("aprovada", MAIORIA)

    def test_todos_votaram_decide_na_hora(self):
        r = apurar([True, False, True], esperados=3)

        assert r.resultado == "aprovada"
        assert r.recebidos == r.esperados


class TestEleitorado:
    def _cand(self, usuario_id, confirmado):
        return SimpleNamespace(usuario_id=usuario_id, confirmado=confirmado)

    def test_conta_so_quem_compareceu(self):
        """Quem foi escalado e faltou não deve voto — contá-lo como abstenção
        puniria o projeto pela falta de outra pessoa."""
        candidaturas = [self._cand(1, True), self._cand(2, True), self._cand(3, False)]

        assert eleitorado(candidaturas, []) == 2

    def test_sem_ninguem_confirmado_cai_para_todos_os_candidatos(self):
        """⚠ A borda que travaria a apuração para sempre.

        `RegistrarRealizacaoBancaUseCase` só grava presença quando a lista vem
        preenchida; com `presentes=None` ninguém fica confirmado. Sem este
        fallback o eleitorado seria zero e nenhuma apuração jamais fecharia.
        """
        candidaturas = [self._cand(1, False), self._cand(2, False)]

        assert eleitorado(candidaturas, []) == 2

    def test_quem_votou_sem_estar_confirmado_entra_na_conta(self):
        """⚠ Senão `recebidos > esperados` e o gatilho 'todos votaram' nunca
        dispara — a apuração ficaria presa esperando o prazo."""
        candidaturas = [self._cand(1, True), self._cand(2, False)]

        assert eleitorado(candidaturas, [2]) == 2

    def test_banca_sem_candidatura_nenhuma(self):
        assert eleitorado([], []) == 0


class TestUmMembroUmVoto:
    """⚠ Regressão de um defeito visto na base real, não hipótese.

    Não há UNIQUE em (avaliador, banca) e o front cria a avaliação ao abrir o
    formulário — abrir duas vezes gera duas linhas. Na primeira apuração contra
    a base isso saiu como 4×2 num eleitorado de 3 pessoas.
    """

    def _av(self, avaliador_id, voto, submetida_em=None):
        return SimpleNamespace(
            avaliador_id=avaliador_id, voto_aprovacao=voto, submetida_em=submetida_em
        )

    def test_duas_avaliacoes_do_mesmo_membro_valem_uma(self):
        escolhidos = votos_por_avaliador([self._av(1, True), self._av(1, True)])

        assert len(escolhidos) == 1

    def test_vence_o_envio_mais_recente(self):
        antigo = self._av(1, True, datetime(2026, 8, 10, 9, 0))
        novo = self._av(1, False, datetime(2026, 8, 11, 9, 0))

        assert votos_por_avaliador([antigo, novo])[1] is novo
        assert votos_por_avaliador([novo, antigo])[1] is novo

    def test_submetida_em_nulo_perde_para_qualquer_data(self):
        sem_data = self._av(1, True, None)
        com_data = self._av(1, False, datetime(2026, 8, 11, 9, 0))

        assert votos_por_avaliador([sem_data, com_data])[1] is com_data

    def test_membros_diferentes_continuam_contando_separado(self):
        assert len(votos_por_avaliador([self._av(1, True), self._av(2, False)])) == 2

    def test_duplicata_nao_decide_a_banca_sozinha(self):
        """O cenário completo: o duplicado viraria maioria contra dois votos."""
        avaliacoes = [self._av(1, True), self._av(1, True), self._av(2, False), self._av(3, False)]

        votos = [a.voto_aprovacao for a in votos_por_avaliador(avaliacoes).values()]

        assert apurar(votos, esperados=3).resultado == "nao_aprovada"


class TestIntegracaoDasRegras:
    @pytest.mark.parametrize(
        "votos,esperados,vencido,alvo",
        [
            ([True, True, True], 3, False, "aprovada"),
            ([False], 1, False, "nao_aprovada"),
            ([True, False], 2, False, "nao_aprovada"),  # empate
            ([], 2, True, None),                        # silêncio
            ([True], 3, False, None),                   # ainda votando
            ([True], 3, True, "aprovada"),              # prazo fechou
        ],
    )
    def test_tabela_verdade(self, votos, esperados, vencido, alvo):
        assert apurar(votos, esperados, prazo_vencido=vencido).resultado == alvo

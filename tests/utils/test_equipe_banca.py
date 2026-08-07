"""§8: quem é "do próprio grupo" de uma banca — e por que a resposta tem duas fontes.

⭐ **O bug que estes testes prendem:** banca marcada pelo CRONOGRAMA não escreve
em `equipe_projeto` (a tabela legada, preenchida à mão na tela de bancas). Como
a trava do §8 lia só aquela tabela, os consultores do projeto apareciam como
elegíveis para a própria banca e conseguiam se inscrever nela.

A equipe real é `projeto_membro`, alcançada pelos escopos que a banca cobre.
As duas fontes valem: a legada cobre as bancas antigas, a nova cobre as que
nascem no calendário.
"""

from types import SimpleNamespace

from src.utils.equipe_banca import mapa_de_equipes, membros_da_banca

BANCA = SimpleNamespace(id=29, coordenador_id=16)


class _BancaEscopoFake:
    def __init__(self, escopos_por_banca):
        self._mapa = escopos_por_banca

    def get_escopo_ids(self, banca_id):
        return self._mapa.get(banca_id, [])


class _EscopoFake:
    def __init__(self, escopos):
        self._escopos = escopos

    def get_by_id(self, escopo_id):
        return self._escopos.get(escopo_id)


class _MembroFake:
    def __init__(self, membros_por_projeto):
        self._mapa = membros_por_projeto

    def get_by_projeto(self, projeto_id, apenas_atuais=False):
        return self._mapa.get(projeto_id, [])


class _EquipeLegadaFake:
    def __init__(self, por_banca):
        self._mapa = por_banca

    def get_by_banca(self, banca_id):
        return self._mapa.get(banca_id, [])


def montar(*, escopos_da_banca=(48,), membros=(4, 5), legado=()):
    return dict(
        banca_escopo_repository=_BancaEscopoFake({BANCA.id: list(escopos_da_banca)}),
        escopo_repository=_EscopoFake({48: SimpleNamespace(id=48, projeto_id=32)}),
        membro_repository=_MembroFake(
            {32: [SimpleNamespace(usuario_id=u) for u in membros]}
        ),
        equipe_projeto_repository=_EquipeLegadaFake(
            {BANCA.id: [SimpleNamespace(usuario_id=u) for u in legado]}
        ),
    )


class TestMembrosDaBanca:
    def test_a_equipe_do_projeto_entra_mesmo_sem_a_tabela_legada(self):
        """⭐ O caso da banca marcada pelo cronograma: `equipe_projeto` vazia,
        e mesmo assim o consultor do projeto não pode avaliá-la."""
        assert membros_da_banca(BANCA, **montar()) == {16, 4, 5}

    def test_o_coordenador_da_banca_sempre_entra(self):
        sozinho = montar(membros=(), legado=())
        assert membros_da_banca(BANCA, **sozinho) == {16}

    def test_a_tabela_legada_continua_valendo(self):
        """Bancas antigas foram montadas à mão e não têm escopo vinculado."""
        antiga = montar(escopos_da_banca=(), membros=(), legado=(7, 8))
        assert membros_da_banca(BANCA, **antiga) == {16, 7, 8}

    def test_as_duas_fontes_se_somam_sem_duplicar(self):
        assert membros_da_banca(BANCA, **montar(membros=(4, 5), legado=(5, 9))) == {
            16,
            4,
            5,
            9,
        }

    def test_escopo_que_sumiu_nao_derruba_a_conta(self):
        """Vínculo apontando para escopo apagado: a banca não pode ficar sem
        equipe por causa disso — o coordenador continua barrado."""
        orfa = montar(escopos_da_banca=(999,))
        assert membros_da_banca(BANCA, **orfa) == {16}


class TestMapaDeEquipes:
    def test_uma_entrada_por_banca(self):
        """A tela de bancas monta três baldes e pergunta "é do meu grupo?" em
        cada um; sem o mapa pronto viraria uma consulta por card."""
        mapa = mapa_de_equipes([BANCA], **montar())
        assert mapa == {29: {16, 4, 5}}

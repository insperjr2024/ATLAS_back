"""🔒 Só quem esteve na banca decide o resultado dela (§8).

Estes testes nasceram de um furo encontrado num teste ponta a ponta contra a
base real, não de uma hipótese: um voto de quem **não estava escalado** entrou
na apuração e fechou uma banca em empate — `nao_aprovada` — travando a entrega
ao cliente de um projeto que o votante nem enxergava.

O vetor era indireto, e é por isso que a trava tinha de mudar de lugar. As
rotas de criar e de submeter avaliação já exigiam candidatura; o que não
exigia era o `PATCH /avaliacoes/{id}` genérico, que aceitava trocar o
`banca_id` de uma avaliação **já submetida**. Bastava votar numa banca legítima
e depois mudar o destino do voto.

⭐ A lição de projeto: enquanto a regra viveu nas ROTAS, cada rota nova era uma
chance de esquecê-la. Movida para a apuração — o único lugar por onde todo voto
obrigatoriamente passa — ela vale para caminhos de escrita que ainda nem
existem.
"""

from types import SimpleNamespace

import pytest

from src.utils.apuracao_banca import apurar, eleitorado, votos_por_avaliador


def voto(avaliador_id, aprova, submetida_em=None):
    return SimpleNamespace(
        avaliador_id=avaliador_id,
        voto_aprovacao=aprova,
        submetida_em=submetida_em,
        status="submetida",
    )


def candidato(usuario_id, confirmado=True):
    return SimpleNamespace(usuario_id=usuario_id, confirmado=confirmado)


def filtrar_pela_urna(avaliacoes, candidaturas):
    """A regra que `apurar_banca` aplica, isolada para poder ser testada sem banco.

    ⚠ Mantida em espelho de propósito: se a de lá mudar e esta não, o teste
    passa a medir outra coisa. O que amarra as duas é o nome do conceito —
    `escalados` — e a borda da banca legada abaixo.
    """
    escalados = {c.usuario_id for c in candidaturas}
    return [
        a
        for a in avaliacoes
        if a.status == "submetida"
        and a.voto_aprovacao is not None
        and (not escalados or a.avaliador_id in escalados)
    ]


class TestVotoDeForaNaoConta:
    def test_estranho_nao_entra_na_conta(self):
        """O caso exato do furo: 1×1 vira 1×0 quando o intruso sai."""
        candidaturas = [candidato(1), candidato(2)]
        avaliacoes = [voto(1, True), voto(99, False)]  # 99 não foi escalado

        contados = filtrar_pela_urna(avaliacoes, candidaturas)

        assert [a.avaliador_id for a in contados] == [1]

    def test_o_intruso_mudava_o_veredito(self):
        """⭐ Por que isto é crítico e não cosmético.

        Com o voto de fora a banca empatava, e empate REPROVA — a entrega ao
        cliente ficava travada por decisão de quem não estava lá.
        """
        candidaturas = [candidato(1), candidato(2)]
        com_intruso = [voto(1, True), voto(99, False)]

        sem_filtro = apurar([a.voto_aprovacao for a in com_intruso], esperados=2)
        contados = filtrar_pela_urna(com_intruso, candidaturas)
        com_filtro = apurar(
            [a.voto_aprovacao for a in contados],
            esperados=eleitorado(candidaturas, [a.avaliador_id for a in contados]),
        )

        assert sem_filtro.resultado == "nao_aprovada"  # o furo
        assert com_filtro.resultado is None  # 1 de 2 votou: ainda aguarda

    def test_eleitorado_nao_infla_mais_com_estranho(self):
        """`eleitorado` une votantes ao conjunto de escalados para o gatilho
        'todos votaram' não travar. Com a urna filtrada antes, essa união
        deixa de ser porta de entrada — todo votante já é escalado."""
        candidaturas = [candidato(1), candidato(2)]
        contados = filtrar_pela_urna([voto(1, True), voto(99, False)], candidaturas)

        assert eleitorado(candidaturas, [a.avaliador_id for a in contados]) == 2

    def test_rascunho_nao_conta_mesmo_de_quem_foi_escalado(self):
        candidaturas = [candidato(1)]
        rascunho = voto(1, True)
        rascunho.status = "rascunho"

        assert filtrar_pela_urna([rascunho], candidaturas) == []

    def test_submetida_sem_voto_nao_conta(self):
        """Formulário enviado antes de o voto existir (registros antigos):
        `voto_aprovacao` nulo não é abstenção nem posição."""
        candidaturas = [candidato(1)]

        assert filtrar_pela_urna([voto(1, None)], candidaturas) == []


class TestBancaLegada:
    def test_sem_candidatura_nenhuma_a_urna_nao_zera(self):
        """⚠ A borda que transformaria a proteção em apagão.

        Bancas antigas não têm candidatura registrada. Filtrar por um conjunto
        VAZIO descartaria todos os votos e nenhuma dessas bancas fecharia
        jamais — trocaríamos um furo por uma trava permanente.
        """
        avaliacoes = [voto(1, True), voto(2, True)]

        assert len(filtrar_pela_urna(avaliacoes, [])) == 2


class TestUrnaMaisDeduplicacao:
    def test_as_duas_regras_convivem(self):
        """Filtrar por escalados e reduzir a um voto por pessoa são regras
        diferentes, e a conta final precisa das duas."""
        candidaturas = [candidato(1), candidato(2), candidato(3)]
        avaliacoes = [
            voto(1, True),
            voto(1, True),   # duplicata do mesmo membro
            voto(2, False),
            voto(99, False),  # intruso
        ]

        contados = filtrar_pela_urna(avaliacoes, candidaturas)
        unicos = votos_por_avaliador(contados)

        assert sorted(unicos) == [1, 2]
        assert apurar([a.voto_aprovacao for a in unicos.values()], esperados=3).resultado is None


@pytest.mark.parametrize(
    "escalados,votantes,esperado",
    [
        ([1, 2, 3], [1, 2, 3], 3),
        ([1, 2, 3], [1, 99], 1),
        ([1], [99], 0),
        ([], [7, 8], 2),  # legada: passa tudo
    ],
)
def test_tabela_de_quem_entra(escalados, votantes, esperado):
    candidaturas = [candidato(u) for u in escalados]
    avaliacoes = [voto(u, True) for u in votantes]

    assert len(filtrar_pela_urna(avaliacoes, candidaturas)) == esperado

"""⭐ 2026-09-18, a pedido: `GET /bancas` sabe dizer, POR PESSOA, se a última
vaga de uma banca está reservada pra outra frente — a mesma banca é "tem
vaga" pra quem cobre a cota que falta e "lotada" pra quem não cobre.

Mesma conta de `CreateCandidaturaUseCase` (a reserva das últimas vagas pro
piso por frente), replicada aqui em modo LEITURA — sem criar candidatura
nenhuma. `FakeChecker`/`FakeResolver` no mesmo idioma de
`test_composicao_na_listagem_de_bancas.py`.
"""

from types import SimpleNamespace

from src.use_cases.banca.get_banca import vaga_disponivel_para_usuario

BUSINESS = 1


class FakeResolver:
    def __init__(self, regras=None):
        self._regras = regras or []

    def para(self, frente_ids):
        return self._regras


class FakeChecker:
    def __init__(self, deficits):
        self._deficits = deficits
        self.chamado_com = None

    def verificar(self, _banca, _regras, candidato_ids):
        self.chamado_com = candidato_ids
        return SimpleNamespace(deficits=self._deficits)


def deficit(lideranca=0, membros=0):
    return SimpleNamespace(piso_faltando=membros, lideranca_faltando=lideranca)


BANCA = SimpleNamespace(id=1, coordenador_id=None)


def test_quem_ja_e_candidato_sempre_tem_vaga():
    # Nem chega a olhar teto ou composição — a pergunta não é dele.
    assert vaga_disponivel_para_usuario(
        BANCA, [], [10], 10, FakeResolver(), FakeChecker([]), vagas=1
    )


def test_teto_cheio_nao_tem_vaga_pra_ninguem():
    assert not vaga_disponivel_para_usuario(
        BANCA, [SimpleNamespace(id=BUSINESS)], [10, 11], 50, FakeResolver(), FakeChecker([]), vagas=2
    )


def test_banca_legada_sem_frente_tem_vaga_se_o_teto_nao_estourou():
    assert vaga_disponivel_para_usuario(
        BANCA, [], [10], 50, FakeResolver(), FakeChecker([]), vagas=8
    )


def test_ultima_vaga_reservada_bloqueia_quem_nao_cobre_a_cota():
    """7/8: falta 1 liderança de Business, e a pessoa 50 não cobre essa
    cota — a mesma aritmética de `test_vaga_reservada_pro_piso.py`."""
    checker = FakeChecker([deficit(lideranca=1)])
    resultado = vaga_disponivel_para_usuario(
        BANCA,
        [SimpleNamespace(id=BUSINESS)],
        list(range(10, 17)),
        50,
        FakeResolver(),
        checker,
        vagas=8,
    )
    assert resultado is False
    assert checker.chamado_com == set(range(10, 17)) | {50}


def test_quem_cobre_a_cota_tem_vaga_na_ultima():
    """Mesmo 7/8 com 1 de liderança faltando, quem cobre a cota (o checker
    devolve deficit zerado pra ela) tem vaga."""
    checker = FakeChecker([])
    resultado = vaga_disponivel_para_usuario(
        BANCA,
        [SimpleNamespace(id=BUSINESS)],
        list(range(10, 17)),
        99,
        FakeResolver(),
        checker,
        vagas=8,
    )
    assert resultado is True


def test_com_folga_de_vaga_qualquer_um_tem_vaga():
    """3/8: sobram 5 vagas pra 1 de déficit — há folga, ninguém é barrado."""
    checker = FakeChecker([deficit(lideranca=1)])
    resultado = vaga_disponivel_para_usuario(
        BANCA,
        [SimpleNamespace(id=BUSINESS)],
        list(range(10, 13)),
        50,
        FakeResolver(),
        checker,
        vagas=8,
    )
    assert resultado is True

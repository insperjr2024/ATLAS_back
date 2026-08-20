"""A correção do início da ambientação — a exceção de §5.3.

⭐ O padrão continua "ambientação = kickoff": isto aqui só existe pro caso em
que o time começou antes do kickoff formal, e o coordenador registra isso.

⚠ **Quem edita é vínculo, não cargo**: o coordenador DAQUELE projeto ou a
diretoria — mesmo idioma de `test_confirmacao_da_entrega.py`, a checagem mora
no use case, que tem a equipe à mão.

Dublês à mão + `monkeypatch` das classes de repositório no módulo.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.projeto import update_inicio_ambientacao
from src.use_cases.projeto.update_inicio_ambientacao import (
    UpdateInicioAmbientacaoRequest,
    UpdateInicioAmbientacaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# Kickoff numa segunda-feira: sexta anterior (2 dias úteis) atravessa um fim
# de semana sem contá-lo, e é o que prova que o limite é em dias ÚTEIS.
SEG_KICKOFF = date(2026, 8, 24)
SEX_2_DIAS_UTEIS_ANTES = date(2026, 8, 21)
TER_5_DIAS_UTEIS_ANTES = date(2026, 8, 18)  # limite exato pro padrão de 5 dias
SEG_6_DIAS_UTEIS_ANTES = date(2026, 8, 17)  # um dia útil além do limite
TER_DEPOIS_DO_KICKOFF = date(2026, 8, 25)

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
BRUNO = SimpleNamespace(id=11, nome="Bruno Lima", posicao="coordenador")
CAIO = SimpleNamespace(id=12, nome="Caio Reis", posicao="consultor")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


@pytest.fixture
def corrigir(monkeypatch):
    """`(executar, estado)` — `estado.gravado` mostra o que foi para o banco."""

    def _montar(*, kickoff=SEG_KICKOFF, dias_ambientacao=5, inicio_atual=None):
        estado = SimpleNamespace(gravado={}, encerrar_chamado_para=[])
        projeto = SimpleNamespace(
            id=3,
            status="ambientacao",
            data_kickoff=kickoff,
            dias_ambientacao=dias_ambientacao,
            data_inicio_ambientacao=inicio_atual,
        )

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return projeto
            def update(self, _id, **campos):
                estado.gravado.update(campos)
                for k, v in campos.items():
                    setattr(projeto, k, v)
                return projeto

        class MembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id, apenas_atuais=False):
                return [
                    SimpleNamespace(usuario_id=ANA.id, papel="coordenador"),
                    SimpleNamespace(usuario_id=CAIO.id, papel="consultor"),
                ]

        class DiaNaoLetivoFake:
            def __init__(self, db): pass
            def get_por_intervalo(self, _inicio, _fim): return []

        class EncerrarFake:
            def __init__(self, db): pass
            def executar_para(self, projeto_id):
                estado.encerrar_chamado_para.append(projeto_id)
                return False

        for nome, fake in [
            ("ProjetoRepository", ProjetoFake),
            ("ProjetoMembroRepository", MembroFake),
            ("DiaNaoLetivoRepository", DiaNaoLetivoFake),
            ("EncerrarAmbientacaoUseCase", EncerrarFake),
        ]:
            monkeypatch.setattr(update_inicio_ambientacao, nome, fake)

        uc = UpdateInicioAmbientacaoUseCase(db=None)

        def executar(nova_data, quem=ANA):
            return uc.execute(
                projeto.id,
                UpdateInicioAmbientacaoRequest(data_inicio_ambientacao=nova_data),
                quem,
                eh_diretor_projetos=quem.posicao == "diretor_projetos",
            )

        return executar, estado

    return _montar


class TestQuemPodeCorrigir:
    """Vínculo com o projeto, não posição no organograma."""

    def test_o_coordenador_do_projeto_corrige(self, corrigir):
        executar, estado = corrigir()

        resposta = executar(SEX_2_DIAS_UTEIS_ANTES, ANA)

        assert estado.gravado["data_inicio_ambientacao"] == SEX_2_DIAS_UTEIS_ANTES
        assert resposta["data_inicio_ambientacao"] == SEX_2_DIAS_UTEIS_ANTES

    def test_a_diretoria_corrige_sem_estar_no_projeto(self, corrigir):
        executar, estado = corrigir()

        executar(SEX_2_DIAS_UTEIS_ANTES, DANI)

        assert estado.gravado["data_inicio_ambientacao"] == SEX_2_DIAS_UTEIS_ANTES

    def test_coordenador_de_outro_projeto_nao_corrige(self, corrigir):
        executar, estado = corrigir()

        with pytest.raises(RegraDeNegocioError, match="coordenador do projeto"):
            executar(SEX_2_DIAS_UTEIS_ANTES, BRUNO)

        assert estado.gravado == {}

    def test_consultor_do_projeto_nao_corrige(self, corrigir):
        executar, _ = corrigir()

        with pytest.raises(RegraDeNegocioError, match="coordenador do projeto"):
            executar(SEX_2_DIAS_UTEIS_ANTES, CAIO)


class TestLimiteDeAntecipacao:
    """§5.3: só pra ANTES do kickoff, no máximo `dias_ambientacao` dias úteis."""

    def test_sem_kickoff_nao_corrige(self, corrigir):
        executar, estado = corrigir(kickoff=None)

        with pytest.raises(RegraDeNegocioError, match="Marque o kickoff"):
            executar(SEX_2_DIAS_UTEIS_ANTES)

        assert estado.gravado == {}

    def test_nao_pode_ficar_depois_do_kickoff(self, corrigir):
        executar, estado = corrigir()

        with pytest.raises(RegraDeNegocioError, match="antecipado"):
            executar(TER_DEPOIS_DO_KICKOFF)

        assert estado.gravado == {}

    def test_no_limite_exato_aceita(self, corrigir):
        """5 dias úteis antes, com `dias_ambientacao=5` (padrão): o kickoff
        cai exatamente no 5º dia da janela — ainda dentro dela."""
        executar, estado = corrigir(dias_ambientacao=5)

        executar(TER_5_DIAS_UTEIS_ANTES)

        assert estado.gravado["data_inicio_ambientacao"] == TER_5_DIAS_UTEIS_ANTES

    def test_um_dia_util_alem_do_limite_rejeita(self, corrigir):
        executar, estado = corrigir(dias_ambientacao=5)

        with pytest.raises(RegraDeNegocioError, match="5 dias úteis antes"):
            executar(SEG_6_DIAS_UTEIS_ANTES)

        assert estado.gravado == {}

    def test_fim_de_semana_no_meio_nao_conta(self, corrigir):
        """⭐ A prova de que o limite é em dias ÚTEIS: sexta -> segunda são só
        2 dias úteis, embora sejam 3 dias corridos."""
        executar, estado = corrigir(dias_ambientacao=2)

        executar(SEX_2_DIAS_UTEIS_ANTES)

        assert estado.gravado["data_inicio_ambientacao"] == SEX_2_DIAS_UTEIS_ANTES

    def test_limite_acompanha_dias_ambientacao_customizado(self, corrigir):
        """O teto não é um "5" fixo — é `dias_ambientacao` do projeto. Com 2,
        o que valia (5 dias úteis antes) passa a estourar."""
        executar, estado = corrigir(dias_ambientacao=2)

        with pytest.raises(RegraDeNegocioError, match="2 dias úteis antes"):
            executar(TER_5_DIAS_UTEIS_ANTES)

        assert estado.gravado == {}


class TestLimparACorrecao:
    def test_none_reseta_para_o_padrao(self, corrigir):
        """Manda `None` de propósito: o início volta a ser o próprio
        kickoff, sem precisar apagar linha nenhuma."""
        executar, estado = corrigir(inicio_atual=SEX_2_DIAS_UTEIS_ANTES)

        resposta = executar(None)

        assert estado.gravado["data_inicio_ambientacao"] is None
        assert resposta["data_inicio_ambientacao"] is None

    def test_reset_nao_passa_pela_validacao_de_data(self, corrigir):
        """`None` não é "uma data depois do kickoff" — não deve estourar a
        validação de ordem."""
        executar, estado = corrigir(kickoff=None, inicio_atual=None)

        executar(None)

        assert estado.gravado["data_inicio_ambientacao"] is None


class TestProjetoInexistente:
    def test_devolve_none(self, corrigir, monkeypatch):
        executar, _ = corrigir()

        class ProjetoVazioFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None

        monkeypatch.setattr(update_inicio_ambientacao, "ProjetoRepository", ProjetoVazioFake)

        uc = UpdateInicioAmbientacaoUseCase(db=None)
        resultado = uc.execute(
            999,
            UpdateInicioAmbientacaoRequest(data_inicio_ambientacao=SEX_2_DIAS_UTEIS_ANTES),
            ANA,
        )

        assert resultado is None

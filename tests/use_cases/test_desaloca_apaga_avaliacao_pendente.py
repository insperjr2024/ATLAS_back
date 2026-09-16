"""2026-09-15, a pedido — diretoria/gestão de membros pode adicionar ou tirar
gente de uma banca já REALIZADA (corrigir a ficha depois do fato: quem foi
escalado por engano, trocar um avaliador), e tirar alguém apaga a avaliação
que essa pessoa fez daquela banca — ela não sobrevive à candidatura que a
gerou, senão o voto de quem já não é mais avaliador continuaria contando.

Sem `eh_gestao`, o bloqueio de banca realizada continua valendo pra todo
mundo, como sempre (ver `test_desalocar_banca_trava_7_dias.py`).
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_frente_model import BancaFrenteModel
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.models.configuracao_model import ConfiguracaoModel
from src.models.equipe_projeto_model import EquipeProjetoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.solicitacao_troca_model import SolicitacaoTrocaModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.candidatura.create_candidatura import (
    CreateCandidaturaRequest,
    CreateCandidaturaUseCase,
)
from src.use_cases.candidatura.update_candidatura import DeleteCandidaturaUseCase
from src.utils.exceptions import RegraDeNegocioError

TABELAS = [
    UsuarioModel.__table__,
    BancaModel.__table__,
    CandidaturaModel.__table__,
    BancaFrenteModel.__table__,
    SolicitacaoTrocaModel.__table__,
    AvaliacaoModel.__table__,
    BancaEscopoModel.__table__,
    ConfiguracaoModel.__table__,
    EquipeProjetoModel.__table__,
    FrenteModel.__table__,
    ProjetoEscopoModel.__table__,
    ProjetoMembroModel.__table__,
]

AGORA_UTC = datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABELAS)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def _banca_realizada(db, *, piso=1):
    b = BancaModel(
        nome_projeto="Alfa",
        coordenador_id=1,
        data_hora=AGORA_UTC - timedelta(days=1),
        realizado_em=AGORA_UTC - timedelta(days=1),
        piso_minimo_override=piso,
    )
    db.add(b)
    db.flush()
    return b


def _candidatura(db, banca, usuario_id):
    c = CandidaturaModel(banca_id=banca.id, usuario_id=usuario_id, criado_em=AGORA_UTC, confirmado=False)
    db.add(c)
    db.commit()
    return c


def _avaliacao(db, banca, avaliador_id, status="submetida"):
    a = AvaliacaoModel(banca_id=banca.id, avaliador_id=avaliador_id, formulario_id=1, status=status)
    db.add(a)
    db.commit()
    return a


class TestRemoverDeBancaRealizada:
    def test_sem_gestao_continua_barrado(self, db):
        banca = _banca_realizada(db)
        candidatura = _candidatura(db, banca, usuario_id=7)

        with pytest.raises(RegraDeNegocioError, match="já foi realizada"):
            DeleteCandidaturaUseCase(db).execute(candidatura.id, eh_gestao=False)

    def test_com_gestao_remove_e_apaga_a_avaliacao_da_pessoa(self, db):
        banca = _banca_realizada(db)
        candidatura = _candidatura(db, banca, usuario_id=7)
        avaliacao = _avaliacao(db, banca, avaliador_id=7)
        # Avaliação de OUTRA pessoa na mesma banca não pode ser tocada.
        avaliacao_de_outra_pessoa = _avaliacao(db, banca, avaliador_id=8)

        assert DeleteCandidaturaUseCase(db).execute(candidatura.id, eh_gestao=True) is True

        from src.repositories.avaliacao_repository import AvaliacaoRepository

        repo = AvaliacaoRepository(db)
        assert repo.get_by_id(avaliacao.id) is None
        assert repo.get_by_id(avaliacao_de_outra_pessoa.id) is not None

    def test_com_gestao_sem_avaliacao_nenhuma_remove_normal(self, db):
        banca = _banca_realizada(db)
        candidatura = _candidatura(db, banca, usuario_id=7)

        assert DeleteCandidaturaUseCase(db).execute(candidatura.id, eh_gestao=True) is True


class TestAdicionarEmBancaRealizada:
    def test_sem_gestao_continua_barrado(self, db):
        banca = _banca_realizada(db)
        request = CreateCandidaturaRequest(banca_id=banca.id)

        with pytest.raises(RegraDeNegocioError, match="já foi realizada"):
            CreateCandidaturaUseCase(db).execute(request, usuario_id=7, eh_gestao=False)

    def test_com_gestao_consegue_adicionar(self, db):
        banca = _banca_realizada(db, piso=0)
        request = CreateCandidaturaRequest(banca_id=banca.id)

        resultado = CreateCandidaturaUseCase(db).execute(request, usuario_id=7, eh_gestao=True)

        assert resultado["usuario_id"] == 7

    def test_gestao_nao_libera_banca_cancelada(self, db):
        """O passe livre é só pra 'já realizada' — cancelada continua travada
        pra todo mundo, gestão incluída: não tem candidatura em banca que não
        vai acontecer."""
        banca = _banca_realizada(db)
        banca.cancelada_em = AGORA_UTC
        db.commit()
        request = CreateCandidaturaRequest(banca_id=banca.id)

        with pytest.raises(RegraDeNegocioError, match="cancelada"):
            CreateCandidaturaUseCase(db).execute(request, usuario_id=7, eh_gestao=True)

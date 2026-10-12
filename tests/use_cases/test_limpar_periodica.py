"""Limpeza das respostas de periódica fora da regra de escopo em andamento
(2026-10-12). O que importa: sai só o que a regra proíbe, nunca resposta
que valia, e finalização não é tocada."""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database.database import Base
from src.models.desempenho_avaliacao_model import DesempenhoAvaliacaoModel
from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.models.desempenho_lote_projeto_model import DesempenhoLoteProjetoModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.desempenho_avaliacao.limpar_periodica import LimparAvaliacoesForaDaPeriodicaUseCase

BUSINESS, TECH = 1, 3
CONEXOES = 10
ANA, BIA, ANDRE, SAIU = 1, 2, 3, 4


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    tabelas = [m.__table__ for m in (UsuarioModel, UsuarioFrenteModel, ProjetoMembroModel, ProjetoEscopoModel, DesempenhoLoteModel, DesempenhoLoteProjetoModel, DesempenhoAvaliacaoModel)]
    Base.metadata.create_all(engine, tables=tabelas)
    s = sessionmaker(bind=engine)()
    for uid, nome in ((ANA, "Ana"), (BIA, "Bia"), (ANDRE, "André"), (SAIU, "Saiu")):
        s.add(UsuarioModel(id=uid, nome=nome, email_insper=f"{uid}@x.com", senha_hash="x", posicao="consultor"))
    for uid, frente in ((ANA, BUSINESS), (BIA, TECH), (ANDRE, BUSINESS), (ANDRE, TECH), (SAIU, BUSINESS)):
        s.add(UsuarioFrenteModel(usuario_id=uid, frente_id=frente))
    for uid in (ANA, BIA, ANDRE):
        s.add(ProjetoMembroModel(projeto_id=CONEXOES, usuario_id=uid, papel="consultor", entrou_em=date(2026, 8, 1)))
    # Saiu do projeto depois do lote: a resposta dela continua valendo.
    s.add(ProjetoMembroModel(projeto_id=CONEXOES, usuario_id=SAIU, papel="consultor", entrou_em=date(2026, 8, 1), saiu_em=date(2026, 10, 20)))
    s.add(ProjetoEscopoModel(id=100, projeto_id=CONEXOES, frente_id=BUSINESS, dias_uteis_vendidos=30, status="em_andamento", data_inicio=date(2026, 9, 1)))
    s.add(ProjetoEscopoModel(id=101, projeto_id=CONEXOES, frente_id=TECH, dias_uteis_vendidos=20, status="nao_iniciado"))
    s.add(DesempenhoLoteModel(id=1, nome="Periódica", tipo="periodico", data_inicio=datetime(2026, 10, 12), data_fim=datetime(2026, 10, 19)))
    s.add(DesempenhoLoteModel(id=2, nome="Finalização", tipo="finalizacao", data_inicio=datetime(2026, 10, 12), data_fim=datetime(2026, 10, 14)))
    for lote_id in (1, 2):
        s.add(DesempenhoLoteProjetoModel(lote_id=lote_id, projeto_id=CONEXOES))
    s.commit()
    yield s
    s.close()


def avaliacao(db, id, lote, de, para, escopo=None):
    db.add(DesempenhoAvaliacaoModel(id=id, lote_id=lote, formulario_id=1, avaliador_id=de, avaliado_id=para, projeto_escopo_id=escopo, nota_geral=5, comentarios=""))
    db.commit()


def restantes(db):
    return {a.id for a in db.query(DesempenhoAvaliacaoModel).all()}


def test_sai_quem_envolve_tech_e_fica_o_resto(db):
    avaliacao(db, 1, 1, ANA, ANDRE)  # Business <-> Business+Tech: fica
    avaliacao(db, 2, 1, ANA, BIA)  # avalia quem é só de Tech: sai
    avaliacao(db, 3, 1, BIA, ANA)  # quem é só de Tech avalia: sai
    avaliacao(db, 4, 1, ANDRE, BIA)  # André avaliando Tech: sai
    avaliacao(db, 5, 1, SAIU, ANA)  # saiu da equipe depois: fica

    relatorio = LimparAvaliacoesForaDaPeriodicaUseCase(db).execute(aplicar=True)

    assert {r["avaliacao_id"] for r in relatorio} == {2, 3, 4}
    assert restantes(db) == {1, 5}


def test_avaliacao_do_escopo_parado_sai(db):
    avaliacao(db, 10, 1, ANA, ANA, escopo=100)
    avaliacao(db, 11, 1, ANDRE, ANDRE, escopo=101)
    avaliacao(db, 12, 1, ANDRE, ANDRE)  # antiga, sem escopo gravado: fica

    LimparAvaliacoesForaDaPeriodicaUseCase(db).execute(aplicar=True)

    assert restantes(db) == {10, 12}


def test_finalizacao_nao_e_tocada(db):
    avaliacao(db, 20, 2, ANA, BIA)

    assert LimparAvaliacoesForaDaPeriodicaUseCase(db).execute(aplicar=True) == []
    assert restantes(db) == {20}


def test_sem_aplicar_so_lista(db):
    avaliacao(db, 2, 1, ANA, BIA)

    relatorio = LimparAvaliacoesForaDaPeriodicaUseCase(db).execute()

    assert [r["avaliacao_id"] for r in relatorio] == [2]
    assert restantes(db) == {2}

"""Uma tarefa com N responsáveis (`tarefa_responsavel`).

Antes era um `tarefa.responsavel_id` NOT NULL. Virou lista para atribuir a
várias pessoas ou a todos os consultores do projeto. Uma tarefa sempre tem
ao menos um responsável, garantido aqui, não por constraint.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.projeto_model import ProjetoModel
from src.models.tarefa_coluna_model import TarefaColunaModel
from src.models.tarefa_model import TarefaModel, TarefaResponsavelModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.tarefa.tarefas import (
    CreateTarefaRequest,
    CreateTarefaUseCase,
    ListTarefasUseCase,
    UpdateTarefaRequest,
    UpdateTarefaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

TABELAS = [
    ProjetoModel.__table__,
    UsuarioModel.__table__,
    TarefaColunaModel.__table__,
    TarefaModel.__table__,
    TarefaResponsavelModel.__table__,
]
PRAZO = date(2026, 10, 1)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABELAS)
    sessao = sessionmaker(bind=engine)()
    try:
        yield sessao
    finally:
        sessao.close()


@pytest.fixture
def base(db):
    projeto = ProjetoModel(
        nome="Alfa", cliente="C", criado_por=1, status="em_andamento", dias_ambientacao=5
    )
    db.add(projeto)
    db.flush()
    for i in (1, 2, 3):
        db.add(UsuarioModel(
            id=i, nome=f"P{i}", email_insper=f"p{i}@al.insper.edu.br",
            senha_hash="x", posicao="consultor", status="ativo", ativo=True,
        ))
    col = TarefaColunaModel(
        projeto_id=projeto.id, nome="A fazer", chave="a_fazer", cor="#ccc",
        ordem=0, encerra_tarefa=False,
    )
    db.add(col)
    db.commit()
    return {"projeto": projeto.id, "coluna": col.id}


def responsaveis(db, tarefa_id):
    return sorted(
        r.usuario_id
        for r in db.query(TarefaResponsavelModel).filter(
            TarefaResponsavelModel.tarefa_id == tarefa_id
        )
    )


class TestCriar:
    def test_grava_todos_os_responsaveis(self, db, base):
        r = CreateTarefaUseCase(db).execute(
            base["projeto"],
            CreateTarefaRequest(titulo="X", responsavel_ids=[1, 2, 3], prazo=PRAZO),
            criado_por=1,
        )
        assert sorted(r["responsavel_ids"]) == [1, 2, 3]
        assert responsaveis(db, r["id"]) == [1, 2, 3]

    def test_um_responsavel_so_tambem_vale(self, db, base):
        r = CreateTarefaUseCase(db).execute(
            base["projeto"],
            CreateTarefaRequest(titulo="X", responsavel_ids=[2], prazo=PRAZO),
            criado_por=1,
        )
        assert responsaveis(db, r["id"]) == [2]

    def test_lista_vazia_e_recusada(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="ao menos um responsável"):
            CreateTarefaUseCase(db).execute(
                base["projeto"],
                CreateTarefaRequest(titulo="X", responsavel_ids=[], prazo=PRAZO),
                criado_por=1,
            )

    def test_id_repetido_e_deduplicado(self, db, base):
        r = CreateTarefaUseCase(db).execute(
            base["projeto"],
            CreateTarefaRequest(titulo="X", responsavel_ids=[2, 2, 2], prazo=PRAZO),
            criado_por=1,
        )
        assert responsaveis(db, r["id"]) == [2]

    def test_usuario_inexistente_e_recusado(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="não encontrado"):
            CreateTarefaUseCase(db).execute(
                base["projeto"],
                CreateTarefaRequest(titulo="X", responsavel_ids=[1, 999], prazo=PRAZO),
                criado_por=1,
            )


class TestEditar:
    def _cria(self, db, base, ids):
        return CreateTarefaUseCase(db).execute(
            base["projeto"],
            CreateTarefaRequest(titulo="X", responsavel_ids=ids, prazo=PRAZO),
            criado_por=1,
        )["id"]

    def test_troca_a_lista_inteira(self, db, base):
        tid = self._cria(db, base, [1, 2])
        r = UpdateTarefaUseCase(db).execute(tid, UpdateTarefaRequest(responsavel_ids=[3]))
        assert r["responsavel_ids"] == [3]
        assert responsaveis(db, tid) == [3]

    def test_editar_so_o_titulo_nao_mexe_nos_responsaveis(self, db, base):
        tid = self._cria(db, base, [1, 2])
        UpdateTarefaUseCase(db).execute(tid, UpdateTarefaRequest(titulo="Y"))
        assert responsaveis(db, tid) == [1, 2]

    def test_esvaziar_a_lista_e_recusado(self, db, base):
        tid = self._cria(db, base, [1, 2])
        with pytest.raises(RegraDeNegocioError, match="ao menos um responsável"):
            UpdateTarefaUseCase(db).execute(tid, UpdateTarefaRequest(responsavel_ids=[]))


class TestListar:
    def test_cada_tarefa_traz_a_propria_lista(self, db, base):
        a = CreateTarefaUseCase(db).execute(
            base["projeto"],
            CreateTarefaRequest(titulo="A", responsavel_ids=[1, 2], prazo=PRAZO),
            criado_por=1,
        )["id"]
        b = CreateTarefaUseCase(db).execute(
            base["projeto"],
            CreateTarefaRequest(titulo="B", responsavel_ids=[3], prazo=PRAZO),
            criado_por=1,
        )["id"]
        por_id = {t["id"]: t["responsavel_ids"] for t in ListTarefasUseCase(db).execute(base["projeto"])}
        assert sorted(por_id[a]) == [1, 2]
        assert por_id[b] == [3]

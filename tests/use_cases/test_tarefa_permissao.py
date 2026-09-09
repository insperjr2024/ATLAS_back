"""§6.4, 2026-09-09 — quem edita, exclui e move tarefa no kanban.

- editar CONTEÚDO (título, responsáveis, prazo) e EXCLUIR: só a coordenação
  do projeto (`projeto_membro.papel == "coordenador"`) e a diretoria de
  projetos. O consultor não mexe — nem no que ele mesmo criou.
- MOVER: coordenação e diretoria movem qualquer tarefa; o consultor move só
  as em que está como responsável.
"""

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.tarefa_coluna_model import TarefaColunaModel
from src.models.tarefa_model import TarefaModel, TarefaResponsavelModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.tarefa.comentarios import (
    exigir_permissao_de_edicao,
    pode_editar_tarefa,
    pode_mover_tarefa,
)
from src.use_cases.tarefa.tarefas import (
    CreateTarefaRequest,
    CreateTarefaUseCase,
    UpdateTarefaRequest,
    UpdateTarefaUseCase,
)
from src.utils.exceptions import CODIGO_TAREFA_SEM_PERMISSAO, RegraDeNegocioError

TABELAS = [
    ProjetoModel.__table__,
    UsuarioModel.__table__,
    ProjetoMembroModel.__table__,
    TarefaColunaModel.__table__,
    TarefaModel.__table__,
    TarefaResponsavelModel.__table__,
]

# ids: 1 = coordenador do projeto, 2 e 3 = consultores, 9 = diretor de projetos
COORD, CONS_A, CONS_B, DIRETOR = 1, 2, 3, 9


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
def cenario(db):
    projeto = ProjetoModel(
        nome="Alfa", cliente="C", criado_por=COORD, status="em_andamento",
        dias_ambientacao=5,
    )
    db.add(projeto)
    db.flush()
    for i, pos in ((COORD, "coordenador"), (CONS_A, "consultor"), (CONS_B, "consultor"), (DIRETOR, "diretor_projetos")):
        db.add(UsuarioModel(
            id=i, nome=f"U{i}", email_insper=f"u{i}@al.insper.edu.br",
            senha_hash="x", posicao=pos, status="ativo", ativo=True,
        ))
    for uid, papel in ((COORD, "coordenador"), (CONS_A, "consultor"), (CONS_B, "consultor")):
        db.add(ProjetoMembroModel(
            projeto_id=projeto.id, usuario_id=uid, papel=papel, entrou_em=date(2026, 1, 1),
        ))
    col = TarefaColunaModel(
        projeto_id=projeto.id, nome="A fazer", chave="a_fazer", cor="#ccc",
        ordem=0, encerra_tarefa=False,
    )
    col2 = TarefaColunaModel(
        projeto_id=projeto.id, nome="Fazendo", chave="fazendo", cor="#ccc",
        ordem=1, encerra_tarefa=False,
    )
    db.add_all([col, col2])
    db.commit()
    return {"projeto": projeto.id, "col": col.id, "col2": col2.id}


def _user(uid):
    pos = {COORD: "coordenador", CONS_A: "consultor", CONS_B: "consultor", DIRETOR: "diretor_projetos"}[uid]
    return SimpleNamespace(id=uid, posicao=pos)


def _tarefa(db, cenario, responsavel_ids):
    r = CreateTarefaUseCase(db).execute(
        cenario["projeto"],
        CreateTarefaRequest(
            titulo="T",
            coluna_id=cenario["col"],
            responsavel_ids=responsavel_ids,
            prazo=date(2026, 10, 1),
        ),
        criado_por=CONS_A,
    )
    return r[0]["id"]


class TestEditarEExcluir:
    def test_consultor_nao_edita_nem_o_que_criou(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        with pytest.raises(RegraDeNegocioError) as exc:
            UpdateTarefaUseCase(db).execute(
                tid, UpdateTarefaRequest(titulo="novo"), _user(CONS_A)
            )
        assert exc.value.codigo == CODIGO_TAREFA_SEM_PERMISSAO

    def test_coordenador_do_projeto_edita(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        r = UpdateTarefaUseCase(db).execute(
            tid, UpdateTarefaRequest(titulo="novo"), _user(COORD)
        )
        assert r["titulo"] == "novo"

    def test_diretor_de_projetos_edita(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        r = UpdateTarefaUseCase(db).execute(
            tid, UpdateTarefaRequest(titulo="dir"), _user(DIRETOR)
        )
        assert r["titulo"] == "dir"

    def test_helper_de_exclusao(self, db, cenario):
        tarefa = SimpleNamespace(projeto_id=cenario["projeto"], criado_por=CONS_A)
        assert pode_editar_tarefa(tarefa, _user(COORD), db) is True
        assert pode_editar_tarefa(tarefa, _user(DIRETOR), db) is True
        assert pode_editar_tarefa(tarefa, _user(CONS_A), db) is False
        with pytest.raises(RegraDeNegocioError):
            exigir_permissao_de_edicao(tarefa, _user(CONS_B), db)


class TestMover:
    def test_consultor_move_a_que_e_responsavel(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        r = UpdateTarefaUseCase(db).execute(
            tid, UpdateTarefaRequest(coluna_id=cenario["col2"]), _user(CONS_A)
        )
        assert r["coluna_id"] == cenario["col2"]

    def test_consultor_nao_move_a_que_nao_e_responsavel(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        with pytest.raises(RegraDeNegocioError) as exc:
            UpdateTarefaUseCase(db).execute(
                tid, UpdateTarefaRequest(coluna_id=cenario["col2"]), _user(CONS_B)
            )
        assert exc.value.codigo == CODIGO_TAREFA_SEM_PERMISSAO

    def test_coordenador_move_qualquer_uma(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        r = UpdateTarefaUseCase(db).execute(
            tid, UpdateTarefaRequest(coluna_id=cenario["col2"]), _user(COORD)
        )
        assert r["coluna_id"] == cenario["col2"]

    def test_helper_pode_mover(self, db, cenario):
        tarefa = SimpleNamespace(projeto_id=cenario["projeto"], criado_por=CONS_A)
        assert pode_mover_tarefa(tarefa, _user(CONS_A), db, [CONS_A]) is True
        assert pode_mover_tarefa(tarefa, _user(CONS_A), db, [CONS_B]) is False
        assert pode_mover_tarefa(tarefa, _user(COORD), db, [CONS_B]) is True

    def test_chamada_interna_sem_usuario_nao_checa(self, db, cenario):
        tid = _tarefa(db, cenario, [CONS_A])
        r = UpdateTarefaUseCase(db).execute(
            tid, UpdateTarefaRequest(coluna_id=cenario["col2"])
        )
        assert r["coluna_id"] == cenario["col2"]

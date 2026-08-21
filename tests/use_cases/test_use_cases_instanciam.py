"""Todo use case tem de conseguir NASCER.

⭐ **Por que este arquivo existe.** Em 2026-08-20 o `GET /bancas` passou a
devolver 500 em produção: `ListBancasUseCase` usava
`self.vendedor_repository` e nunca o definia. `get_banca.py` tem duas classes,
as duas chamam `membros_da_banca`, e a dependência nova foi acrescentada só no
`__init__` de uma delas.

As 829 provas da suíte não pegaram, e não é descuido delas: elas trocam os
repositórios por dublês e montam os use cases com `__new__`, justamente para
não precisar de banco. Nenhuma executa o `__init__` de verdade — que é onde o
defeito morava.

Esta prova cobre só isso: percorre os use cases e instancia cada um. Não
valida comportamento nenhum. `AttributeError`, import faltando ou repositório
inexistente aparecem aqui, e não na tela de alguém.
"""

import importlib
import inspect
import pkgutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.use_cases


def _use_cases():
    """Toda classe `*UseCase` sob `src/use_cases`, com `__init__(self, db)`."""
    achados = []
    for info in pkgutil.walk_packages(src.use_cases.__path__, "src.use_cases."):
        modulo = importlib.import_module(info.name)
        for nome, classe in inspect.getmembers(modulo, inspect.isclass):
            if not nome.endswith("UseCase") or classe.__module__ != info.name:
                continue
            parametros = list(inspect.signature(classe.__init__).parameters)
            # `(self, db)` e nada mais: quem pede outra coisa não é construído
            # pelas rotas do jeito padrão e sai daqui.
            if parametros[:2] == ["self", "db"] and len(parametros) == 2:
                achados.append(pytest.param(classe, id=f"{info.name.split('.')[-1]}.{nome}"))
    return achados


@pytest.fixture(scope="module")
def db():
    """SQLite em memória. Nenhuma tabela é criada de propósito: o `__init__`
    dos repositórios só guarda a sessão, não consulta nada."""
    engine = create_engine("sqlite://")
    sessao = sessionmaker(bind=engine)()
    yield sessao
    sessao.close()


@pytest.mark.parametrize("classe", _use_cases())
def test_use_case_instancia(classe, db):
    classe(db)


def test_a_varredura_achou_use_cases():
    """Se um refactor mudar o nome ou o lugar dos use cases, a lista pode
    esvaziar e esta prova passaria sem provar nada."""
    assert len(_use_cases()) > 50

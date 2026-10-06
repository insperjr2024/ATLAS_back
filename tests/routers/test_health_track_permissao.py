"""Quem preenche o Health Track: diretoria de projetos e gerente de uma
frente do projeto.

**O caso que já deu errado em outras telas:** num projeto sinérgico, a
frente de uma pessoa era deduzida dos projetos em que ela estava, e todo
mundo do projeto passava a contar como de todas as frentes dele. Aqui a
frente do gerente vem só de `usuario_frente`; estar no projeto, ter vendido
ou enxergá-lo não conta.
"""

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401 — registra todos os models no metadata
from src.database.database import Base
from src.middlewares.authorization import (
    exigir_pode_preencher_health_track,
    gerencia_frente_do_projeto,
)
from src.models.posicao_permissao_model import PosicaoPermissaoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_vendedor_model import ProjetoVendedorModel
from src.models.usuario_frente_model import UsuarioFrenteModel

FRENTE_A, FRENTE_B, FRENTE_C = 1, 2, 3
SO_DA_A, SINERGICO_AB, SO_DA_C = 100, 200, 300
ENTROU = date(2026, 9, 1)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            PosicaoPermissaoModel.__table__,
            ProjetoModel.__table__,
            ProjetoFrenteModel.__table__,
            ProjetoMembroModel.__table__,
            ProjetoVendedorModel.__table__,
            UsuarioFrenteModel.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    for projeto_id, frentes in ((SO_DA_A, [FRENTE_A]), (SINERGICO_AB, [FRENTE_A, FRENTE_B]), (SO_DA_C, [FRENTE_C])):
        s.add(ProjetoModel(id=projeto_id, nome=f"Projeto {projeto_id}"))
        for frente in frentes:
            s.add(ProjetoFrenteModel(projeto_id=projeto_id, frente_id=frente))
    s.commit()
    try:
        yield s
    finally:
        s.close()


def pessoa(db, posicao, *, id=7, frentes=()):
    for frente in frentes:
        db.add(UsuarioFrenteModel(usuario_id=id, frente_id=frente))
    db.commit()
    return SimpleNamespace(id=id, posicao=posicao, cargo_extra=None)


def preenche(projeto_id, quem, db) -> int:
    """200 se pode, senão o status da recusa."""
    try:
        exigir_pode_preencher_health_track(projeto_id, quem, db)
        return 200
    except HTTPException as e:
        return e.status_code


class TestGerente:
    def test_preenche_projeto_da_propria_frente(self, db):
        assert preenche(SO_DA_A, pessoa(db, "gerente", frentes=[FRENTE_A]), db) == 200

    def test_preenche_sinergico_que_envolve_a_frente_dele(self, db):
        """Gerente da B entra no sinérgico A+B: é um dos gerentes dele."""
        assert preenche(SINERGICO_AB, pessoa(db, "gerente", frentes=[FRENTE_B]), db) == 200

    def test_projeto_de_outra_frente_nem_aparece(self, db):
        """404, não 403: quem não enxerga o projeto não sabe que ele existe."""
        assert preenche(SO_DA_C, pessoa(db, "gerente", frentes=[FRENTE_A]), db) == 404

    def test_estar_no_sinergico_nao_da_as_outras_frentes(self, db):
        """O bug de antes: o gerente da B, por estar no sinérgico A+B, não
        vira gerente da A — o projeto só da A continua fora."""
        gerente_b = pessoa(db, "gerente", frentes=[FRENTE_B])
        db.add(ProjetoMembroModel(projeto_id=SINERGICO_AB, usuario_id=gerente_b.id, papel="coordenador", entrou_em=ENTROU))
        db.commit()

        assert gerencia_frente_do_projeto(SO_DA_A, gerente_b, db) is False
        assert preenche(SO_DA_A, gerente_b, db) == 404

    def test_estar_na_equipe_de_projeto_de_outra_frente_nao_basta(self, db):
        """Para o gerente, o recorte de visão é só por frente (e venda): estar
        na equipe de um projeto de outra frente nem o faz aparecer."""
        gerente_a = pessoa(db, "gerente", frentes=[FRENTE_A])
        db.add(ProjetoMembroModel(projeto_id=SO_DA_C, usuario_id=gerente_a.id, papel="coordenador", entrou_em=ENTROU))
        db.commit()

        assert preenche(SO_DA_C, gerente_a, db) == 404

    def test_ter_vendido_projeto_de_outra_frente_nao_basta(self, db):
        """Vender dá visão (somente leitura), não o preenchimento."""
        gerente_a = pessoa(db, "gerente", frentes=[FRENTE_A])
        db.add(ProjetoVendedorModel(projeto_id=SO_DA_C, usuario_id=gerente_a.id))
        db.commit()

        assert preenche(SO_DA_C, gerente_a, db) == 403

    def test_gerente_sem_frente_nao_preenche_nada(self, db):
        assert preenche(SO_DA_A, pessoa(db, "gerente"), db) == 404


class TestOutrasPosicoes:
    def test_diretoria_de_projetos_preenche_qualquer_um(self, db):
        diretor = pessoa(db, "diretor_projetos")
        assert [preenche(p, diretor, db) for p in (SO_DA_A, SINERGICO_AB, SO_DA_C)] == [200, 200, 200]

    @pytest.mark.parametrize("posicao", ["diretor", "diretor_pessoas"])
    def test_outros_cargos_da_diretoria_so_leem(self, db, posicao):
        assert preenche(SO_DA_A, pessoa(db, posicao), db) == 403

    @pytest.mark.parametrize("papel", ["coordenador", "consultor"])
    def test_equipe_do_projeto_nao_preenche(self, db, papel):
        membro = pessoa(db, papel, frentes=[FRENTE_A])
        db.add(ProjetoMembroModel(projeto_id=SO_DA_A, usuario_id=membro.id, papel=papel, entrou_em=ENTROU))
        db.commit()

        assert preenche(SO_DA_A, membro, db) == 403


class TestQuemEditaARegra:
    """A regra do status geral (§5): só a diretoria de projetos edita. É a
    mesma guarda das outras ações de condução de projeto."""

    def test_diretoria_de_projetos_edita(self):
        from src.middlewares.authorization import require_diretor_projetos

        diretor = SimpleNamespace(id=1, posicao="diretor_projetos")
        assert require_diretor_projetos(current_user=diretor) is diretor

    @pytest.mark.parametrize("posicao", ["diretor", "diretor_pessoas", "gerente", "coordenador", "consultor"])
    def test_ninguem_mais_edita(self, posicao):
        from src.middlewares.authorization import require_diretor_projetos

        with pytest.raises(HTTPException) as erro:
            require_diretor_projetos(current_user=SimpleNamespace(id=1, posicao=posicao))
        assert erro.value.status_code == 403

    def test_a_rota_de_edicao_usa_essa_guarda(self):
        """Sem isto, trocar a dependência na rota passaria batido pelos
        testes acima."""
        from src.middlewares.authorization import require_diretor_projetos
        from src.routers.health_track import router

        rota = next(r for r in router.routes if r.path == "/health-track/regra" and "PUT" in r.methods)
        assert require_diretor_projetos in [d.call for d in rota.dependant.dependencies]


class TestPodePreencherParaATela:
    """O `/atual` diz à tela se mostra o formulário — mesma regra do POST."""

    def test_mesma_resposta_que_a_guarda_de_escrita(self, db):
        from src.middlewares.authorization import pode_preencher_health_track

        gerente_a = pessoa(db, "gerente", frentes=[FRENTE_A])
        assert pode_preencher_health_track(SO_DA_A, gerente_a, db) is True
        assert pode_preencher_health_track(SINERGICO_AB, gerente_a, db) is True
        assert pode_preencher_health_track(SO_DA_C, gerente_a, db) is False
        assert pode_preencher_health_track(SO_DA_A, SimpleNamespace(id=9, posicao="diretor_projetos", cargo_extra=None), db) is True
        assert pode_preencher_health_track(SO_DA_A, SimpleNamespace(id=9, posicao="diretor", cargo_extra=None), db) is False

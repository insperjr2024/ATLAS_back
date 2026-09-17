"""Publicar uma nova versão do formulário de avaliação (2026-09-16).

⚠ **Editar tem que editar, sem duplicar.** Antes, publicar SEMPRE recriava
toda pergunta com id novo — mesmo a que não mudou nada. Uma correção de texto
(ex.: "Tangibilização das Recomendação" → "...Recomendações") ganhava outro
id, e quem já tinha respondido sob o id antigo (inclusive "Médias por
critério" de uma banca já realizada) continuava vendo o texto velho pra
sempre. Agora, quando o front manda o id de uma pergunta que já existia, o
mesmo registro é atualizado — `get_notas_por_pergunta.py` busca a pergunta
pelo id, então a correção aparece em toda banca que já a usou, passada ou
futura.

Usa banco de verdade (SQLite em memória): este use case faz suas próprias
queries de checagem de escopo, não só repositório trocável.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.escopo_model import EscopoModel
from src.models.formulario_model import FormularioModel
from src.models.pergunta_model import PerguntaModel
from src.models.semestre_model import SemestreModel
from src.use_cases.formulario.create_nova_versao_formulario import (
    CreateNovaVersaoFormularioRequest,
    CreateNovaVersaoFormularioUseCase,
    PerguntaNovaVersao,
)
from src.utils.exceptions import RegraDeNegocioError

TABELAS = [
    SemestreModel.__table__,
    FormularioModel.__table__,
    PerguntaModel.__table__,
    EscopoModel.__table__,
]


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
    semestre = SemestreModel(
        nome="2026.2", inicio=date(2020, 1, 1), fim=date(2030, 12, 31), status="ativa"
    )
    db.add(semestre)
    db.flush()

    formulario = FormularioModel(semestre_id=semestre.id, ativo=True)
    db.add(formulario)
    db.flush()

    pergunta = PerguntaModel(
        formulario_id=formulario.id,
        texto="Tangibilização das Recomendação",
        ordem=1,
        tipo_resposta="nota",
    )
    db.add(pergunta)
    db.flush()

    return {"db": db, "formulario": formulario, "pergunta": pergunta}


class TestReaproveitaOId:
    def test_corrigir_o_texto_atualiza_o_mesmo_registro(self, base):
        db, pergunta_id = base["db"], base["pergunta"].id

        resultado = CreateNovaVersaoFormularioUseCase(db).execute(
            CreateNovaVersaoFormularioRequest(
                perguntas=[
                    PerguntaNovaVersao(
                        id=pergunta_id,
                        texto="Tangibilização das Recomendações",
                        ordem=1,
                        tipo_resposta="nota",
                    )
                ]
            )
        )

        assert resultado["perguntas"][0]["id"] == pergunta_id

        pergunta_no_banco = db.get(PerguntaModel, pergunta_id)
        assert pergunta_no_banco.texto == "Tangibilização das Recomendações"
        # Migrou pro formulário novo — não ficou órfã no antigo, desativado.
        assert pergunta_no_banco.formulario_id == resultado["id"]
        # Uma linha só: não duplicou.
        assert db.query(PerguntaModel).count() == 1

    def test_sem_id_cria_pergunta_nova_de_verdade(self, base):
        db, pergunta_id = base["db"], base["pergunta"].id

        CreateNovaVersaoFormularioUseCase(db).execute(
            CreateNovaVersaoFormularioRequest(
                perguntas=[
                    PerguntaNovaVersao(texto="Storytelling", ordem=1, tipo_resposta="nota"),
                ]
            )
        )

        # A pergunta antiga continua no banco (histórico), a nova é outra
        # linha — não reaproveitou o id de propósito, porque não foi mandado.
        assert db.query(PerguntaModel).count() == 2
        antiga_ainda_existe = db.get(PerguntaModel, pergunta_id)
        assert antiga_ainda_existe is not None
        assert antiga_ainda_existe.texto == "Tangibilização das Recomendação"

    def test_id_que_nao_existe_mais_cai_pra_criar_nova(self, base):
        db = base["db"]

        resultado = CreateNovaVersaoFormularioUseCase(db).execute(
            CreateNovaVersaoFormularioRequest(
                perguntas=[
                    PerguntaNovaVersao(id=99999, texto="Pergunta nova", ordem=1),
                ]
            )
        )

        assert resultado["perguntas"][0]["id"] != 99999

    def test_texto_vazio_continua_recusado(self, base):
        db = base["db"]

        with pytest.raises(RegraDeNegocioError):
            CreateNovaVersaoFormularioUseCase(db).execute(
                CreateNovaVersaoFormularioRequest(perguntas=[])
            )

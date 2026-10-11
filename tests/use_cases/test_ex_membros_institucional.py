"""Institucional — ex-membros em destaque do site (2026-10-09).

O que importa aqui: a rota pública só devolve quem está publicado, só os
campos listados em `serializar_publico`, e na ordem; a reordenação exige a
lista inteira; a foto vira JPEG pequeno seja o que for que subiu.
"""

import io

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database.database import Base
from src.models.ex_membro_model import ExMembroModel
from src.models.usuario_model import UsuarioModel
from src.repositories.ex_membro_repository import ExMembroRepository
from src.use_cases.institucional.ex_membros import (
    ApagarExMembroUseCase,
    AtualizarFotoUseCase,
    CriarExMembroUseCase,
    EditarExMembroUseCase,
    ExMembroRequest,
    GetFotoUseCase,
    ImportarIniciaisUseCase,
    ListarPublicadosUseCase,
    ListarTodosUseCase,
    PublicarExMembroUseCase,
    ReordenarExMembrosUseCase,
    ReordenarRequest,
    normalizar_foto,
)
from src.utils.exceptions import RegraDeNegocioError

CAMPOS_PUBLICOS = {
    "id", "nome", "cargo_pt", "cargo_en", "area_pt", "area_en", "empresa", "empresa_en",
    "depoimento_pt", "depoimento_en", "linkedin", "ordem", "tem_foto", "foto_versao",
}


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[UsuarioModel.__table__, ExMembroModel.__table__])
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def pedido(nome, **extra):
    base = dict(nome=nome, cargo_pt="Analista", empresa="Empresa X")
    base.update(extra)
    return ExMembroRequest(**base)


def png(largura=1600, altura=1200, modo="RGBA"):
    buf = io.BytesIO()
    Image.new(modo, (largura, altura), (200, 30, 30, 255) if modo == "RGBA" else (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


class TestPublico:
    def test_so_publicados_na_ordem_e_so_campos_publicos(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana"), criado_por=None)
        b = CriarExMembroUseCase(db).execute(pedido("Bia", publicado=False), criado_por=None)
        c = CriarExMembroUseCase(db).execute(pedido("Caio"), criado_por=None)

        ReordenarExMembrosUseCase(db).execute(ReordenarRequest(ids=[c["id"], b["id"], a["id"]]))

        publico = ListarPublicadosUseCase(db).execute()
        assert [p["nome"] for p in publico] == ["Caio", "Ana"]
        assert set(publico[0]) == CAMPOS_PUBLICOS, "campo novo vazou (ou sumiu) da rota pública"
        assert "publicado" not in publico[0] and "criado_em" not in publico[0]

        admin = ListarTodosUseCase(db).execute()
        assert [p["nome"] for p in admin] == ["Caio", "Bia", "Ana"]
        assert admin[1]["publicado"] is False

    def test_ocultar_tira_do_site_sem_apagar(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana"), criado_por=None)
        PublicarExMembroUseCase(db).execute(a["id"], publicado=False)
        assert ListarPublicadosUseCase(db).execute() == []
        assert len(ListarTodosUseCase(db).execute()) == 1

    def test_foto_publica_nao_sai_de_quem_esta_oculto(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana", publicado=False), criado_por=None)
        AtualizarFotoUseCase(db).execute(a["id"], png())
        with pytest.raises(RegraDeNegocioError):
            GetFotoUseCase(db).execute(a["id"], apenas_publicado=True)
        assert GetFotoUseCase(db).execute(a["id"], apenas_publicado=False)[:2] == b"\xff\xd8"  # JPEG


class TestEscrita:
    def test_novo_entra_no_fim(self, db):
        CriarExMembroUseCase(db).execute(pedido("Ana"), criado_por=None)
        b = CriarExMembroUseCase(db).execute(pedido("Bia"), criado_por=None)
        assert b["ordem"] == 1

    def test_reordenar_exige_lista_inteira(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana"), criado_por=None)
        CriarExMembroUseCase(db).execute(pedido("Bia"), criado_por=None)
        with pytest.raises(RegraDeNegocioError):
            ReordenarExMembrosUseCase(db).execute(ReordenarRequest(ids=[a["id"]]))

    def test_linkedin_normalizado_e_validado(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana", linkedin="linkedin.com/in/ana"), criado_por=None)
        assert a["linkedin"] == "https://linkedin.com/in/ana"
        with pytest.raises(RegraDeNegocioError):
            EditarExMembroUseCase(db).execute(a["id"], pedido("Ana", linkedin="https://instagram.com/ana"))

    def test_campos_en_vazios_viram_nulos(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana", cargo_en="  ", depoimento_en=""), criado_por=None)
        assert a["cargo_en"] is None and a["depoimento_en"] is None

    def test_apagar(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana"), criado_por=None)
        ApagarExMembroUseCase(db).execute(a["id"])
        assert ListarTodosUseCase(db).execute() == []
        with pytest.raises(RegraDeNegocioError):
            ApagarExMembroUseCase(db).execute(a["id"])


class TestFoto:
    def test_png_grande_vira_jpeg_pequeno(self):
        saida = normalizar_foto(png(3000, 2000))
        imagem = Image.open(io.BytesIO(saida))
        assert imagem.format == "JPEG" and imagem.mode == "RGB"
        assert max(imagem.size) == 900

    def test_arquivo_que_nao_e_imagem(self):
        with pytest.raises(RegraDeNegocioError):
            normalizar_foto(b"isto nao e uma imagem")

    def test_trocar_foto_sobe_a_versao(self, db):
        a = CriarExMembroUseCase(db).execute(pedido("Ana"), criado_por=None)
        assert a["tem_foto"] is False and a["foto_versao"] == 0
        a = AtualizarFotoUseCase(db).execute(a["id"], png())
        assert a["tem_foto"] is True and a["foto_versao"] == 1


class TestImportacao:
    def test_importa_a_lista_inicial_e_nao_duplica(self, db):
        r = ImportarIniciaisUseCase(db).execute(criado_por=None)
        assert r == {"importados": 32, "atualizados": 0, "pulados": 0}
        todos = ListarTodosUseCase(db).execute()
        assert [t["nome"] for t in todos][:2] == ["Giovanna Fava Steinberg", "Fernando Mauad"]
        assert all(t["tem_foto"] for t in todos)
        assert all(t["cargo_pt"] and t["cargo_en"] and t["empresa"] for t in todos)

        # Os 13 do site entram publicados e com depoimento; os 19 do
        # formulário da 51ª entram OCULTOS e sem depoimento (a diretoria
        # revisa e publica pela aba).
        do_site, do_formulario = todos[:13], todos[13:]
        assert len(do_formulario) == 19
        assert all(t["publicado"] and t["depoimento_pt"] for t in do_site)
        assert all(not t["publicado"] and not t["depoimento_pt"] for t in do_formulario)
        assert len(ListarPublicadosUseCase(db).execute()) == 13

        r = ImportarIniciaisUseCase(db).execute(criado_por=None)
        assert r == {"importados": 0, "atualizados": 0, "pulados": 32}
        assert len(ListarTodosUseCase(db).execute()) == 32

    def test_reimportar_completa_linkedin_e_foto_de_quem_ja_existe_sem_sobrescrever(self, db):
        """Os 19 foram importados em produção antes de o lote ter os links:
        rodar de novo preenche o que está vazio e não mexe no que foi editado."""
        ImportarIniciaisUseCase(db).execute(criado_por=None)
        repo = ExMembroRepository(db)
        a = repo.buscar_por_nome("Clarice Barroso")
        b = repo.buscar_por_nome("Lucca Foguel")
        a.linkedin = None
        a.foto = None
        b.linkedin = "https://www.linkedin.com/in/editado-pela-diretoria/"
        b.cargo_pt = "Cargo editado"
        db.commit()

        r = ImportarIniciaisUseCase(db).execute(criado_por=None)
        assert r == {"importados": 0, "atualizados": 1, "pulados": 31}
        a = repo.buscar_por_nome("Clarice Barroso")
        b = repo.buscar_por_nome("Lucca Foguel")
        assert a.linkedin == "https://www.linkedin.com/in/claricebarroso/" and a.foto is not None
        assert b.linkedin == "https://www.linkedin.com/in/editado-pela-diretoria/" and b.cargo_pt == "Cargo editado"
        assert len(ListarTodosUseCase(db).execute()) == 32

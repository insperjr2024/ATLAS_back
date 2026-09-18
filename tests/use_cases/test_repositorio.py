from types import SimpleNamespace

from src.use_cases.documento_contratual.repositorio import ListarRepositorioContratualUseCase


class FakeDocumentoRepo:
    def __init__(self, documentos):
        self._documentos = documentos
        self.chamado_com = None

    def list_arquivados(self, gestao_id=None, busca=None):
        self.chamado_com = {"gestao_id": gestao_id, "busca": busca}
        return self._documentos


class FakeVersaoRepo:
    def __init__(self, versoes_por_documento):
        self._versoes = versoes_por_documento

    def ultima_versao_obj(self, documento_id):
        return self._versoes.get(documento_id)


class FakeSemestreRepo:
    def __init__(self, semestres):
        self._semestres = semestres

    def get_all(self):
        return self._semestres


def documento(id, tipo="contrato", gestao_id=5, projeto_id=7, projeto_nome="Alfa", cliente="Cliente X"):
    projeto = SimpleNamespace(nome=projeto_nome, cliente=cliente)
    return SimpleNamespace(id=id, tipo=tipo, gestao_id=gestao_id, projeto_id=projeto_id, projeto=projeto)


def montar(documentos, versoes=None, semestres=None):
    uc = ListarRepositorioContratualUseCase.__new__(ListarRepositorioContratualUseCase)
    uc.documentos = FakeDocumentoRepo(documentos)
    uc.versoes = FakeVersaoRepo(versoes or {})
    uc.semestres = FakeSemestreRepo(semestres or [])
    return uc


def test_monta_um_item_por_documento_com_rotulo_e_gestao():
    doc = documento(1)
    versao = SimpleNamespace(docx_path="/a.docx", pdf_path="/a.pdf", arquivado_em="2026-09-01")
    semestre = SimpleNamespace(id=5, nome="2026.2")
    uc = montar([doc], versoes={1: versao}, semestres=[semestre])

    itens = uc.execute()

    assert itens == [
        {
            "id": 1,
            "projeto_id": 7,
            "projeto_nome": "Alfa",
            "cliente": "Cliente X",
            "tipo": "contrato",
            "tipo_rotulo": "Contrato de Prestação de Serviços",
            "gestao_id": 5,
            "gestao_nome": "2026.2",
            "docx_path": "/a.docx",
            "pdf_path": "/a.pdf",
            "arquivado_em": "2026-09-01",
        }
    ]


def test_repassa_filtros_pro_repositorio():
    uc = montar([])

    uc.execute(gestao_id=3, busca="Alfa")

    assert uc.documentos.chamado_com == {"gestao_id": 3, "busca": "Alfa"}


def test_documento_sem_versao_nao_quebra():
    doc = documento(1, gestao_id=None)
    uc = montar([doc])

    itens = uc.execute()

    assert itens[0]["docx_path"] is None
    assert itens[0]["gestao_nome"] is None

"""O painel da aba Contratos: quem vê o que (§ Contratos, 2026-09-21).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório e as
funções de `authorization` trocadas no MÓDULO `painel`.
"""

from types import SimpleNamespace

import src.use_cases.documento_contratual.painel as mod
from src.use_cases.documento_contratual.painel import PainelContratualUseCase


def usuario(id, posicao="consultor"):
    return SimpleNamespace(id=id, posicao=posicao)


DIRETOR = usuario(1, "diretor_projetos")
JURIDICO = usuario(2)
VENDEDOR = usuario(3)
COORDENADOR = usuario(4)
NINGUEM = usuario(5)


def documento(id, projeto_id, tipo, nome_projeto="Projeto X"):
    projeto = SimpleNamespace(nome=nome_projeto, cliente="Cliente Y")
    return SimpleNamespace(id=id, projeto_id=projeto_id, tipo=tipo, status="em_revisao_interna",
                            confirmado=True, dados=None, criado_em=None, atualizado_em=None, projeto=projeto,
                            nome_projeto_externo=None, cliente_externo=None)


def documento_institucional(id, tipo, nome, cliente=None):
    return SimpleNamespace(id=id, projeto_id=None, tipo=tipo, status="em_revisao_interna",
                            confirmado=True, dados=None, criado_em=None, atualizado_em=None, projeto=None,
                            nome_projeto_externo=nome, cliente_externo=cliente)


def montar(monkeypatch, documentos, vendedores=(), membros=(), permissoes_juridico=(), permissoes_painel=()):
    class DocumentoFake:
        def __init__(self, db): pass
        def list_para_painel(self):
            return documentos

    class VersaoFake:
        def __init__(self, db): pass
        def ultima_versao(self, _id):
            return 1

    class VendedorFake:
        def __init__(self, db): pass
        def get_by_projetos(self, _projeto_ids):
            return vendedores

    class MembroFake:
        def __init__(self, db): pass
        def get_by_projetos(self, _projeto_ids, apenas_atuais=False):
            return membros

    class FrenteFake:
        def __init__(self, db): pass
        def get_by_projetos(self, _projeto_ids):
            return []

    monkeypatch.setattr(mod, "DocumentoContratualRepository", DocumentoFake)
    monkeypatch.setattr(mod, "DocumentoContratualVersaoRepository", VersaoFake)
    monkeypatch.setattr(mod, "ProjetoVendedorRepository", VendedorFake)
    monkeypatch.setattr(mod, "ProjetoMembroRepository", MembroFake)
    monkeypatch.setattr(mod, "ProjetoFrenteRepository", FrenteFake)
    monkeypatch.setattr(mod, "eh_diretoria_de_projetos", lambda u: u.posicao == "diretor_projetos")
    monkeypatch.setattr(
        mod,
        "usuario_tem_permissao",
        lambda u, db, campo: (
            (campo == "pode_editar_documento_juridico" and u.id in permissoes_juridico)
            or (campo == "pode_ver_painel_contratos" and u.id in permissoes_painel)
        ),
    )
    return PainelContratualUseCase(db=None)


class TestVisibilidade:
    def test_diretoria_ve_tudo(self, monkeypatch):
        docs = [documento(1, 100, "contrato"), documento(2, 200, "tep")]
        uc = montar(monkeypatch, docs)

        resultado = uc.execute(DIRETOR)

        assert {r["id"] for r in resultado} == {1, 2}

    def test_juridico_ve_tudo(self, monkeypatch):
        docs = [documento(1, 100, "contrato"), documento(2, 200, "tep")]
        uc = montar(monkeypatch, docs, permissoes_juridico={JURIDICO.id})

        resultado = uc.execute(JURIDICO)

        assert {r["id"] for r in resultado} == {1, 2}

    def test_caixa_pode_ver_painel_contratos_ve_tudo(self, monkeypatch):
        docs = [documento(1, 100, "contrato"), documento(2, 200, "tep")]
        uc = montar(monkeypatch, docs, permissoes_painel={NINGUEM.id})

        resultado = uc.execute(NINGUEM)

        assert {r["id"] for r in resultado} == {1, 2}

    def test_vendedor_ve_so_contrato_do_projeto_onde_vendeu(self, monkeypatch):
        docs = [
            documento(1, 100, "contrato"),  # projeto onde é vendedor
            documento(2, 100, "tep"),  # mesmo projeto, mas TEP não é dele
            documento(3, 200, "contrato"),  # outro projeto
        ]
        vendedores = [SimpleNamespace(projeto_id=100, usuario_id=VENDEDOR.id)]
        uc = montar(monkeypatch, docs, vendedores=vendedores)

        resultado = uc.execute(VENDEDOR)

        assert {r["id"] for r in resultado} == {1}

    def test_coordenador_ve_so_tep_do_projeto_onde_coordena(self, monkeypatch):
        docs = [
            documento(1, 100, "tep"),  # projeto onde coordena
            documento(2, 100, "contrato"),  # mesmo projeto, mas contrato não é dele
            documento(3, 200, "tep"),  # outro projeto
        ]
        membros = [SimpleNamespace(projeto_id=100, usuario_id=COORDENADOR.id, papel="coordenador")]
        uc = montar(monkeypatch, docs, membros=membros)

        resultado = uc.execute(COORDENADOR)

        assert {r["id"] for r in resultado} == {1}

    def test_consultor_sem_vinculo_nenhum_nao_ve_nada(self, monkeypatch):
        docs = [documento(1, 100, "contrato"), documento(2, 200, "tep")]
        uc = montar(monkeypatch, docs)

        resultado = uc.execute(NINGUEM)

        assert resultado == []

    def test_membro_nao_coordenador_do_projeto_nao_ve_o_tep(self, monkeypatch):
        docs = [documento(1, 100, "tep")]
        membros = [SimpleNamespace(projeto_id=100, usuario_id=NINGUEM.id, papel="consultor")]
        uc = montar(monkeypatch, docs, membros=membros)

        resultado = uc.execute(NINGUEM)

        assert resultado == []


class TestDocumentoInstitucional:
    def test_diretoria_ve_institucional_com_nome_externo(self, monkeypatch):
        docs = [documento_institucional(1, "nda", "Parceria Agro Insper", "Agro Ltda")]
        uc = montar(monkeypatch, docs)

        resultado = uc.execute(DIRETOR)

        assert resultado[0]["projeto_id"] is None
        assert resultado[0]["projeto_nome"] == "Parceria Agro Insper"
        assert resultado[0]["cliente"] == "Agro Ltda"
        assert resultado[0]["frente_ids"] == []

    def test_vendedor_sem_vinculo_nao_ve_institucional(self, monkeypatch):
        docs = [documento_institucional(1, "contrato", "Parceria Agro Insper")]
        uc = montar(monkeypatch, docs)

        assert uc.execute(VENDEDOR) == []

"""⭐ 2026-09-18, a pedido: entrar numa banca sem vaga livre pra quem pede.

A autoinscrição normal (`CreateCandidaturaUseCase`) já é testada em
`test_vaga_reservada_pro_piso.py` e companhia — aqui ela é um DUBLÊ
(`FakeCreateCandidatura`), porque o que se testa é a decisão de "isto vira
pedido ou sobe direto?", não a aritmética de vagas de novo.

Mesmo idioma de `test_remarcacao_solicitacao.py`: repositórios trocados no
módulo via `monkeypatch`, sem sessão de banco.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import entrada_solicitacao
from src.use_cases.banca.entrada_solicitacao import (
    DecidirEntradaBancaRequest,
    DecidirEntradaBancaUseCase,
    ListarEntradaBancaPendentesUseCase,
    ListarMinhasEntradaBancaUseCase,
    SolicitarEntradaBancaRequest,
    SolicitarEntradaBancaUseCase,
)
from src.utils.exceptions import CODIGO_BANCA_LOTADA, RegraDeNegocioError

DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


def _banca(*, data_hora=datetime(2026, 9, 25, 14, 0), nome_projeto="FRUTAS I"):
    return SimpleNamespace(id=50, data_hora=data_hora, nome_projeto=nome_projeto)


@pytest.fixture
def solicitar(monkeypatch):
    def _montar(*, banca=None, pendente=None, candidatura_erro=None, candidatura_ok=None):
        banca = banca if banca is not None else _banca()
        estado = SimpleNamespace(criados=[], atualizados=[], notificados=[], tentou_alocar=[])

        class RepoFake:
            def __init__(self, db):
                pass

            def get_pendente_do_par(self, banca_id, usuario_id):
                return pendente

            def create(self, **campos):
                estado.criados.append(campos)
                return SimpleNamespace(id=99, status="pendente", **campos)

            def update(self, pedido_id, **campos):
                estado.atualizados.append(campos)
                base = pendente or SimpleNamespace()
                for k, v in campos.items():
                    setattr(base, k, v)
                base.id = pedido_id
                return base

        class BancaFake:
            def __init__(self, db):
                pass

            def get_by_id(self, _id):
                return banca

        class UsuarioFake:
            def __init__(self, db):
                pass

            def get_by_id(self, uid):
                return SimpleNamespace(id=uid, nome="Fulano")

            def get_por_posicoes(self, *posicoes):
                return [DANI] if "diretor_projetos" in posicoes else []

        class FakeCreateCandidatura:
            def __init__(self, db):
                pass

            def execute(self, request, usuario_id, eh_gestao):
                estado.tentou_alocar.append(usuario_id)
                if candidatura_erro:
                    raise candidatura_erro
                return candidatura_ok or {"id": 1, "banca_id": request.banca_id, "usuario_id": usuario_id}

        monkeypatch.setattr(entrada_solicitacao, "BancaEntradaSolicitacaoRepository", RepoFake)
        monkeypatch.setattr(entrada_solicitacao, "BancaRepository", BancaFake)
        monkeypatch.setattr(entrada_solicitacao, "UsuarioRepository", UsuarioFake)
        monkeypatch.setattr(entrada_solicitacao, "CreateCandidaturaUseCase", FakeCreateCandidatura)
        # `notificar` é importado DENTRO de `_avisar_diretoria` (import local
        # pra evitar ciclo) — troca direto onde ele mora, não no módulo.
        import src.utils.notificar as notificar_mod

        monkeypatch.setattr(
            notificar_mod, "notificar", lambda db, uid, msg, **kw: estado.notificados.append((uid, msg))
        )

        def _executar(justificativa="Quero muito avaliar este projeto"):
            return SolicitarEntradaBancaUseCase(db=None).execute(
                SolicitarEntradaBancaRequest(banca_id=50, justificativa=justificativa),
                solicitado_por=10,
            )

        return _executar, estado

    return _montar


class TestSolicitar:
    def test_aloca_direto_quando_a_vaga_estava_livre(self, solicitar):
        """A vaga pode ter aberto entre a pessoa ver a tela e clicar — a
        autoinscrição normal já resolve, sem pedido nenhum."""
        executar, estado = solicitar()

        resultado = executar()

        assert resultado["alocado_direto"] is True
        assert estado.criados == []
        assert estado.notificados == []

    def test_cria_pedido_quando_recusada_por_banca_lotada(self, solicitar):
        erro = RegraDeNegocioError("Não é possível se candidatar: banca lotada", codigo=CODIGO_BANCA_LOTADA)
        executar, estado = solicitar(candidatura_erro=erro)

        resultado = executar()

        assert resultado["alocado_direto"] is False
        assert len(estado.criados) == 1
        assert estado.criados[0]["usuario_id"] == 10
        assert [uid for uid, _ in estado.notificados] == [DANI.id]

    def test_recusa_reservada_pro_piso_tambem_cria_pedido(self, solicitar):
        """O segundo caso de `CODIGO_BANCA_LOTADA`: última vaga reservada
        pro piso por frente que quem pediu não cobre."""
        erro = RegraDeNegocioError(
            "Esta vaga está reservada para completar a composição: falta 1 liderança de Business.",
            codigo=CODIGO_BANCA_LOTADA,
        )
        executar, estado = solicitar(candidatura_erro=erro)

        resultado = executar()

        assert resultado["alocado_direto"] is False
        assert len(estado.criados) == 1

    def test_outro_motivo_de_recusa_sobe_direto(self, solicitar):
        """Já é candidata, é do próprio grupo, banca realizada/cancelada —
        nada disso é "falta de vaga", então não faz sentido pedir aprovação."""
        erro = RegraDeNegocioError("Você não pode se candidatar à banca do seu próprio grupo")
        executar, estado = solicitar(candidatura_erro=erro)

        with pytest.raises(RegraDeNegocioError, match="próprio grupo"):
            executar()
        assert estado.criados == []
        assert estado.notificados == []

    def test_sem_justificativa_nao_passa(self, solicitar):
        executar, estado = solicitar()

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(justificativa="   ")
        # Nem chega a tentar a autoinscrição.
        assert estado.tentou_alocar == []

    def test_pedir_de_novo_reescreve_o_pendente(self, solicitar):
        pendente = SimpleNamespace(id=99, status="pendente", banca_id=50, usuario_id=10)
        erro = RegraDeNegocioError("banca lotada", codigo=CODIGO_BANCA_LOTADA)
        executar, estado = solicitar(candidatura_erro=erro, pendente=pendente)

        executar(justificativa="Motivo atualizado")

        assert estado.criados == []
        assert estado.atualizados[0]["justificativa"] == "Motivo atualizado"
        # Reescrever não dispara um segundo aviso à diretoria.
        assert estado.notificados == []

    def test_banca_nao_encontrada_devolve_none(self):
        uc = SolicitarEntradaBancaUseCase.__new__(SolicitarEntradaBancaUseCase)
        uc.db = None
        uc.banca_repository = SimpleNamespace(get_by_id=lambda _id: None)
        uc.repository = SimpleNamespace()
        uc.usuario_repository = SimpleNamespace()

        resultado = uc.execute(
            SolicitarEntradaBancaRequest(banca_id=999, justificativa="Motivo"),
            solicitado_por=10,
        )
        assert resultado is None


@pytest.fixture
def decidir(monkeypatch):
    def _montar(*, pedido, candidaturas_existentes=None):
        estado = SimpleNamespace(atualizados=[], notificados=[], criadas=[])

        class RepoFake:
            def __init__(self, db):
                pass

            def get_by_id(self, _id):
                return pedido

            def update(self, pedido_id, **campos):
                estado.atualizados.append(campos)
                for k, v in campos.items():
                    setattr(pedido, k, v)
                return pedido

        class CandidaturaFake:
            def __init__(self, db):
                pass

            def get_by_banca(self, _banca_id):
                return candidaturas_existentes or []

            def create(self, **campos):
                estado.criadas.append(campos)
                return SimpleNamespace(id=1, **campos)

        class BancaFake:
            def __init__(self, db):
                pass

            def get_by_id(self, _id):
                return _banca()

        monkeypatch.setattr(entrada_solicitacao, "BancaEntradaSolicitacaoRepository", RepoFake)
        monkeypatch.setattr(entrada_solicitacao, "CandidaturaRepository", CandidaturaFake)
        monkeypatch.setattr(entrada_solicitacao, "BancaRepository", BancaFake)
        import src.utils.notificar as notificar_mod

        monkeypatch.setattr(
            notificar_mod, "notificar", lambda db, uid, msg, **kw: estado.notificados.append((uid, msg))
        )

        def _executar(aprovar=True, resposta="ok"):
            return DecidirEntradaBancaUseCase(db=None).execute(
                pedido.id,
                DecidirEntradaBancaRequest(aprovar=aprovar, resposta=resposta),
                respondido_por=DANI.id,
            )

        return _executar, estado

    return _montar


def _pedido_pendente():
    return SimpleNamespace(
        id=99,
        status="pendente",
        banca_id=50,
        usuario_id=10,
        justificativa="Quero muito avaliar este projeto",
        resposta=None,
    )


class TestDecidir:
    def test_aprovar_cria_a_candidatura_acima_do_teto(self, decidir):
        executar, estado = decidir(pedido=_pedido_pendente())

        resultado = executar(aprovar=True, resposta="Combinado, pode entrar")

        assert resultado["status"] == "aprovada"
        assert resultado["candidatura_criada"] is True
        assert estado.criadas[0]["usuario_id"] == 10
        assert estado.criadas[0]["banca_id"] == 50
        assert [uid for uid, _ in estado.notificados] == [10]

    def test_aprovar_nao_duplica_se_ja_entrou_por_outra_via(self, decidir):
        """Alguém se desalocou no meio tempo e a pessoa usou Alocar-se
        direto — aprovar não pode criar uma segunda candidatura (bateria na
        constraint `uq_candidatura_banca_usuario`)."""
        executar, estado = decidir(
            pedido=_pedido_pendente(),
            candidaturas_existentes=[SimpleNamespace(usuario_id=10)],
        )

        resultado = executar(aprovar=True, resposta="Combinado")

        assert resultado["candidatura_criada"] is False
        assert estado.criadas == []

    def test_recusar_nao_cria_candidatura(self, decidir):
        executar, estado = decidir(pedido=_pedido_pendente())

        resultado = executar(aprovar=False, resposta="Não há como abrir exceção agora")

        assert resultado["status"] == "recusada"
        assert estado.criadas == []

    def test_resposta_vazia_nao_passa(self, decidir):
        executar, _ = decidir(pedido=_pedido_pendente())

        with pytest.raises(RegraDeNegocioError, match="motivo"):
            executar(resposta="  ")

    def test_pedido_ja_respondido_nao_passa(self, decidir):
        pedido = _pedido_pendente()
        pedido.status = "aprovada"
        executar, _ = decidir(pedido=pedido)

        with pytest.raises(RegraDeNegocioError, match="já foi respondido"):
            executar()


class TestListar:
    def test_lista_com_contexto_da_banca(self, monkeypatch):
        pedido = SimpleNamespace(
            id=1, banca_id=50, usuario_id=10, justificativa="Motivo", criado_em=datetime(2026, 9, 18)
        )

        class RepoFake:
            def __init__(self, db):
                pass

            def get_pendentes(self):
                return [pedido]

        class BancaFake:
            def __init__(self, db):
                pass

            def get_by_id(self, _id):
                return _banca()

        class UsuarioFake:
            def __init__(self, db):
                pass

            def get_by_id(self, uid):
                return SimpleNamespace(id=uid, nome="Fulano de Tal")

        class BancaFrenteFake:
            def __init__(self, db):
                pass

            def get_by_banca(self, _id):
                return []

        class FrenteFake:
            def __init__(self, db):
                pass

            def get_by_id(self, _id):
                return None

        class CandidaturaFake:
            def __init__(self, db):
                pass

            def get_by_banca(self, _id):
                return [SimpleNamespace(usuario_id=1), SimpleNamespace(usuario_id=2)]

        monkeypatch.setattr(entrada_solicitacao, "BancaEntradaSolicitacaoRepository", RepoFake)
        monkeypatch.setattr(entrada_solicitacao, "BancaRepository", BancaFake)
        monkeypatch.setattr(entrada_solicitacao, "UsuarioRepository", UsuarioFake)
        monkeypatch.setattr(entrada_solicitacao, "_projeto_id_da_banca", lambda db, banca_id: 3)
        import src.repositories.banca_frente_repository as bf_mod
        import src.repositories.frente_repository as f_mod
        import src.utils.teto_banca as teto_mod

        monkeypatch.setattr(bf_mod, "BancaFrenteRepository", BancaFrenteFake)
        monkeypatch.setattr(f_mod, "FrenteRepository", FrenteFake)
        monkeypatch.setattr(teto_mod, "calcular_vagas_banca", lambda frentes, db: 5)
        monkeypatch.setattr(entrada_solicitacao, "CandidaturaRepository", CandidaturaFake)

        linhas = ListarEntradaBancaPendentesUseCase(db=None).execute()

        assert len(linhas) == 1
        assert linhas[0]["projeto_id"] == 3
        assert linhas[0]["projeto_nome"] == "FRUTAS I"
        assert linhas[0]["usuario_nome"] == "Fulano de Tal"
        assert linhas[0]["alocados"] == 2


class TestListarMinhas:
    def test_devolve_so_os_pedidos_pendentes_da_pessoa(self, monkeypatch):
        """2026-09-18, a pedido: é o que `/bancas` usa pra trocar "Solicitar
        entrada" por "Aguardando aprovação" nas bancas que a pessoa já
        pediu — só as DELA, não a fila inteira da diretoria."""
        meu_pedido = SimpleNamespace(id=1, banca_id=50, criado_em=datetime(2026, 9, 18))

        class RepoFake:
            def __init__(self, db):
                pass

            def get_pendentes_do_usuario(self, usuario_id):
                assert usuario_id == 10
                return [meu_pedido]

        monkeypatch.setattr(entrada_solicitacao, "BancaEntradaSolicitacaoRepository", RepoFake)

        linhas = ListarMinhasEntradaBancaUseCase(db=None).execute(10)

        assert linhas == [{"id": 1, "banca_id": 50, "criado_em": datetime(2026, 9, 18)}]

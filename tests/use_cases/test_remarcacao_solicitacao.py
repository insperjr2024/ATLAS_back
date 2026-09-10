"""⭐ §13, 2026-09-10: o pedido de remarcação de uma banca que já tem data.

Remarcar dentro da janela e com folga era LIVRE — bastava justificativa e a
data trocava na hora. Virou rotina silenciosa (o coordenador do ENSINO
remarcou e ninguém aprovou). Agora quem não é da diretoria PEDE aqui, a
diretoria decide, e a aprovação chama a marcação de volta com
`eh_diretor_projetos=True`.

Dublês à mão, repositórios trocados no módulo via `monkeypatch` — mesmo idioma
de `test_banca_fora_da_janela.py`.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import marcar_banca_escopo, remarcacao_solicitacao
from src.use_cases.banca.remarcacao_solicitacao import (
    DecidirRemarcacaoRequest,
    DecidirRemarcacaoUseCase,
    SolicitarRemarcacaoRequest,
    SolicitarRemarcacaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

ANTIGA = datetime(2026, 9, 24, 14, 0)
NOVA = datetime(2026, 9, 25, 14, 0)
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


def _escopo(id=7):
    return SimpleNamespace(id=id, projeto_id=3, escopo_id=None, nome_customizado="Contratos")


def _banca(*, data_hora=ANTIGA, realizado_em=None, cancelada_em=None):
    return SimpleNamespace(
        id=50, data_hora=data_hora, realizado_em=realizado_em, cancelada_em=cancelada_em
    )


@pytest.fixture
def solicitar(monkeypatch):
    def _montar(*, banca=None, pendente=None, alvo=None):
        alvo = alvo if alvo is not None else _escopo()
        estado = SimpleNamespace(criados=[], atualizados=[], notificados=[])

        class RepoFake:
            def __init__(self, db):
                pass

            def get_pendente_da_banca(self, banca_id):
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

            def get_by_projeto_escopo(self, _id):
                return banca

        class EscopoFake:
            def __init__(self, db):
                pass

            def get_by_id(self, escopo_id):
                return alvo if alvo and alvo.id == escopo_id else None

        class ProjetoFake:
            def __init__(self, db):
                pass

            def get_by_id(self, _id):
                return SimpleNamespace(id=3, nome="Projeto ENSINO")

        class UsuarioFake:
            def __init__(self, db):
                pass

            def get_por_posicoes(self, *posicoes):
                return [DANI] if "diretor_projetos" in posicoes else []

        monkeypatch.setattr(remarcacao_solicitacao, "BancaRemarcacaoSolicitacaoRepository", RepoFake)
        monkeypatch.setattr(remarcacao_solicitacao, "BancaRepository", BancaFake)
        monkeypatch.setattr(remarcacao_solicitacao, "ProjetoEscopoRepository", EscopoFake)
        monkeypatch.setattr(remarcacao_solicitacao, "ProjetoRepository", ProjetoFake)
        monkeypatch.setattr(remarcacao_solicitacao, "UsuarioRepository", UsuarioFake)
        monkeypatch.setattr(
            remarcacao_solicitacao,
            "notificar",
            lambda db, uid, msg, **kw: estado.notificados.append((uid, msg)),
        )

        def _executar(data=NOVA, justificativa="O cliente pediu outro dia"):
            return SolicitarRemarcacaoUseCase(db=None).execute(
                SolicitarRemarcacaoRequest(
                    projeto_escopo_id=alvo.id,
                    data_hora_pretendida=data,
                    justificativa=justificativa,
                ),
                solicitado_por=10,
            )

        return _executar, estado

    return _montar


class TestSolicitar:
    def test_cria_o_pedido_e_avisa_a_diretoria(self, solicitar):
        executar, estado = solicitar(banca=_banca())

        resultado = executar()

        assert len(estado.criados) == 1
        assert estado.criados[0]["data_hora_anterior"] == ANTIGA
        assert estado.criados[0]["data_hora_pretendida"] == NOVA
        assert resultado["status"] == "pendente"
        assert [uid for uid, _ in estado.notificados] == [DANI.id]

    def test_sem_justificativa_nao_passa(self, solicitar):
        executar, _ = solicitar(banca=_banca())

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(justificativa="   ")

    def test_mesma_data_nao_e_remarcacao(self, solicitar):
        executar, _ = solicitar(banca=_banca())

        with pytest.raises(RegraDeNegocioError, match="mesma"):
            executar(data=ANTIGA)

    def test_banca_sem_data_nao_tem_o_que_remarcar(self, solicitar):
        executar, _ = solicitar(banca=_banca(data_hora=None))

        with pytest.raises(RegraDeNegocioError, match="não há o que remarcar"):
            executar()

    def test_banca_ja_realizada_e_segunda_banca_nao_remarcacao(self, solicitar):
        executar, _ = solicitar(banca=_banca(realizado_em=ANTIGA))

        with pytest.raises(RegraDeNegocioError, match="segunda"):
            executar()

    def test_banca_cancelada_nao_passa(self, solicitar):
        executar, _ = solicitar(banca=_banca(cancelada_em=ANTIGA))

        with pytest.raises(RegraDeNegocioError, match="cancelada"):
            executar()

    def test_pedir_de_novo_reescreve_o_pendente(self, solicitar):
        pendente = SimpleNamespace(id=99, status="pendente", banca_id=50)
        executar, estado = solicitar(banca=_banca(), pendente=pendente)

        executar(data=datetime(2026, 9, 26, 14, 0), justificativa="Mudou de novo")

        assert estado.criados == []
        assert estado.atualizados[0]["data_hora_pretendida"] == datetime(2026, 9, 26, 14, 0)
        assert estado.atualizados[0]["justificativa"] == "Mudou de novo"
        # Reescrever não dispara um segundo aviso à diretoria.
        assert estado.notificados == []


@pytest.fixture
def decidir(monkeypatch):
    def _montar(*, pedido, marcar_erro=None):
        estado = SimpleNamespace(atualizados=[], notificados=[], marcou=[])

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

        class EscopoFake:
            def __init__(self, db):
                pass

        class MarcarFake:
            def __init__(self, db):
                pass

            def execute(self, escopo_id, request, **kwargs):
                estado.marcou.append({"escopo_id": escopo_id, **kwargs})
                if marcar_erro:
                    raise RegraDeNegocioError(marcar_erro)
                return {"id": 50, "data_hora": request.data_hora}

        monkeypatch.setattr(remarcacao_solicitacao, "BancaRemarcacaoSolicitacaoRepository", RepoFake)
        monkeypatch.setattr(remarcacao_solicitacao, "ProjetoEscopoRepository", EscopoFake)
        monkeypatch.setattr(marcar_banca_escopo, "MarcarBancaEscopoUseCase", MarcarFake)
        monkeypatch.setattr(
            remarcacao_solicitacao,
            "notificar",
            lambda db, uid, msg, **kw: estado.notificados.append((uid, msg)),
        )

        def _executar(aprovar=True, resposta="ok"):
            return DecidirRemarcacaoUseCase(db=None).execute(
                pedido.id,
                DecidirRemarcacaoRequest(aprovar=aprovar, resposta=resposta),
                respondido_por=DANI.id,
            )

        return _executar, estado

    return _montar


def _pedido_pendente():
    return SimpleNamespace(
        id=99,
        status="pendente",
        banca_id=50,
        projeto_escopo_id=7,
        data_hora_anterior=ANTIGA,
        data_hora_pretendida=NOVA,
        justificativa="O cliente pediu outro dia",
        solicitado_por=10,
        resposta=None,
    )


class TestDecidir:
    def test_aprovar_remarca_a_banca_como_diretoria(self, decidir):
        executar, estado = decidir(pedido=_pedido_pendente())

        resultado = executar(aprovar=True, resposta="Combinado")

        assert resultado["status"] == "aprovada"
        assert resultado["banca_marcada_em"] == NOVA
        assert estado.marcou[0]["eh_diretor_projetos"] is True
        assert [uid for uid, _ in estado.notificados] == [10]

    def test_recusar_nao_marca_nada(self, decidir):
        executar, estado = decidir(pedido=_pedido_pendente())

        resultado = executar(aprovar=False, resposta="Não dá")

        assert resultado["status"] == "recusada"
        assert estado.marcou == []

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

    def test_marcacao_falhou_o_pedido_volta_a_pendente(self, decidir):
        executar, estado = decidir(
            pedido=_pedido_pendente(), marcar_erro="Já existe uma banca marcada para este horário"
        )

        with pytest.raises(RegraDeNegocioError, match="Já existe uma banca"):
            executar(aprovar=True, resposta="Combinado")

        # Última escrita: de volta para a fila, sem responsável.
        assert estado.atualizados[-1]["status"] == "pendente"
        assert estado.atualizados[-1]["respondido_por"] is None

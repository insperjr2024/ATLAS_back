"""⭐ O pedido de autorização para marcar banca fora da janela do escopo (§13).

Antes, marcar fora da janela era um atalho de um ato só: só quem tinha
`posicao == "diretor"` conseguia, e fazia sozinho, na mesma chamada que
gravava a data. Este arquivo prende o desenho novo — dois atos separados,
mesmo idioma do pedido de exceção de choque e do pedido de dias de ajuste:

- **Quem marca pede**, com justificativa, e só se a data REALMENTE cair fora
  da janela.
- **A diretoria decide depois**, em ato separado, sempre com justificativa
  nos dois sentidos.
- **A autorização é do par (escopo, data)**, não do escopo inteiro nem da
  banca — outra data do mesmo escopo pede de novo.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch`,
mesmo idioma de `test_dias_de_ajuste.py`.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import fora_janela
from src.use_cases.banca.fora_janela import (
    DecidirForaJanelaRequest,
    DecidirForaJanelaUseCase,
    SolicitarForaJanelaRequest,
    SolicitarForaJanelaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

QUI_03_09 = date(2026, 9, 3)  # a reunião inicial
DENTRO = datetime(2026, 9, 25, 14, 0)  # dentro dos 20 vendidos
FORA = datetime(2026, 10, 20, 14, 0)  # bem depois do fim da janela

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor")


def escopo(id=7, vendidos=20, ajustados=0, data_inicio=QUI_03_09):
    return SimpleNamespace(
        id=id,
        projeto_id=3,
        escopo_id=None,
        nome_customizado="Elaboração Contratual",
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
        data_inicio=data_inicio,
    )


@pytest.fixture
def pedir(monkeypatch):
    """Devolve `(executar, estado)` — `estado` mostra o que foi gravado."""

    def _montar(alvo=None, *, banca_existente=None, pendente=None, aprovada=None):
        alvo = alvo if alvo is not None else escopo()
        estado = SimpleNamespace(criados=[], atualizados=[], notificados=[])

        class ForaJanelaFake:
            def __init__(self, db): pass
            def get_aprovada(self, escopo_id, data_hora):
                return aprovada
            def get_pendente_do_par(self, escopo_id, data_hora):
                return pendente
            def create(self, **campos):
                estado.criados.append(campos)
                return SimpleNamespace(
                    id=99, status="pendente", respondido_por=None, resposta=None,
                    respondido_em=None, criado_em=None, **campos,
                )
            def update(self, pedido_id, **campos):
                estado.atualizados.append(campos)
                for k, v in campos.items():
                    setattr(pendente, k, v)
                return pendente

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, _id): return banca_existente

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, escopo_id):
                return alvo if alvo and alvo.id == escopo_id else None

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id):
                return SimpleNamespace(id=3, nome="Projeto Alfa")

        class UsuarioFake:
            def __init__(self, db): pass
            def get_por_posicao(self, posicao):
                return [DANI] if posicao == "diretor" else []

        class DiaNaoLetivoFake:
            def __init__(self, db): pass
            def get_all(self): return []

        class HistoricoFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id): return []

        monkeypatch.setattr(fora_janela, "BancaForaJanelaRepository", ForaJanelaFake)
        monkeypatch.setattr(fora_janela, "BancaRepository", BancaFake)
        monkeypatch.setattr(fora_janela, "ProjetoEscopoRepository", EscopoProjetoFake)
        monkeypatch.setattr(fora_janela, "ProjetoRepository", ProjetoFake)
        monkeypatch.setattr(fora_janela, "UsuarioRepository", UsuarioFake)
        monkeypatch.setattr(fora_janela, "DiaNaoLetivoRepository", DiaNaoLetivoFake)
        monkeypatch.setattr(fora_janela, "ProjetoStatusHistoricoRepository", HistoricoFake)

        def notificou(db, dest, mensagem, **k):
            estado.notificados.append(dest)

        monkeypatch.setattr(fora_janela, "notificar", notificou)

        uc = SolicitarForaJanelaUseCase.__new__(SolicitarForaJanelaUseCase)
        uc.__init__(db=None)

        def executar(
            data_hora=FORA, justificativa="Agenda do cliente atrasou", quem=ANA,
        ):
            return uc.execute(
                SolicitarForaJanelaRequest(
                    projeto_escopo_id=alvo.id,
                    data_hora_pretendida=data_hora,
                    justificativa=justificativa,
                ),
                solicitado_por=quem.id,
            )

        return executar, estado

    return _montar


class TestSolicitar:
    def test_data_fora_da_janela_cria_o_pedido_e_avisa_a_diretoria(self, pedir):
        executar, estado = pedir()

        resposta = executar()

        assert resposta["status"] == "pendente"
        assert estado.criados[0]["projeto_escopo_id"] == 7
        assert estado.criados[0]["data_hora_pretendida"] == FORA
        assert estado.notificados == [DANI.id]

    def test_justificativa_vazia_nao_passa(self, pedir):
        executar, _ = pedir()

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(justificativa="   ")

    def test_data_dentro_da_janela_nao_precisa_de_pedido(self, pedir):
        """Sem esta checagem a fila da diretoria encheria de pedidos para
        datas que já cabiam — cada um seria uma decisão sobre nada."""
        executar, _ = pedir()

        with pytest.raises(RegraDeNegocioError, match="dentro da janela"):
            executar(data_hora=DENTRO)

    def test_data_ja_autorizada_nao_pede_de_novo(self, pedir):
        executar, _ = pedir(aprovada=SimpleNamespace(id=1))

        with pytest.raises(RegraDeNegocioError, match="já foi autorizada"):
            executar()

    def test_pedir_de_novo_reescreve_o_pendente_em_vez_de_duplicar(self, pedir):
        pendente = SimpleNamespace(
            id=5, projeto_escopo_id=7, data_hora_pretendida=FORA,
            justificativa="motivo antigo", status="pendente",
        )
        executar, estado = pedir(pendente=pendente)

        resposta = executar(justificativa="motivo novo, mais claro")

        assert estado.criados == []
        assert resposta["justificativa"] == "motivo novo, mais claro"

@pytest.fixture
def decidir(monkeypatch):
    def _montar(*, status="pendente"):
        estado = SimpleNamespace(notificados=[])
        pedido = SimpleNamespace(
            id=99,
            projeto_escopo_id=7,
            banca_id=None,
            data_hora_pretendida=FORA,
            justificativa="Agenda do cliente",
            status=status,
            solicitado_por=ANA.id,
            respondido_por=None,
            resposta=None,
            criado_em=None,
            respondido_em=None,
        )

        class ForaJanelaFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return pedido
            def update(self, _id, **campos):
                for k, v in campos.items():
                    setattr(pedido, k, v)
                return pedido

        monkeypatch.setattr(fora_janela, "BancaForaJanelaRepository", ForaJanelaFake)

        def notificou(db, dest, mensagem, **k):
            estado.notificados.append((dest, mensagem))

        monkeypatch.setattr(fora_janela, "notificar", notificou)

        uc = DecidirForaJanelaUseCase.__new__(DecidirForaJanelaUseCase)
        uc.__init__(db=None)

        def executar(aprovar=True, resposta="Faz sentido, agenda do cliente"):
            return uc.execute(
                99, DecidirForaJanelaRequest(aprovar=aprovar, resposta=resposta), DANI.id
            )

        return executar, estado, pedido

    return _montar


class TestDecidir:
    def test_aprovar_muda_o_status_e_avisa_quem_pediu(self, decidir):
        executar, estado, pedido = decidir()

        executar(aprovar=True)

        assert pedido.status == "aprovada"
        assert pedido.respondido_por == DANI.id
        assert estado.notificados[0][0] == ANA.id
        assert "já pode marcar" in estado.notificados[0][1]

    def test_recusar_nao_avisa_que_pode_marcar(self, decidir):
        executar, estado, pedido = decidir()

        executar(aprovar=False)

        assert pedido.status == "recusada"
        assert "já pode marcar" not in estado.notificados[0][1]

    def test_resposta_vazia_nao_passa(self, decidir):
        executar, _, _ = decidir()

        with pytest.raises(RegraDeNegocioError, match="motivo"):
            executar(resposta="  ")

    def test_pedido_ja_respondido_nao_responde_de_novo(self, decidir):
        executar, _, _ = decidir(status="aprovada")

        with pytest.raises(RegraDeNegocioError, match="já foi respondido"):
            executar()


def test_fora_janela_liberada_sem_escopo_e_falso():
    assert fora_janela.fora_janela_liberada(db=None, projeto_escopo_id=None, data_hora=FORA) is False

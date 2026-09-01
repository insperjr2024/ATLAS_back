"""⭐ O pedido de autorização para marcar banca fora da janela do escopo (§13).

Antes, marcar fora da janela era um atalho de um ato só: só quem tinha
`posicao == "diretor_projetos"` conseguia, e fazia sozinho, na mesma chamada que
gravava a data. Este arquivo prende o desenho novo — dois atos separados,
mesmo idioma do pedido de exceção de choque e do pedido de dias de ajuste:

- **Quem marca pede**, com justificativa, e só se a data REALMENTE cair fora
  da janela.
- **A diretoria decide depois**, em ato separado, sempre com justificativa
  nos dois sentidos.
- **A autorização é do par (escopo, data)**, não do escopo inteiro nem da
  banca — outra data do mesmo escopo pede de novo.
- **Autorizar MARCA a banca**, não só libera: o pedido já carrega escopo, data
  e justificativa, então não havia o que esperar de quem pediu. E se a marcação
  falhar, o pedido VOLTA para a fila em vez de ficar aprovado sem banca.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch`,
mesmo idioma de `test_dias_de_ajuste.py`.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import fora_janela, marcar_banca_escopo
from src.use_cases.banca.fora_janela import (
    DecidirForaJanelaRequest,
    DecidirForaJanelaUseCase,
    SolicitarForaJanelaRequest,
    SolicitarForaJanelaUseCase,
)
from src.utils.exceptions import CODIGO_CHOQUE_DE_HORARIO, RegraDeNegocioError

QUI_03_09 = date(2026, 9, 3)  # a reunião inicial
DENTRO = datetime(2026, 9, 25, 14, 0)  # dentro dos 20 vendidos
FORA = datetime(2026, 10, 20, 14, 0)  # bem depois do fim da janela

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor_projetos")


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
                # ⚠ Honra o PAR (escopo, data), como a consulta real. Devolvendo
                # a autorização para qualquer data, o dublê escondia o recorte
                # que é o coração desta regra: autorizar 20/10 não autoriza
                # 27/10 do mesmo escopo.
                if aprovada is None:
                    return None
                mesma_data = getattr(aprovada, "data_hora_pretendida", data_hora)
                return aprovada if mesma_data == data_hora else None
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
                return [DANI] if posicao == "diretor_projetos" else []
            def get_por_posicoes(self, *posicoes):
                return [DANI] if "diretor_projetos" in posicoes else []

        class DiaNaoLetivoFake:
            def __init__(self, db): pass
            def get_all(self): return []
            # O calendário deste projeto. Sem variantes no fake, é o mesmo
            # `get_all()` — o que muda na produção é só o corte por curso.
            def get_do_escopo(self, _escopo): return self.get_all()

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
        executar, _ = pedir(aprovada=SimpleNamespace(id=1, data_hora_pretendida=FORA))

        with pytest.raises(RegraDeNegocioError, match="já foi autorizada"):
            executar()

    def test_outra_data_do_mesmo_escopo_exige_pedido_novo(self, pedir):
        """⭐ A autorização é do PAR (escopo, data), nunca do escopo inteiro.

        É o que faz a regra se repetir a cada mudança de data: ter autorizado
        20/10 não abre 27/10. Sem este recorte, um único "sim" viraria licença
        permanente para aquele escopo marcar onde quisesse fora da janela — e a
        diretoria perderia a decisão que o §13 dá a ela.
        """
        aprovada_para_20_10 = SimpleNamespace(id=1, data_hora_pretendida=FORA)
        executar, estado = pedir(aprovada=aprovada_para_20_10)
        outra_data = datetime(2026, 10, 27, 14, 0)

        resposta = executar(data_hora=outra_data)

        assert resposta["status"] == "pendente"
        assert estado.criados[0]["data_hora_pretendida"] == outra_data
        assert estado.notificados == [DANI.id]

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

        # ⚠ O dublê vai no módulo de ORIGEM, não em `fora_janela`: o import de
        # `MarcarBancaEscopoUseCase` é local (dentro de `_marcar_a_banca`, para
        # quebrar o ciclo entre os dois módulos), então ele resolve o nome em
        # `marcar_banca_escopo` na hora da chamada. Trocar o atributo em
        # `fora_janela` não seria visto por ninguém.
        estado.marcacoes = []

        # ⚠ O choque é simulado como a marcação REAL o produz: `checar_choque`
        # roda dentro dela e só passa se já houver exceção aprovada. Por isso o
        # dublê olha `estado.liberacoes` — é o que prende a ordem "libera o §8
        # antes de marcar"; liberar depois não salvaria a marcação.
        class MarcarFake:
            def __init__(self, db): pass

            def execute(self, escopo_id, request, **kwargs):
                if estado.marcacao_falha:
                    raise RegraDeNegocioError(estado.marcacao_falha)
                if estado.choque_ate_liberar and not estado.liberacoes:
                    raise RegraDeNegocioError(
                        "Já existe uma banca marcada para este horário (PIRATININGA I). "
                        "Peça uma exceção de choque à diretoria para marcar mesmo assim",
                        codigo=CODIGO_CHOQUE_DE_HORARIO,
                    )
                estado.marcacoes.append((escopo_id, request.data_hora, request.justificativa))
                return {"id": 555, "data_hora": request.data_hora}

        estado.marcacao_falha = None
        estado.choque_ate_liberar = False
        monkeypatch.setattr(marcar_banca_escopo, "MarcarBancaEscopoUseCase", MarcarFake)

        estado.liberacoes = []

        def liberou(db, **campos):
            estado.liberacoes.append(campos)
            return SimpleNamespace(id=77, status="aprovada")

        monkeypatch.setattr(fora_janela, "liberar_choque", liberou)

        uc = DecidirForaJanelaUseCase.__new__(DecidirForaJanelaUseCase)
        uc.__init__(db=None)

        def executar(
            aprovar=True, resposta="Faz sentido, agenda do cliente", autorizar_choque=False
        ):
            return uc.execute(
                99,
                DecidirForaJanelaRequest(
                    aprovar=aprovar, resposta=resposta, autorizar_choque=autorizar_choque
                ),
                DANI.id,
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
        # ⭐ O aviso mudou junto com a decisão: enquanto aprovar só liberava,
        # ele dizia "já pode marcar" e era essa frase que segurava o fluxo.
        assert "já foi marcada" in estado.notificados[0][1]

    def test_aprovar_marca_a_banca_na_data_pedida(self, decidir):
        """⭐ O ponto do desenho novo: a decisão fecha o ciclo sozinha."""
        executar, estado, _ = decidir()

        resposta = executar(aprovar=True)

        assert estado.marcacoes == [(7, FORA, "Agenda do cliente")]
        assert resposta["banca_marcada_em"] == FORA
        assert resposta["banca_id"] == 555

    def test_aprovar_amarra_o_pedido_a_banca_que_ele_criou(self, decidir):
        """`banca_id` nasce nulo (o pedido vem antes da banca existir)."""
        executar, _, pedido = decidir()

        executar(aprovar=True)

        assert pedido.banca_id == 555

    def test_marcacao_que_falha_devolve_o_pedido_para_a_fila(self, decidir):
        """⚠ Sem isto, um choque de horário nascido depois do pedido deixaria
        uma autorização "aprovada" que não produziu banca nenhuma — e ela
        sumiria da fila sem ninguém notar."""
        executar, estado, pedido = decidir()
        estado.marcacao_falha = "Já existe uma banca marcada para este horário"

        with pytest.raises(RegraDeNegocioError, match="Já existe uma banca"):
            executar(aprovar=True)

        assert pedido.status == "pendente"
        assert pedido.respondido_por is None
        assert pedido.resposta is None
        assert estado.notificados == []

    def test_recusar_nao_marca_nada(self, decidir):
        executar, estado, pedido = decidir()

        executar(aprovar=False)

        assert pedido.status == "recusada"
        assert estado.marcacoes == []
        assert "já foi marcada" not in estado.notificados[0][1]

    def test_resposta_vazia_nao_passa(self, decidir):
        executar, _, _ = decidir()

        with pytest.raises(RegraDeNegocioError, match="motivo"):
            executar(resposta="  ")

    def test_pedido_ja_respondido_nao_responde_de_novo(self, decidir):
        executar, _, _ = decidir(status="aprovada")

        with pytest.raises(RegraDeNegocioError, match="já foi respondido"):
            executar()


class TestChoqueNaAprovacao:
    """⭐ O beco sem saída do §8 dentro do §13.

    A data pedida esbarrava na banca de outro projeto, a marcação falhava, e a
    recusa dizia "peça uma exceção de choque à diretoria" — para quem É a
    diretoria, numa fila que não tinha botão nenhum para conceder. Sem saída,
    a única ação restante era Negar um pedido legítimo.
    """

    def test_choque_sem_autorizacao_devolve_o_pedido_e_preserva_o_codigo(self, decidir):
        """⚠ O CÓDIGO precisa sobreviver: é por ele que a tela oferece a saída.

        Procurar a frase na mensagem foi o que já quebrou o "registrar assim
        mesmo" da composição de banca quando o texto mudou.
        """
        executar, estado, pedido = decidir()
        estado.choque_ate_liberar = True

        with pytest.raises(RegraDeNegocioError) as recusa:
            executar(aprovar=True)

        assert recusa.value.codigo == CODIGO_CHOQUE_DE_HORARIO
        assert "PIRATININGA I" in str(recusa.value)
        # Volta para a fila: aprovado sem banca sumiria da tela sem produzir nada.
        assert pedido.status == "pendente"
        assert pedido.respondido_por is None
        assert estado.marcacoes == []

    def test_autorizar_o_choque_libera_antes_de_marcar(self, decidir):
        """A ordem é o ponto: `checar_choque` roda DENTRO da marcação."""
        executar, estado, pedido = decidir()
        estado.choque_ate_liberar = True

        resposta = executar(aprovar=True, autorizar_choque=True)

        assert len(estado.liberacoes) == 1
        assert estado.marcacoes == [(7, FORA, "Agenda do cliente")]
        assert pedido.status == "aprovada"
        assert resposta["banca_marcada_em"] == FORA

    def test_a_liberacao_guarda_quem_pediu_a_banca_e_quem_decidiu(self, decidir):
        """Quem pediu a exceção é quem pediu a BANCA, não a diretora.

        A exceção existe por causa do pedido dele, e é o histórico dele que
        precisa mostrar por que aquele horário foi aberto.
        """
        executar, estado, _ = decidir()
        estado.choque_ate_liberar = True

        executar(aprovar=True, autorizar_choque=True)

        liberacao = estado.liberacoes[0]
        assert liberacao["solicitado_por"] == ANA.id
        assert liberacao["respondido_por"] == DANI.id
        assert liberacao["projeto_escopo_id"] == 7
        assert liberacao["data_hora"] == FORA

    def test_sem_choque_nenhum_a_aprovacao_normal_nao_libera_nada(self, decidir):
        """⚠ Aprovar o §13 não pode virar liberação silenciosa do §8."""
        executar, estado, _ = decidir()

        executar(aprovar=True)

        assert estado.liberacoes == []
        assert estado.marcacoes == [(7, FORA, "Agenda do cliente")]

    def test_recusar_nao_libera_choque_mesmo_marcado(self, decidir):
        """A caixa só vale acompanhando um SIM — recusar não abre horário."""
        executar, estado, pedido = decidir()

        executar(aprovar=False, autorizar_choque=True)

        assert pedido.status == "recusada"
        assert estado.liberacoes == []
        assert estado.marcacoes == []


def test_fora_janela_liberada_sem_escopo_e_falso():
    assert fora_janela.fora_janela_liberada(db=None, projeto_escopo_id=None, data_hora=FORA) is False

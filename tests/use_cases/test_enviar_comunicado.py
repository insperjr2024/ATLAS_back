"""Comunicado manual (2026-10-11): o recorte de destinatarios e o disparo.

Mesmo idioma dos vizinhos: dubles a mao, `registrar_varios` trocado no
modulo. O que importa aqui: cada segmento pega quem deve (e so ativo),
desmarcado na previa nao recebe, e o disparo e um tipo `comunicado` com a
MESMA chave pra todo mundo, mas chave nova a cada envio.
"""

from types import SimpleNamespace

import pytest

import src.use_cases.comunicado.enviar_comunicado as mod
from src.use_cases.comunicado.enviar_comunicado import (
    ComunicadoRequest,
    EnviarComunicadoUseCase,
    FiltroComunicado,
    ResolverDestinatariosUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def usuario(id, nome, posicao="consultor", ativo=True):
    return SimpleNamespace(id=id, nome=nome, posicao=posicao, email_insper=f"{nome.lower()}@x.com", ativo=ativo)


ANA = usuario(1, "Ana")
BIA = usuario(2, "Bia", "coordenador")
CAIO = usuario(3, "Caio", "gerente")
DESLIGADO = usuario(4, "Duda", ativo=False)

DIRETOR = SimpleNamespace(id=50, nome="Diretor")


def _resolver(
    *,
    ativos=(ANA, BIA, CAIO),
    carga=(),
    pendencias=None,
    lote=None,
    banca=None,
    candidaturas=(),
    por_posicao=(),
    pastas_pdi=(),
    pendencias_pdi=None,
):
    uc = ResolverDestinatariosUseCase.__new__(ResolverDestinatariosUseCase)
    uc.usuario_repository = SimpleNamespace(
        get_ativos=lambda: list(ativos),
        get_ativos_por_posicoes_ou_cargo_extra=lambda posicoes: list(por_posicao),
    )
    uc.candidatura_repository = SimpleNamespace(get_by_banca=lambda banca_id: list(candidaturas))
    uc.banca_repository = SimpleNamespace(get_by_id=lambda banca_id: banca)
    uc.lote_repository = SimpleNamespace(get_by_id=lambda lote_id: lote)
    uc.carga_use_case = SimpleNamespace(execute=lambda filtro="todas": list(carga))
    uc.pendencias_use_case = SimpleNamespace(execute=lambda lote_id: pendencias)
    uc.pasta_pdi_repository = SimpleNamespace(
        get_ordenadas=lambda: list(pastas_pdi),
        get_by_id=lambda i: next((p for p in pastas_pdi if p.id == i), None),
    )
    uc.pendencias_pdi_use_case = SimpleNamespace(execute=lambda pasta_id: pendencias_pdi)
    return uc


def carga(u, qtd):
    return {"usuario_id": u.id, "nome": u.nome, "posicao": u.posicao, "quantidade_bancas": qtd}


def pendencia(avaliador, respondida):
    return {"avaliador_id": avaliador.id, "avaliador_nome": avaliador.nome, "avaliado_id": 99, "respondida": respondida}


class TestSegmentos:
    def test_zero_bancas_pega_so_quem_esta_zerado(self):
        uc = _resolver(carga=[carga(ANA, 0), carga(BIA, 2), carga(CAIO, 0)])

        r = uc.execute(FiltroComunicado(segmento="zero_bancas"))

        assert [d["usuario_id"] for d in r["destinatarios"]] == [ANA.id, CAIO.id]
        assert "0 bancas" in r["rotulo"]

    def test_bancas_acima_de_e_pelo_menos_n_com_detalhe(self):
        uc = _resolver(carga=[carga(ANA, 1), carga(BIA, 3), carga(CAIO, 5)])

        r = uc.execute(FiltroComunicado(segmento="bancas_acima_de", minimo_bancas=3))

        assert [d["usuario_id"] for d in r["destinatarios"]] == [BIA.id, CAIO.id]
        assert {d["detalhe"] for d in r["destinatarios"]} == {"3 bancas", "5 bancas"}

    def test_bancas_acima_de_sem_minimo_recusa(self):
        with pytest.raises(RegraDeNegocioError):
            _resolver().execute(FiltroComunicado(segmento="bancas_acima_de"))

    def test_pendentes_do_lote_agrupa_por_avaliador_e_ignora_respondida(self):
        lote = SimpleNamespace(id=7, nome="Periódica outubro")
        uc = _resolver(
            lote=lote,
            pendencias=[pendencia(ANA, False), pendencia(ANA, False), pendencia(BIA, True), pendencia(CAIO, False)],
        )

        r = uc.execute(FiltroComunicado(segmento="pendentes_do_lote", lote_id=7))

        por_id = {d["usuario_id"]: d for d in r["destinatarios"]}
        assert set(por_id) == {ANA.id, CAIO.id}
        assert por_id[ANA.id]["detalhe"] == "2 pendências"
        assert por_id[CAIO.id]["detalhe"] == "1 pendência"
        assert "Periódica outubro" in r["rotulo"]

    def test_lote_inexistente_recusa(self):
        with pytest.raises(RegraDeNegocioError):
            _resolver(lote=None, pendencias=None).execute(FiltroComunicado(segmento="pendentes_do_lote", lote_id=1))

    def test_inscritos_da_banca_todos_ou_so_confirmados(self):
        banca = SimpleNamespace(id=3, nome_projeto="ALFA")
        cands = [
            SimpleNamespace(usuario_id=ANA.id, confirmado=True),
            SimpleNamespace(usuario_id=BIA.id, confirmado=False),
        ]
        uc = _resolver(banca=banca, candidaturas=cands)

        todos = uc.execute(FiltroComunicado(segmento="inscritos_da_banca", banca_id=3))
        confirmados = uc.execute(FiltroComunicado(segmento="inscritos_da_banca", banca_id=3, so_confirmados=True))

        assert {d["usuario_id"] for d in todos["destinatarios"]} == {ANA.id, BIA.id}
        assert [d["usuario_id"] for d in confirmados["destinatarios"]] == [ANA.id]
        assert "ALFA" in todos["rotulo"]

    def test_por_posicao_usa_o_ou_de_base_e_cargo_extra(self):
        uc = _resolver(por_posicao=[BIA, CAIO])

        r = uc.execute(FiltroComunicado(segmento="por_posicao", posicoes=["coordenador", "gerente"]))

        assert [d["usuario_id"] for d in r["destinatarios"]] == [BIA.id, CAIO.id]

    def test_todos_e_manual(self):
        uc = _resolver()

        todos = uc.execute(FiltroComunicado(segmento="todos"))
        manual = uc.execute(FiltroComunicado(segmento="manual", usuario_ids=[CAIO.id, ANA.id]))

        assert [d["usuario_id"] for d in todos["destinatarios"]] == [ANA.id, BIA.id, CAIO.id]
        # Ordenado por nome, nao pela ordem dos ids pedidos.
        assert [d["usuario_id"] for d in manual["destinatarios"]] == [ANA.id, CAIO.id]


class TestPendentesDoPdi:
    def _mundo(self):
        from datetime import date

        pastas = [
            SimpleNamespace(id=1, nome="Encontro 1", prazo=date(2026, 9, 30)),
            SimpleNamespace(id=2, nome="Encontro 2", prazo=date(2026, 10, 20)),
            SimpleNamespace(id=3, nome="Encontro 3", prazo=date(2026, 11, 20)),
        ]
        pend = {
            "pasta_id": 2,
            "pessoas": [
                {"mentorado_id": ANA.id, "mentorado_nome": "Ana", "mentor_id": CAIO.id, "mentor_nome": "Caio",
                 "itens": [{"item_id": 1, "item_nome": "Planilha", "status": "pendente"}, {"item_id": 2, "item_nome": "Foto", "status": "pendente"}]},
                {"mentorado_id": BIA.id, "mentorado_nome": "Bia", "mentor_id": CAIO.id, "mentor_nome": "Caio",
                 "itens": [{"item_id": 1, "item_nome": "Planilha", "status": "atrasado"}]},
            ],
        }
        return pastas, pend

    def test_mentorado_e_mentor_de_quem_nao_enviou(self):
        pastas, pend = self._mundo()
        uc = _resolver(pastas_pdi=pastas, pendencias_pdi=pend)

        r = uc.execute(FiltroComunicado(segmento="pendentes_do_pdi", pasta_pdi_id=2))

        por_id = {d["usuario_id"]: d for d in r["destinatarios"]}
        assert set(por_id) == {ANA.id, CAIO.id}, "Bia entregou atrasado: já entregou"
        assert por_id[ANA.id]["detalhe"] == "2 itens pendentes"
        assert por_id[CAIO.id]["detalhe"] == "mentor de Ana"
        assert 'Encontro 2' in r["rotulo"] and "20/10" in r["rotulo"]

    def test_sem_pasta_escolhida_usa_a_mais_proxima(self, monkeypatch):
        import src.use_cases.comunicado.enviar_comunicado as mod
        from datetime import date as _date

        class Hoje(_date):
            @classmethod
            def today(cls):
                return _date(2026, 10, 13)

        monkeypatch.setattr(mod, "date", Hoje)
        pastas, pend = self._mundo()
        pedidas = []
        uc = _resolver(pastas_pdi=pastas, pendencias_pdi=pend)
        uc.pendencias_pdi_use_case = SimpleNamespace(execute=lambda pasta_id: pedidas.append(pasta_id) or pend)

        uc.execute(FiltroComunicado(segmento="pendentes_do_pdi"))

        assert pedidas == [2], "a mais próxima ainda não vencida"

    def test_sem_pasta_cadastrada_recusa(self):
        with pytest.raises(RegraDeNegocioError):
            _resolver(pastas_pdi=[]).execute(FiltroComunicado(segmento="pendentes_do_pdi"))


class TestFiltrosComuns:
    def test_desligado_nunca_recebe_mesmo_constando_no_recorte(self):
        banca = SimpleNamespace(id=3, nome_projeto="ALFA")
        uc = _resolver(
            ativos=[ANA],
            banca=banca,
            candidaturas=[SimpleNamespace(usuario_id=ANA.id, confirmado=True), SimpleNamespace(usuario_id=DESLIGADO.id, confirmado=True)],
        )

        r = uc.execute(FiltroComunicado(segmento="inscritos_da_banca", banca_id=3))

        assert [d["usuario_id"] for d in r["destinatarios"]] == [ANA.id]

    def test_excluir_ids_tira_quem_foi_desmarcado_na_previa(self):
        uc = _resolver()

        r = uc.execute(FiltroComunicado(segmento="todos", excluir_ids=[BIA.id]))

        assert [d["usuario_id"] for d in r["destinatarios"]] == [ANA.id, CAIO.id]

    def test_duplicata_no_recorte_vira_uma_pessoa(self):
        banca = SimpleNamespace(id=3, nome_projeto="ALFA")
        uc = _resolver(
            banca=banca,
            candidaturas=[SimpleNamespace(usuario_id=ANA.id, confirmado=True)] * 2,
        )

        r = uc.execute(FiltroComunicado(segmento="inscritos_da_banca", banca_id=3))

        assert len(r["destinatarios"]) == 1


class TestEnviar:
    def _enviar(self, monkeypatch, resolver):
        chamadas = []

        def registrar_varios_fake(db, usuario_ids, **kwargs):
            chamadas.append((list(usuario_ids), kwargs))

        monkeypatch.setattr(mod, "registrar_varios", registrar_varios_fake)
        uc = EnviarComunicadoUseCase.__new__(EnviarComunicadoUseCase)
        uc.db = None
        uc.resolver = resolver
        return uc, chamadas

    def test_dispara_um_tipo_comunicado_com_a_mesma_chave_pra_todos(self, monkeypatch):
        uc, chamadas = self._enviar(monkeypatch, _resolver())

        r = uc.execute(ComunicadoRequest(segmento="todos", assunto="  Reunião geral  ", mensagem="Sexta às 18h.\nTraga dúvidas."), DIRETOR)

        assert r["enviados"] == 3
        (ids, kwargs), = chamadas
        assert ids == [ANA.id, BIA.id, CAIO.id]
        assert kwargs["tipo"] == "comunicado"
        assert kwargs["titulo"] == "Reunião geral"
        assert kwargs["corpo"] == "Sexta às 18h.\nTraga dúvidas.\n\nEnviado por Diretor."
        assert kwargs["chave_dedup"] == f"comunicado:{r['comunicado_id']}"
        assert kwargs["payload"]["remetente_id"] == DIRETOR.id
        assert kwargs["payload"]["segmento"] == "todos"

    def test_dois_envios_iguais_ganham_chaves_diferentes(self, monkeypatch):
        uc, chamadas = self._enviar(monkeypatch, _resolver())
        pedido = ComunicadoRequest(segmento="todos", assunto="A", mensagem="B")

        uc.execute(pedido, DIRETOR)
        uc.execute(pedido, DIRETOR)

        assert chamadas[0][1]["chave_dedup"] != chamadas[1][1]["chave_dedup"]

    def test_sem_destinatario_recusa_e_nao_registra(self, monkeypatch):
        uc, chamadas = self._enviar(monkeypatch, _resolver(carga=[carga(ANA, 2)]))

        with pytest.raises(RegraDeNegocioError):
            uc.execute(ComunicadoRequest(segmento="zero_bancas", assunto="A", mensagem="B"), DIRETOR)

        assert chamadas == []

    def test_assunto_so_de_espaco_recusa(self, monkeypatch):
        uc, chamadas = self._enviar(monkeypatch, _resolver())

        with pytest.raises(RegraDeNegocioError):
            uc.execute(ComunicadoRequest(segmento="todos", assunto="   ", mensagem="B"), DIRETOR)

        assert chamadas == []


def test_comunicado_fica_fora_dos_tipos_opcionais():
    """So o desligamento total de e-mail silencia um comunicado."""
    from src.models.notificacao_model import TIPO_NOTIFICACAO_ENUM, TIPOS_NOTIFICACAO_OPCIONAIS

    assert "comunicado" in TIPO_NOTIFICACAO_ENUM.enums
    assert "comunicado" not in TIPOS_NOTIFICACAO_OPCIONAIS


class TestHistorico:
    def _uc(self, linhas):
        from src.use_cases.comunicado.enviar_comunicado import ListarComunicadosUseCase

        uc = ListarComunicadosUseCase.__new__(ListarComunicadosUseCase)
        uc.notificacao_repository = SimpleNamespace(get_por_tipo=lambda tipo: list(linhas))
        uc.usuario_repository = SimpleNamespace(get_all=lambda: [ANA, BIA, CAIO, DIRETOR])
        return uc

    def _linha(self, cid, usuario, quando, email=False, lida=False, titulo="Aviso"):
        from datetime import datetime

        return SimpleNamespace(
            usuario_id=usuario.id,
            titulo=titulo,
            corpo="Texto\n\nEnviado por Diretor.",
            criado_em=datetime(2026, 10, 12, 10, quando),
            email_enviado_em=datetime(2026, 10, 12, 10, quando) if email else None,
            lida_em=datetime(2026, 10, 12, 11, 0) if lida else None,
            payload={"comunicado_id": cid, "remetente_id": DIRETOR.id, "rotulo": "Todo mundo ativo"},
        )

    def test_agrupa_por_disparo_e_conta_email_e_leitura(self):
        uc = self._uc([
            self._linha("a", ANA, 1, email=True, lida=True),
            self._linha("a", BIA, 1, email=True),
            self._linha("a", CAIO, 1),
            self._linha("b", ANA, 30, titulo="Outro"),
        ])

        recente, antigo = uc.execute()

        assert recente["comunicado_id"] == "b" and recente["total"] == 1
        assert antigo["total"] == 3
        assert antigo["emails_enviados"] == 2
        assert antigo["lidas"] == 1
        assert [d["nome"] for d in antigo["destinatarios"]] == ["Ana", "Bia", "Caio"]
        ana = antigo["destinatarios"][0]
        assert ana == {"usuario_id": ANA.id, "nome": "Ana", "email": "ana@x.com", "email_enviado": True, "lida": True}
        assert antigo["destinatarios"][2]["email_enviado"] is False
        # Disparo antigo sem `remetente_nome` no payload resolve pelo id.
        assert antigo["remetente_nome"] == "Diretor"

    def test_linha_sem_comunicado_id_fica_de_fora(self):
        linha = self._linha("a", ANA, 1)
        linha.payload = {}

        assert self._uc([linha]).execute() == []


class TestApagar:
    def test_apaga_so_as_linhas_do_comunicado(self):
        from src.use_cases.comunicado.enviar_comunicado import ApagarComunicadoUseCase

        linhas = [
            SimpleNamespace(id=1, payload={"comunicado_id": "a"}),
            SimpleNamespace(id=2, payload={"comunicado_id": "a"}),
            SimpleNamespace(id=3, payload={"comunicado_id": "b"}),
        ]
        apagadas = []
        uc = ApagarComunicadoUseCase.__new__(ApagarComunicadoUseCase)
        uc.notificacao_repository = SimpleNamespace(get_por_tipo=lambda tipo: linhas)
        uc.db = SimpleNamespace(delete=lambda linha: apagadas.append(linha.id), commit=lambda: None)

        assert uc.execute("a") == 2
        assert apagadas == [1, 2]

    def test_comunicado_que_nao_existe_recusa(self):
        from src.use_cases.comunicado.enviar_comunicado import ApagarComunicadoUseCase

        uc = ApagarComunicadoUseCase.__new__(ApagarComunicadoUseCase)
        uc.notificacao_repository = SimpleNamespace(get_por_tipo=lambda tipo: [])
        uc.db = None

        with pytest.raises(RegraDeNegocioError):
            uc.execute("x")

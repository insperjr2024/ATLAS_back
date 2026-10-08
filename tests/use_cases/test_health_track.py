"""Health Track §2 e §3 — pilares e avaliação por projeto + pilar + data.

**Os dois contratos que a etapa seguinte (status geral, persistência) vai
assumir:** os pilares vêm do banco — desativar um muda o que é cobrado sem
mudar código — e avaliar de novo nunca apaga a cor anterior.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401 — registra todos os models no metadata
from src.database.database import Base
from src.models.health_track_avaliacao_model import HealthTrackAvaliacaoModel
from src.models.health_track_pilar_model import HealthTrackPilarModel
from src.models.health_track_regra_model import HealthTrackRegraModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.health_track.get_avaliacao_atual import GetAvaliacaoAtualUseCase
from src.use_cases.health_track.get_ciclos import GetCiclosUseCase
from src.use_cases.health_track.get_historico import GetHistoricoUseCase
from src.use_cases.health_track.listar_classificacoes import ListarClassificacoesUseCase
from src.use_cases.health_track.listar_pilares import ListarPilaresUseCase
from src.use_cases.health_track import registrar_avaliacao as registrar
from src.use_cases.health_track.registrar_avaliacao import (
    RegistrarAvaliacaoRequest,
    RegistrarAvaliacaoUseCase,
)
from src.models.health_track_rodada_model import HealthTrackRodadaModel, HealthTrackRodadaProjetoModel
from src.use_cases.health_track import update_regra as editar_regra
from src.use_cases.health_track.get_regra import GetHistoricoRegraUseCase, GetRegraUseCase
from src.use_cases.health_track.update_regra import UpdateRegraRequest, UpdateRegraUseCase
from src.utils.exceptions import RegraDeNegocioError

PROJETO = 10

NOMES = ["Cronograma & Prazos", "Cliente", "Escopo", "Qualidade", "Equipe", "Desenvolvimento"]


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            UsuarioModel.__table__,
            HealthTrackPilarModel.__table__,
            HealthTrackAvaliacaoModel.__table__,
            HealthTrackRegraModel.__table__,
            # O registro de avaliação consulta a rodada aberta.
            HealthTrackRodadaModel.__table__,
            HealthTrackRodadaProjetoModel.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    s.add(UsuarioModel(id=1, nome="Gerente", email_insper="g@insper.edu.br", senha_hash="x", posicao="gerente"))
    for ordem, nome in enumerate(NOMES):
        s.add(HealthTrackPilarModel(nome=nome, ordem=ordem, ativo=True))
    # A regra inicial, como a migration semeia.
    s.add(HealthTrackRegraModel(
        verde_max_amarelos=1, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1,
        vigente_desde=datetime(2000, 1, 1),
    ))
    s.commit()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def relogio(monkeypatch):
    """Controla o "agora" de preenchimentos e edições de regra — dois eventos
    no mesmo teste precisam de instantes diferentes para a ordem ter sentido."""
    instantes = []

    def _proximo(dt: datetime):
        instantes.append(dt)
        monkeypatch.setattr(registrar, "agora_utc", lambda: dt)
        monkeypatch.setattr(editar_regra, "agora_utc", lambda: dt)

    return _proximo


QUEM = SimpleNamespace(id=1, posicao="gerente")


def pilares(db):
    return {p.nome: p for p in db.query(HealthTrackPilarModel).all()}


def preenchimento(db, **cores):
    """Todos os pilares ativos verdes, salvo os que o teste mudar por nome
    curto (`Cliente="vermelho"`)."""
    ativos = ListarPilaresUseCase(db).execute()
    return RegistrarAvaliacaoRequest(
        avaliacoes=[
            {"pilar_id": p["id"], "cor": cores.get(p["nome"].split()[0], "verde")}
            for p in ativos
        ]
    )


class TestPilares:
    def test_lista_os_ativos_na_ordem_de_exibicao(self, db):
        assert [p["nome"] for p in ListarPilaresUseCase(db).execute()] == NOMES

    def test_pilar_desativado_some_da_lista(self, db):
        pilares(db)["Equipe"].ativo = False
        db.commit()

        assert "Equipe" not in [p["nome"] for p in ListarPilaresUseCase(db).execute()]

    def test_ordem_vem_do_banco_nao_do_codigo(self, db):
        """A diretoria vai reordenar (§18): a lista segue o campo, não a
        ordem de criação."""
        pilares(db)["Desenvolvimento"].ordem = -1
        db.commit()

        assert ListarPilaresUseCase(db).execute()[0]["nome"] == "Desenvolvimento"


class TestClassificacoes:
    def test_tres_cores_do_mais_saudavel_ao_mais_critico(self):
        classificacoes = ListarClassificacoesUseCase().execute()

        assert [(c["cor"], c["nome"]) for c in classificacoes] == [
            ("verde", "Saudável"),
            ("amarelo", "Atenção"),
            ("vermelho", "Crítico"),
        ]
        assert all(c["descricao"] for c in classificacoes)

    def test_toda_cor_listada_e_aceita_no_preenchimento(self):
        """A lista que a tela mostra e o que a API aceita saem da mesma
        constante — não dá para uma cor aparecer na tela e ser recusada."""
        for c in ListarClassificacoesUseCase().execute():
            RegistrarAvaliacaoRequest(avaliacoes=[{"pilar_id": 1, "cor": c["cor"]}])

    def test_alterar_a_resposta_nao_altera_a_constante(self):
        ListarClassificacoesUseCase().execute()[0]["nome"] = "Outro"

        assert ListarClassificacoesUseCase().execute()[0]["nome"] == "Saudável"


class TestRegistrar:
    def test_grava_uma_linha_por_pilar_com_o_mesmo_instante(self, db, relogio):
        relogio(datetime(2026, 10, 1, 12))

        criadas = RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="amarelo"), QUEM)

        assert len(criadas) == 6
        assert {c["avaliado_em"] for c in criadas} == {datetime(2026, 10, 1, 12)}
        assert {c["avaliado_por"] for c in criadas} == {1}
        assert next(c for c in criadas if c["pilar_nome"] == "Cliente")["cor"] == "amarelo"

    def test_volta_na_ordem_de_exibicao(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        request = preenchimento(db)
        request.avaliacoes.reverse()

        criadas = RegistrarAvaliacaoUseCase(db).execute(PROJETO, request, QUEM)

        assert [c["pilar_nome"] for c in criadas] == NOMES

    def test_faltar_pilar_recusa_e_nao_grava_nada(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        request = preenchimento(db)
        request.avaliacoes.pop()  # sem Desenvolvimento

        with pytest.raises(RegraDeNegocioError, match="Desenvolvimento"):
            RegistrarAvaliacaoUseCase(db).execute(PROJETO, request, QUEM)
        assert db.query(HealthTrackAvaliacaoModel).count() == 0

    def test_pilar_repetido_recusa(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        request = preenchimento(db)
        request.avaliacoes.append(request.avaliacoes[0])

        with pytest.raises(RegraDeNegocioError, match="mais de uma vez"):
            RegistrarAvaliacaoUseCase(db).execute(PROJETO, request, QUEM)

    def test_pilar_desativado_nao_e_aceito_nem_cobrado(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        com_equipe = preenchimento(db)
        pilares(db)["Equipe"].ativo = False
        db.commit()

        with pytest.raises(RegraDeNegocioError, match="desativado"):
            RegistrarAvaliacaoUseCase(db).execute(PROJETO, com_equipe, QUEM)

        # Sem Equipe, os 5 restantes bastam.
        criadas = RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)
        assert len(criadas) == 5

    def test_pilar_inexistente_recusa(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        request = preenchimento(db)
        request.avaliacoes[0].pilar_id = 999

        with pytest.raises(RegraDeNegocioError, match="999"):
            RegistrarAvaliacaoUseCase(db).execute(PROJETO, request, QUEM)

    def test_cor_fora_das_tres_e_recusada_na_entrada(self):
        with pytest.raises(ValueError):
            RegistrarAvaliacaoRequest(avaliacoes=[{"pilar_id": 1, "cor": "azul"}])

    def test_comentario_em_branco_vira_nulo(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        request = preenchimento(db)
        request.avaliacoes[0].comentario = "   "
        request.avaliacoes[1].comentario = " Cliente sumiu "

        criadas = RegistrarAvaliacaoUseCase(db).execute(PROJETO, request, QUEM)

        assert criadas[0]["comentario"] is None
        assert criadas[1]["comentario"] == "Cliente sumiu"


class TestHistoricoNuncaSobrescreve:
    def test_segundo_preenchimento_soma_linhas(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)
        relogio(datetime(2026, 10, 8))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cronograma="vermelho"), QUEM)

        assert db.query(HealthTrackAvaliacaoModel).count() == 12

    def test_atual_pega_o_ultimo_preenchimento(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cronograma="amarelo"), QUEM)
        relogio(datetime(2026, 10, 8))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cronograma="vermelho"), QUEM)

        atual = {i["pilar"]["nome"]: i["avaliacao"] for i in GetAvaliacaoAtualUseCase(db).execute(PROJETO)["pilares"]}

        assert atual["Cronograma & Prazos"]["cor"] == "vermelho"
        assert atual["Cronograma & Prazos"]["avaliado_em"] == datetime(2026, 10, 8)

    def test_atual_sem_avaliacao_devolve_pilares_vazios(self, db):
        atual = GetAvaliacaoAtualUseCase(db).execute(PROJETO)["pilares"]

        assert [i["pilar"]["nome"] for i in atual] == NOMES
        assert all(i["avaliacao"] is None for i in atual)

    def test_atual_nao_mistura_projetos(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO + 1, preenchimento(db), QUEM)

        assert all(i["avaliacao"] is None for i in GetAvaliacaoAtualUseCase(db).execute(PROJETO)["pilares"])

    def test_historico_do_mais_novo_para_o_mais_antigo(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)
        relogio(datetime(2026, 10, 8))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)

        datas = [h["avaliado_em"] for h in GetHistoricoUseCase(db).execute(PROJETO)]

        assert datas == sorted(datas, reverse=True)
        assert len(datas) == 12

    def test_historico_filtrado_por_pilar(self, db, relogio):
        cliente = pilares(db)["Cliente"].id
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="amarelo"), QUEM)
        relogio(datetime(2026, 10, 8))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="vermelho"), QUEM)

        historico = GetHistoricoUseCase(db).execute(PROJETO, pilar_id=cliente)

        assert [h["cor"] for h in historico] == ["vermelho", "amarelo"]

    def test_pilar_desativado_continua_no_historico(self, db, relogio):
        """O histórico é o que foi avaliado na época — desativar o pilar
        depois não apaga o passado, mas ele sai da avaliação atual."""
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)
        pilares(db)["Equipe"].ativo = False
        db.commit()

        historico = GetHistoricoUseCase(db).execute(PROJETO)
        atual = GetAvaliacaoAtualUseCase(db).execute(PROJETO)["pilares"]

        assert "Equipe" in {h["pilar_nome"] for h in historico}
        assert "Equipe" not in {i["pilar"]["nome"] for i in atual}


class TestStatusGeral:
    """O §4 por cima do histórico: o status sai das cores, na leitura."""

    def test_atual_traz_o_status_do_ultimo_preenchimento(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="amarelo", Escopo="amarelo"), QUEM)

        status = GetAvaliacaoAtualUseCase(db).execute(PROJETO)["status_geral"]

        assert status == {"na_epoca": "amarelo", "pela_regra_atual": "amarelo", "avaliado_em": datetime(2026, 10, 1)}

    def test_atual_sem_avaliacao_nao_tem_status(self, db):
        assert GetAvaliacaoAtualUseCase(db).execute(PROJETO)["status_geral"] is None

    def test_pilar_ativado_depois_deixa_o_status_nulo(self, db, relogio):
        """O pilar novo ainda não tem cor: o status esperaria o próximo
        preenchimento em vez de sair verde com um pilar em branco."""
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)
        db.add(HealthTrackPilarModel(nome="Financeiro", ordem=9, ativo=True))
        db.commit()

        assert GetAvaliacaoAtualUseCase(db).execute(PROJETO)["status_geral"] is None

    def test_pilar_desativado_sai_da_conta_do_status_atual(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Equipe="vermelho"), QUEM)
        pilares(db)["Equipe"].ativo = False
        db.commit()

        assert GetAvaliacaoAtualUseCase(db).execute(PROJETO)["status_geral"]["na_epoca"] == "verde"


class TestCiclos:
    def test_um_ciclo_por_preenchimento_do_mais_novo_ao_mais_antigo(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)
        relogio(datetime(2026, 10, 8))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cronograma="vermelho"), QUEM)

        ciclos = GetCiclosUseCase(db).execute(PROJETO)

        assert [c["avaliado_em"] for c in ciclos] == [datetime(2026, 10, 8), datetime(2026, 10, 1)]
        assert [c["status_geral"]["na_epoca"] for c in ciclos] == ["vermelho", "verde"]
        assert [len(c["avaliacoes"]) for c in ciclos] == [6, 6]
        assert ciclos[0]["avaliado_por_nome"] == "Gerente"

    def test_pilares_do_ciclo_na_ordem_de_exibicao(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db), QUEM)

        assert [a["pilar_nome"] for a in GetCiclosUseCase(db).execute(PROJETO)[0]["avaliacoes"]] == NOMES

    def test_ciclo_antigo_mostra_a_regra_da_epoca_e_a_atual(self, db, relogio):
        """A diretoria apertou o verde depois do ciclo: ele continua verde
        "na época", e a tela pode avisar que hoje seria amarelo. O ciclo de
        depois da mudança já nasce amarelo nas duas."""
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="amarelo"), QUEM)
        relogio(datetime(2026, 11, 1))
        UpdateRegraUseCase(db).execute(regra(verde_max_amarelos=0), DIRETOR)
        relogio(datetime(2026, 11, 8))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="amarelo"), QUEM)

        novo, antigo = [c["status_geral"] for c in GetCiclosUseCase(db).execute(PROJETO)]

        assert antigo == {"na_epoca": "verde", "pela_regra_atual": "amarelo"}
        assert novo == {"na_epoca": "amarelo", "pela_regra_atual": "amarelo"}

    def test_status_atual_tambem_usa_as_duas_reguas(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO, preenchimento(db, Cliente="amarelo"), QUEM)
        relogio(datetime(2026, 11, 1))
        UpdateRegraUseCase(db).execute(regra(verde_max_amarelos=0), DIRETOR)

        status = GetAvaliacaoAtualUseCase(db).execute(PROJETO)["status_geral"]

        assert (status["na_epoca"], status["pela_regra_atual"]) == ("verde", "amarelo")

    def test_ciclos_nao_misturam_projetos(self, db, relogio):
        relogio(datetime(2026, 10, 1))
        RegistrarAvaliacaoUseCase(db).execute(PROJETO + 1, preenchimento(db), QUEM)

        assert GetCiclosUseCase(db).execute(PROJETO) == []


DIRETOR = SimpleNamespace(id=1, posicao="diretor_projetos")


def regra(**mudancas):
    """A regra inicial com o que o teste mudar."""
    valores = dict(verde_max_amarelos=1, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1)
    valores.update(mudancas)
    return UpdateRegraRequest(**valores)


class TestRegraEditavel:
    """§5: a regra sai do banco, e editar cria versão nova."""

    def test_regra_inicial_com_o_amarelo_calculado(self, db):
        atual = GetRegraUseCase(db).execute()

        assert atual["verde"] == {"max_amarelos": 1, "max_vermelhos": 0}
        assert atual["amarelo"] == {"min_amarelos": 2, "max_amarelos": 2, "max_vermelhos": 0}
        assert atual["vermelho"] == {"min_amarelos": 3, "min_vermelhos": 1}
        assert atual["criado_por_nome"] is None  # veio da migration

    def test_editar_cria_versao_nova_e_preserva_a_anterior(self, db, relogio):
        relogio(datetime(2026, 11, 1))

        UpdateRegraUseCase(db).execute(regra(verde_max_amarelos=0), DIRETOR)

        historico = GetHistoricoRegraUseCase(db).execute()
        assert [v["verde"]["max_amarelos"] for v in historico] == [0, 1]  # mais nova primeiro
        assert historico[0]["vigente_desde"] == datetime(2026, 11, 1)
        assert historico[0]["criado_por_nome"] == "Gerente"  # o usuário 1 do fixture
        assert GetRegraUseCase(db).execute()["verde"]["max_amarelos"] == 0

    def test_salvar_sem_mudar_nada_nao_cria_versao(self, db, relogio):
        relogio(datetime(2026, 11, 1))

        UpdateRegraUseCase(db).execute(regra(), DIRETOR)

        assert len(GetHistoricoRegraUseCase(db).execute()) == 1

    @pytest.mark.parametrize(
        "mudancas,trecho",
        [
            (dict(verde_max_amarelos=3), "amarelos"),       # verde alcança o mínimo do vermelho
            (dict(verde_max_vermelhos=1), "vermelhos"),
        ],
    )
    def test_verde_que_encosta_no_vermelho_e_recusado(self, db, relogio, mudancas, trecho):
        relogio(datetime(2026, 11, 1))

        with pytest.raises(RegraDeNegocioError, match=trecho):
            UpdateRegraUseCase(db).execute(regra(**mudancas), DIRETOR)
        assert len(GetHistoricoRegraUseCase(db).execute()) == 1

    @pytest.mark.parametrize(
        "mudancas",
        [
            dict(vermelho_min_vermelhos=0),   # todo projeto seria vermelho
            dict(vermelho_min_amarelos=0),
            dict(verde_max_amarelos=-1),
        ],
    )
    def test_valores_fora_do_intervalo_recusados_na_entrada(self, mudancas):
        with pytest.raises(ValueError):
            regra(**mudancas)

    def test_faixa_do_amarelo_acompanha_a_edicao(self, db, relogio):
        relogio(datetime(2026, 11, 1))

        UpdateRegraUseCase(db).execute(regra(verde_max_amarelos=0, vermelho_min_amarelos=4), DIRETOR)

        assert GetRegraUseCase(db).execute()["amarelo"] == {"min_amarelos": 1, "max_amarelos": 3, "max_vermelhos": 0}

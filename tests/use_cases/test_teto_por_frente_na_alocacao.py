"""§8 — os TETOS por frente passam a valer na hora de alocar (2026-09-02).

⭐ O que estes testes protegem: os "Máx. membros" e "Máx. liderança" da tela de
Configurações eram, até aqui, números guardados que nada consultava. Quem
segurava a banca era só o teto GLOBAL (`configuracao.vagas_por_banca`), que não
sabe de frente nenhuma — a banca de Business + Direito podia fechar com seis
pessoas de Business.

⚠ Isto NÃO é a volta da exigência por frente no registro da banca (removida em
2026-08-12 porque travava banca que já tinha acontecido). Aqui a porta é a
ALOCAÇÃO, que é antes: recusar é dizer "escolha outra banca".

Mesmo padrão dos vizinhos: `__new__` + repositórios fake, sem sessão de banco.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.configuracao import composicao_banca as composicao_mod
from src.use_cases.candidatura.create_candidatura import (
    CreateCandidaturaRequest,
    CreateCandidaturaUseCase,
)
from src.utils import composicao_banca as checker_mod
from src.utils.exceptions import RegraDeNegocioError

BUSINESS, TECH = 1, 2


def usuario(id, posicao="consultor"):
    return SimpleNamespace(id=id, posicao=posicao)


def frente(id, nome, piso_banca=1):
    return SimpleNamespace(id=id, nome=nome, piso_banca=piso_banca, ativa=True)


def regra_gravada(frente_id, min_membros=1, max_membros=99, min_lideranca=1, max_lideranca=99):
    return SimpleNamespace(
        frente_id=frente_id,
        min_membros=min_membros,
        max_membros=max_membros,
        min_lideranca=min_lideranca,
        max_lideranca=max_lideranca,
    )


def montar(
    monkeypatch,
    *,
    frente_ids,
    frentes,
    por_frente,
    usuarios,
    gravadas=None,
    alocados=(),
    vagas=10,
):
    """Um `CreateCandidaturaUseCase` sem banco, com a matriz que se pedir.

    `gravadas` vazio = combinação não configurada, que é o padrão `SEM_TETO` —
    o caso que precisa continuar passando.
    """

    class FakeRegraRepo:
        def __init__(self, db):
            pass

        def get_por_frente(self, _combinacao):
            return {r.frente_id: r for r in (gravadas or [])}

    class FakeFrenteRepoTodas:
        def __init__(self, db):
            pass

        def get_all(self):
            return list(frentes.values())

    class FakeConfigRepoResolver:
        def __init__(self, db):
            pass

        def get(self):
            return SimpleNamespace(lideranca_minima_por_frente=1, vagas_por_banca=vagas)

    class FakeUsuarioFrenteRepo:
        def __init__(self, db):
            pass

        def get_by_frente(self, frente_id):
            return [SimpleNamespace(usuario_id=uid) for uid in por_frente.get(frente_id, [])]

    class FakeUsuarioRepo:
        def __init__(self, db):
            pass

        def get_all(self):
            return usuarios

    class FakeEquipeProjetoRepo:
        def __init__(self, db=None):
            pass

        def get_by_banca(self, _banca_id):
            return []

    monkeypatch.setattr(composicao_mod, "BancaComposicaoRegraRepository", FakeRegraRepo)
    monkeypatch.setattr(composicao_mod, "FrenteRepository", FakeFrenteRepoTodas)
    monkeypatch.setattr(composicao_mod, "ConfiguracaoRepository", FakeConfigRepoResolver)
    monkeypatch.setattr(checker_mod, "UsuarioFrenteRepository", FakeUsuarioFrenteRepo)
    monkeypatch.setattr(checker_mod, "UsuarioRepository", FakeUsuarioRepo)
    monkeypatch.setattr(checker_mod, "EquipeProjetoRepository", FakeEquipeProjetoRepo)

    class FakeCandidaturaRepo:
        def __init__(self):
            self.criadas = []

        def get_by_banca(self, _banca_id):
            return [SimpleNamespace(usuario_id=uid) for uid in alocados]

        def create(self, **kwargs):
            self.criadas.append(kwargs["usuario_id"])
            return SimpleNamespace(id=1, **kwargs)

    banca = SimpleNamespace(
        id=1,
        nome_projeto="BLEND I",
        data_hora=datetime.now() + timedelta(days=3),
        realizado_em=None,
        coordenador_id=None,
    )

    uc = CreateCandidaturaUseCase.__new__(CreateCandidaturaUseCase)
    uc.db = None
    candidatura_repo = FakeCandidaturaRepo()
    uc.repository = candidatura_repo
    uc.banca_repository = SimpleNamespace(get_by_id=lambda _id: banca)
    uc.configuracao_repository = SimpleNamespace(
        get=lambda: SimpleNamespace(vagas_por_banca=vagas)
    )
    uc.banca_frente_repository = SimpleNamespace(
        get_by_banca=lambda _id: [SimpleNamespace(frente_id=fid) for fid in frente_ids]
    )
    uc.frente_repository = SimpleNamespace(get_by_id=lambda fid: frentes.get(fid))
    # A banca destes testes não cobre escopo nenhum: o assunto é a frente de
    # quem se aloca, e `membros_da_banca` sem escopo devolve só o coordenador.
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _id: [])
    uc.escopo_repository = SimpleNamespace(get_by_id=lambda _id: None)
    uc.membro_repository = SimpleNamespace(get_by_projeto=lambda *a, **k: [])
    uc.equipe_projeto_repository = SimpleNamespace(get_by_banca=lambda _id: [])
    uc.vendedor_repository = SimpleNamespace(get_by_projeto=lambda *a, **k: [])
    return uc, candidatura_repo


def alocar(uc, usuario_id):
    return uc.execute(CreateCandidaturaRequest(banca_id=1), usuario_id=usuario_id)


class TestOTetoDaFrente:
    def test_recusa_quem_estoura_o_maximo_da_propria_frente(self, monkeypatch):
        """O caso que o teto global não pega: cabem 10 na banca, mas Business
        já tem os 3 que a diretoria configurou."""
        uc, _ = montar(
            monkeypatch,
            frente_ids=[BUSINESS],
            frentes={BUSINESS: frente(BUSINESS, "Business", 3)},
            por_frente={BUSINESS: [10, 11, 12, 13]},
            usuarios=[usuario(i) for i in (10, 11, 12, 13)],
            gravadas=[regra_gravada(BUSINESS, min_membros=3, max_membros=3, min_lideranca=0)],
            alocados=(10, 11, 12),
        )

        with pytest.raises(RegraDeNegocioError) as erro:
            alocar(uc, 13)

        assert "Business" in str(erro.value)

    def test_quem_nao_e_da_frente_cheia_continua_entrando(self, monkeypatch):
        """O teto é DA FRENTE. Business lotado não fecha a banca para Tech —
        fechar seria o teto global, que já existe e é outro número."""
        uc, candidaturas = montar(
            monkeypatch,
            frente_ids=[BUSINESS, TECH],
            frentes={
                BUSINESS: frente(BUSINESS, "Business", 3),
                TECH: frente(TECH, "Tech", 2),
            },
            por_frente={BUSINESS: [10, 11, 12], TECH: [20]},
            usuarios=[usuario(i) for i in (10, 11, 12, 20)],
            gravadas=[
                regra_gravada(BUSINESS, min_membros=3, max_membros=3, min_lideranca=0),
                regra_gravada(TECH, min_membros=2, max_membros=2, min_lideranca=0),
            ],
            alocados=(10, 11, 12),
        )

        alocar(uc, 20)

        assert candidaturas.criadas == [20]

    def test_combinacao_sem_configuracao_nao_barra_ninguem(self, monkeypatch):
        """⭐ A garantia de que ligar isto não mexeu em base nenhuma: sem linha
        gravada, a regra cai em `SEM_TETO` e o comportamento é o de sempre."""
        uc, candidaturas = montar(
            monkeypatch,
            frente_ids=[BUSINESS],
            frentes={BUSINESS: frente(BUSINESS, "Business", 3)},
            por_frente={BUSINESS: list(range(10, 20))},
            usuarios=[usuario(i) for i in range(10, 20)],
            gravadas=[],
            alocados=(10, 11, 12, 13, 14),
        )

        alocar(uc, 15)

        assert candidaturas.criadas == [15]

    def test_lideranca_tem_teto_proprio(self, monkeypatch):
        """A banca é para avaliar, não para reunir a gestão inteira: o segundo
        gerente de Business não entra onde a liderança está limitada a 1."""
        uc, _ = montar(
            monkeypatch,
            frente_ids=[BUSINESS],
            frentes={BUSINESS: frente(BUSINESS, "Business", 3)},
            por_frente={BUSINESS: [10, 11]},
            usuarios=[usuario(10, "gerente"), usuario(11, "gerente")],
            gravadas=[
                regra_gravada(
                    BUSINESS, min_membros=1, max_membros=9, min_lideranca=1, max_lideranca=1
                )
            ],
            alocados=(10,),
        )

        with pytest.raises(RegraDeNegocioError) as erro:
            alocar(uc, 11)

        assert "liderança" in str(erro.value)


class TestOQueONovoAlocadoNaoPiora:
    def test_banca_ja_acima_do_teto_nao_trava_outra_frente(self, monkeypatch):
        """A diretoria apertou o número depois de a banca encher. Recusar
        todo mundo aqui deixaria a banca presa: o jeito de cobrir a frente que
        falta é justamente alocar mais gente."""
        uc, candidaturas = montar(
            monkeypatch,
            frente_ids=[BUSINESS, TECH],
            frentes={
                BUSINESS: frente(BUSINESS, "Business", 3),
                TECH: frente(TECH, "Tech", 2),
            },
            por_frente={BUSINESS: [10, 11, 12, 13], TECH: [20]},
            usuarios=[usuario(i) for i in (10, 11, 12, 13, 20)],
            # Business já tem 4 com teto 2 — quatro pessoas alocadas antes de
            # o teto virar 2.
            gravadas=[
                regra_gravada(BUSINESS, min_membros=1, max_membros=2, min_lideranca=0),
                regra_gravada(TECH, min_membros=1, max_membros=2, min_lideranca=0),
            ],
            alocados=(10, 11, 12, 13),
        )

        alocar(uc, 20)

        assert candidaturas.criadas == [20]

    def test_banca_legada_sem_frente_vinculada_passa(self, monkeypatch):
        """Sem frente não há combinação, e sem combinação não há regra. Quem
        segura essa banca continua sendo o teto global."""
        uc, candidaturas = montar(
            monkeypatch,
            frente_ids=[],
            frentes={},
            por_frente={},
            usuarios=[usuario(10)],
            alocados=(),
        )

        alocar(uc, 10)

        assert candidaturas.criadas == [10]


class TestATrocaDeVaga:
    """A troca é a TERCEIRA porta que põe gente numa banca (inscrição, push e
    ela). Sem o teto aqui, a regra seria contornável: bastava entrar por uma
    troca em vez da inscrição."""

    def montar_troca(self, monkeypatch, *, por_frente, usuarios, gravadas, alocados, sai):
        from src.use_cases.solicitacao_troca.confirmar_solicitacao_troca import (
            ConfirmarSolicitacaoTrocaUseCase,
        )

        uc_base, _ = montar(
            monkeypatch,
            frente_ids=[BUSINESS, TECH],
            frentes={
                BUSINESS: frente(BUSINESS, "Business", 3),
                TECH: frente(TECH, "Tech", 2),
            },
            por_frente=por_frente,
            usuarios=usuarios,
            gravadas=gravadas,
            alocados=alocados,
        )

        uc = ConfirmarSolicitacaoTrocaUseCase.__new__(ConfirmarSolicitacaoTrocaUseCase)
        uc.db = None
        uc.banca_frente_repository = uc_base.banca_frente_repository
        uc.candidatura_repository = uc_base.repository
        banca = SimpleNamespace(id=1, coordenador_id=None)
        solicitacao = SimpleNamespace(usuario_original_id=sai)
        return uc, banca, solicitacao

    def test_quem_sai_da_banca_sai_da_conta_antes(self, monkeypatch):
        """Business com teto 3 e 3 alocados: o consultor que passa a vaga
        para outro de Business devolve a vaga, não estoura o teto."""
        uc, banca, solicitacao = self.montar_troca(
            monkeypatch,
            por_frente={BUSINESS: [10, 11, 12, 13], TECH: []},
            usuarios=[usuario(i) for i in (10, 11, 12, 13)],
            gravadas=[
                regra_gravada(BUSINESS, min_membros=1, max_membros=3, min_lideranca=0),
                regra_gravada(TECH, min_membros=1, max_membros=3, min_lideranca=0),
            ],
            alocados=(10, 11, 12),
            sai=10,
        )

        candidaturas = uc.candidatura_repository.get_by_banca(1)

        assert uc._recusa_por_teto(banca, candidaturas, solicitacao, 13) is None

    def test_a_troca_que_estoura_a_frente_de_quem_entra_e_recusada(self, monkeypatch):
        """Sai um de Business, entra um de Tech — e Tech já está no teto."""
        uc, banca, solicitacao = self.montar_troca(
            monkeypatch,
            por_frente={BUSINESS: [10, 11], TECH: [20, 21]},
            usuarios=[usuario(i) for i in (10, 11, 20, 21)],
            gravadas=[
                regra_gravada(BUSINESS, min_membros=1, max_membros=3, min_lideranca=0),
                regra_gravada(TECH, min_membros=1, max_membros=1, min_lideranca=0),
            ],
            alocados=(10, 11, 20),
            sai=10,
        )

        candidaturas = uc.candidatura_repository.get_by_banca(1)

        assert "Tech" in (uc._recusa_por_teto(banca, candidaturas, solicitacao, 21) or "")

"""§8 — o push automático (`PushAlocacaoAutomaticaUseCase`) passa a puxar
POR frente (não mais um pool misturado) e a cobrir a liderança da frente
separado do piso. Mesmo padrão de fake de `test_destinatarios_notificacao.py`
— `__new__` + repositórios fake, e `notificar` trocado por um espião (é uma
função solta importada no módulo, não um método de repositório).
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.banca import push_alocacao_automatica as mod
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase


def usuario(id, posicao="consultor"):
    return SimpleNamespace(id=id, posicao=posicao)


class FakeBancaFrenteRepo:
    def __init__(self, frente_ids):
        self._frente_ids = frente_ids

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(frente_id=fid) for fid in self._frente_ids]


class FakeFrenteRepo:
    def __init__(self, frentes: dict):
        self._frentes = frentes

    def get_by_id(self, frente_id):
        return self._frentes.get(frente_id)


class FakeCandidaturaRepo:
    def __init__(self, existentes=()):
        self._existentes = list(existentes)
        self.criadas = []

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(usuario_id=uid) for uid in self._existentes]

    def create(self, banca_id, usuario_id, criado_em, confirmado=False):
        self.criadas.append(usuario_id)
        return SimpleNamespace(usuario_id=usuario_id)

    def get_all(self):
        return []


class FakeConfiguracaoRepo:
    def __init__(self, lideranca_minima=1):
        self._lideranca_minima = lideranca_minima

    def get(self):
        return SimpleNamespace(lideranca_minima_por_frente=self._lideranca_minima, vagas_por_banca=5)


class FakeEquipeProjetoRepo:
    def get_by_banca(self, banca_id):
        return []


class FakeBancaEscopoRepo:
    """A banca destes testes não cobre escopo nenhum — o assunto aqui é a
    composição por FRENTE. Sem escopo, `membros_da_banca` não tem projeto de
    onde puxar equipe, e o único excluído continua sendo o coordenador."""

    def __init__(self, escopo_ids=()):
        self._escopo_ids = list(escopo_ids)

    def get_escopo_ids(self, banca_id):
        return self._escopo_ids


class FakeProjetoEscopoRepo:
    def __init__(self, por_id: dict | None = None):
        self._por_id = por_id or {}

    def get_by_id(self, escopo_id):
        return self._por_id.get(escopo_id)


class FakeProjetoMembroRepo:
    def __init__(self, por_projeto: dict | None = None):
        self._por_projeto = por_projeto or {}

    def get_by_projeto(self, projeto_id, apenas_atuais=False):
        return self._por_projeto.get(projeto_id, [])


class FakeUsuarioFrenteRepo:
    def __init__(self, por_frente: dict):
        self._por_frente = por_frente

    def get_by_frente(self, frente_id):
        return [SimpleNamespace(usuario_id=uid) for uid in self._por_frente.get(frente_id, [])]


class FakeUsuarioRepo:
    def __init__(self, usuarios):
        self._usuarios = usuarios

    def get_ativos(self):
        return self._usuarios


class FakeSemestreRepo:
    """Sem semestre cadastrado = `_com_aula_no_horario` (§11) devolve vazio
    sem tocar na grade — os testes deste arquivo não são sobre choque de
    horário, então mantém o comportamento de antes dessa checagem existir."""

    def get_por_data(self, data):
        return None


class FakeGradeHorariaRepo:
    def get_por_semestre(self, semestre_id):
        return []


def frente(id, nome, piso_banca):
    return SimpleNamespace(id=id, nome=nome, piso_banca=piso_banca)


def montar(
    monkeypatch,
    *,
    frente_ids,
    frentes: dict,
    por_frente: dict,
    usuarios: list,
    candidaturas_existentes=(),
    lideranca_minima=1,
    teto=5,
    coordenador_id=None,
):
    monkeypatch.setattr(mod, "notificar", lambda *a, **k: None)
    uc = PushAlocacaoAutomaticaUseCase.__new__(PushAlocacaoAutomaticaUseCase)
    uc.db = None
    uc.banca_frente_repository = FakeBancaFrenteRepo(frente_ids)
    uc.frente_repository = FakeFrenteRepo(frentes)
    candidatura_repo = FakeCandidaturaRepo(candidaturas_existentes)
    uc.candidatura_repository = candidatura_repo
    uc.configuracao_repository = FakeConfiguracaoRepo(lideranca_minima)
    uc.equipe_projeto_repository = FakeEquipeProjetoRepo()
    uc.banca_escopo_repository = FakeBancaEscopoRepo()
    uc.escopo_repository = FakeProjetoEscopoRepo()
    uc.membro_repository = FakeProjetoMembroRepo()
    uc.usuario_frente_repository = FakeUsuarioFrenteRepo(por_frente)
    uc.usuario_repository = FakeUsuarioRepo(usuarios)
    uc.semestre_repository = FakeSemestreRepo()
    uc.grade_horaria_repository = FakeGradeHorariaRepo()
    banca = SimpleNamespace(
        id=1,
        nome_projeto="Projeto X",
        data_hora=datetime.now() + timedelta(days=3),
        coordenador_id=coordenador_id,
        piso_minimo_override=None,
    )
    return uc, banca, candidatura_repo


class TestPuxaPorFrenteEspecifica:
    def test_nao_mistura_pool_das_duas_frentes(self, monkeypatch):
        """Business(3)+Tech(2): antes, um pool único das duas frentes podia
        preencher os 5 só com gente de Business. Agora cada frente puxa da
        própria lista."""
        uc, banca, candidaturas = montar(
            monkeypatch,
            frente_ids=[1, 2],
            frentes={1: frente(1, "Business", 3), 2: frente(2, "Tech", 2)},
            por_frente={1: [10, 11, 12, 13], 2: [20, 21, 22]},
            usuarios=[usuario(i) for i in (10, 11, 12, 13, 20, 21, 22)],
            lideranca_minima=0,
        )

        resultado = uc._processar_banca(banca, teto=5, ultima_alocacao={})

        selecionados = set(resultado["usuarios_alocados"])
        assert len(selecionados & {10, 11, 12, 13}) == 3
        assert len(selecionados & {20, 21, 22}) == 2


class TestFallbackQualquerFrente:
    def test_frente_curta_e_completada_por_fora(self, monkeypatch):
        """Regra da diretoria: cumprido o piso por frente, o RESTO pode ser
        de qualquer frente — inclusive o próprio déficit de uma frente sem
        gente suficiente pra cobrir o piso dela mesma."""
        uc, banca, candidaturas = montar(
            monkeypatch,
            frente_ids=[1, 2],
            frentes={1: frente(1, "Business", 3), 2: frente(2, "Tech", 2)},
            # Tech só tem 1 pessoa disponível pro piso de 2.
            por_frente={1: [10, 11, 12], 2: [20]},
            usuarios=[usuario(i) for i in (10, 11, 12, 20, 30)],
            lideranca_minima=0,
            teto=6,
        )

        resultado = uc._processar_banca(banca, teto=6, ultima_alocacao={})

        selecionados = set(resultado["usuarios_alocados"])
        # As 4 óbvias (piso de cada frente) + a pessoa 30 (de fora) cobrindo
        # o déficit que Tech não conseguiu preencher sozinha.
        assert {10, 11, 12, 20}.issubset(selecionados)
        assert 30 in selecionados
        assert len(selecionados) == 5


class TestLiderancaNoPush:
    def test_puxa_gerente_antes_de_consultor_quando_falta_lideranca(self, monkeypatch):
        uc, banca, candidaturas = montar(
            monkeypatch,
            frente_ids=[1],
            frentes={1: frente(1, "Business", 2)},
            por_frente={1: [10, 11, 12]},  # 10 é gerente
            usuarios=[usuario(10, "gerente"), usuario(11), usuario(12)],
            lideranca_minima=1,
            teto=5,
        )

        resultado = uc._processar_banca(banca, teto=5, ultima_alocacao={})

        assert 10 in resultado["usuarios_alocados"]

    def test_diretor_nao_e_escalado_automaticamente_para_lideranca(self, monkeypatch):
        """O push cobre rotina com gerente — diretor só conta se já estiver
        lá por conta própria, a automação não escala diretoria pra banca."""
        uc, banca, candidaturas = montar(
            monkeypatch,
            frente_ids=[1],
            frentes={1: frente(1, "Business", 1)},
            por_frente={1: [11]},
            usuarios=[usuario(11), usuario(99, "diretor_projetos")],
            lideranca_minima=1,
            teto=5,
        )

        resultado = uc._processar_banca(banca, teto=5, ultima_alocacao={})

        assert 99 not in resultado["usuarios_alocados"]


class TestRespeitaOTeto:
    def test_nao_ultrapassa_o_teto_mesmo_com_deficit_maior(self, monkeypatch):
        uc, banca, candidaturas = montar(
            monkeypatch,
            frente_ids=[1],
            frentes={1: frente(1, "Business", 5)},
            por_frente={1: [10, 11, 12, 13, 14]},
            usuarios=[usuario(i) for i in range(10, 15)],
            lideranca_minima=0,
            teto=3,
        )

        resultado = uc._processar_banca(banca, teto=3, ultima_alocacao={})

        assert len(resultado["usuarios_alocados"]) == 3

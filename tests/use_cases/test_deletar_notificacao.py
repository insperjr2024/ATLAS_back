"""Excluir/limpar notificações já lidas.

Só `origem="evento"` tem linha de verdade no banco — uma `condicao` é a
marcação de leitura, não a notificação (ver `notificacao_model.py`). Estes
testes cobrem exatamente essa fronteira: o que pode ser apagado e o que não.

Os repositórios são dublês escritos à mão, mesmo idioma de
`test_email_notificacao.py`: nenhum destes casos precisa de banco de verdade,
só de saber quais linhas existem e o que foi feito com elas.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.notificacao import deletar_notificacao
from src.use_cases.notificacao.deletar_notificacao import (
    ExcluirNotificacaoUseCase,
    LimparNotificacoesLidasUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

USUARIO = SimpleNamespace(id=5)


class NotificacaoRepositoryFake:
    def __init__(self, db=None):
        self.linhas = {}
        self.excluidas = []
        self.limpar_chamado_para = None
        self.a_limpar = 0

    def get_evento_do_usuario(self, notificacao_id, usuario_id):
        linha = self.linhas.get(notificacao_id)
        if not linha or linha.usuario_id != usuario_id or linha.origem != "evento":
            return None
        return linha

    def excluir(self, linha):
        self.excluidas.append(linha.id)

    def limpar_eventos_lidos(self, usuario_id):
        self.limpar_chamado_para = usuario_id
        return self.a_limpar


@pytest.fixture
def repo(monkeypatch):
    fake = NotificacaoRepositoryFake()
    monkeypatch.setattr(deletar_notificacao, "NotificacaoRepository", lambda db: fake)
    return fake


def linha(id=1, usuario_id=5, origem="evento", lida_em=None):
    return SimpleNamespace(id=id, usuario_id=usuario_id, origem=origem, lida_em=lida_em)


class TestExcluir:
    def test_apaga_evento_ja_lido(self, repo):
        repo.linhas[1] = linha(lida_em=datetime(2026, 8, 5, 9, 0))
        ExcluirNotificacaoUseCase(db=None).execute(USUARIO, 1)
        assert repo.excluidas == [1]

    def test_recusa_evento_nao_lido(self, repo):
        """Excluir é para dar baixa em algo já resolvido, não uma segunda
        forma de sumir com um alerta sem olhar para ele."""
        repo.linhas[1] = linha(lida_em=None)
        with pytest.raises(RegraDeNegocioError, match="Marque como lida"):
            ExcluirNotificacaoUseCase(db=None).execute(USUARIO, 1)
        assert repo.excluidas == []

    def test_recusa_condicao(self, repo):
        """Uma condição não é a notificação, é a marcação de leitura dela —
        apagá-la faria o alerta voltar a contar no sino mesmo resolvido."""
        repo.linhas[1] = linha(origem="condicao", lida_em=datetime(2026, 8, 5, 9, 0))
        with pytest.raises(RegraDeNegocioError, match="não encontrada"):
            ExcluirNotificacaoUseCase(db=None).execute(USUARIO, 1)

    def test_recusa_notificacao_de_outra_pessoa(self, repo):
        repo.linhas[1] = linha(usuario_id=99, lida_em=datetime(2026, 8, 5, 9, 0))
        with pytest.raises(RegraDeNegocioError, match="não encontrada"):
            ExcluirNotificacaoUseCase(db=None).execute(USUARIO, 1)

    def test_recusa_id_inexistente(self, repo):
        with pytest.raises(RegraDeNegocioError, match="não encontrada"):
            ExcluirNotificacaoUseCase(db=None).execute(USUARIO, 404)


class TestLimparLidas:
    def test_delega_ao_repositorio_com_o_usuario_certo(self, repo):
        repo.a_limpar = 3
        resultado = LimparNotificacoesLidasUseCase(db=None).execute(USUARIO)
        assert resultado == {"excluidas": 3}
        assert repo.limpar_chamado_para == 5

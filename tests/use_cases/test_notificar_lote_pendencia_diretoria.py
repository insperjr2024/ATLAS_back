"""⭐ 2026-09-23 — lote de Avaliação de Desempenho encerrado com pendência
avisa quem administra Desempenho, um aviso por pessoa pendente, com o nome
dela — pra dar pra pontuar. Mesmo idioma dos vizinhos: dublês à mão, com
`registrar` e `usuarios_com_permissao` trocados no MÓDULO `eventos`.
"""

from types import SimpleNamespace

import src.use_cases.notificacao.eventos as mod


def usuario(id):
    return SimpleNamespace(id=id, nome=f"Diretor {id}")


DIRETOR_A = usuario(1)
DIRETOR_B = usuario(2)

LOTE = SimpleNamespace(id=99, nome="Finalização - PROJETO X - Escopo")


def pendencia(avaliador_id, avaliador_nome, respondida):
    return {
        "avaliador_id": avaliador_id,
        "avaliador_nome": avaliador_nome,
        "avaliado_id": 999,
        "respondida": respondida,
    }


def _montar(monkeypatch, *, diretores=()):
    chamadas = []

    def registrar_fake(db, **kwargs):
        chamadas.append(kwargs)

    monkeypatch.setattr(mod, "registrar", registrar_fake)
    monkeypatch.setattr(mod, "usuarios_com_permissao", lambda db, campo: list(diretores))
    return chamadas


class TestNotificarLoteDesempenhoPendenciaDiretoria:
    def test_um_aviso_por_pendente_por_diretor(self, monkeypatch):
        chamadas = _montar(monkeypatch, diretores=[DIRETOR_A, DIRETOR_B])
        pendencias = [
            pendencia(10, "Fulano", respondida=False),
            pendencia(11, "Beltrana", respondida=False),
        ]

        mod.notificar_lote_desempenho_pendencia_diretoria(None, LOTE, pendencias)

        # 2 pendentes x 2 diretores = 4 avisos.
        assert len(chamadas) == 4
        destinatarios = {c["usuario_id"] for c in chamadas}
        assert destinatarios == {DIRETOR_A.id, DIRETOR_B.id}
        titulos = {c["titulo"] for c in chamadas}
        assert any("Fulano" in t for t in titulos)
        assert any("Beltrana" in t for t in titulos)

    def test_quem_ja_respondeu_nao_gera_aviso(self, monkeypatch):
        chamadas = _montar(monkeypatch, diretores=[DIRETOR_A])
        pendencias = [pendencia(10, "Fulano", respondida=True)]

        mod.notificar_lote_desempenho_pendencia_diretoria(None, LOTE, pendencias)

        assert chamadas == []

    def test_sem_diretor_cadastrado_nao_gera_aviso(self, monkeypatch):
        chamadas = _montar(monkeypatch, diretores=[])
        pendencias = [pendencia(10, "Fulano", respondida=False)]

        mod.notificar_lote_desempenho_pendencia_diretoria(None, LOTE, pendencias)

        assert chamadas == []

    def test_chave_dedup_e_por_lote_pendente_e_diretor(self, monkeypatch):
        chamadas = _montar(monkeypatch, diretores=[DIRETOR_A])
        pendencias = [pendencia(10, "Fulano", respondida=False)]

        mod.notificar_lote_desempenho_pendencia_diretoria(None, LOTE, pendencias)

        assert chamadas[0]["chave_dedup"] == (
            f"lote_desempenho_pendencia_diretoria:lote={LOTE.id}:pendente=10:diretor={DIRETOR_A.id}"
        )

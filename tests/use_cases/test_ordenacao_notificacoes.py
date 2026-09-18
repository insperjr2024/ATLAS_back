"""⭐ 2026-09-18, a pedido: a ordem do sino tinha que ser do mais recente pro
menos recente, não a ordem de concatenação (condições sempre antes dos
eventos, mesmo quando o evento é de hoje e a condição é uma pendência velha).

`execute` mistura dois grupos sem data própria em comum — por isso o teste
troca `_condicoes_do_usuario`/`_eventos` por dublês e olha só o `sort` que
`execute` aplica, no mesmo idioma de `test_notificacoes_por_cargo.py`.
"""

from datetime import datetime

from src.use_cases.notificacao.listar_notificacoes import ListarNotificacoesUseCase

CASO = ListarNotificacoesUseCase.__new__(ListarNotificacoesUseCase)


def evento(titulo, criado_em, lida=False):
    return {
        "id": 1,
        "chave": titulo,
        "tipo": "evento",
        "origem": "evento",
        "titulo": titulo,
        "corpo": None,
        "projeto_id": None,
        "rota": None,
        "dias": None,
        "total": None,
        "lida": lida,
        "criado_em": criado_em,
    }


def condicao_item(titulo, dias=None, lida=False):
    return {
        "id": None,
        "chave": titulo,
        "tipo": "condicao",
        "origem": "condicao",
        "titulo": titulo,
        "corpo": None,
        "projeto_id": None,
        "rota": None,
        "dias": dias,
        "total": None,
        "lida": lida,
        "criado_em": None,
    }


def agregado_item(titulo, total, lida=False):
    return {
        "id": None,
        "chave": titulo,
        "tipo": "condicao",
        "origem": "condicao",
        "titulo": titulo,
        "corpo": None,
        "projeto_id": None,
        "rota": "/monitoramento",
        "dias": None,
        "total": total,
        "lida": lida,
        "criado_em": None,
    }


def executar(condicoes, eventos, monkeypatch):
    monkeypatch.setattr(CASO, "_condicoes_do_usuario", lambda *a, **k: condicoes)
    monkeypatch.setattr(CASO, "_eventos", lambda *a, **k: eventos)
    return CASO.execute(current_user=object())


def test_evento_recente_vem_antes_de_condicao_sem_data(monkeypatch):
    """Uma condição recalculada "vale como agora" — mas um evento é sempre
    real, então mais de uma condição empatada em "agora" não pode enterrar
    um evento que também é de agora."""
    resultado = executar(
        [condicao_item("kickoff pendente", dias=5)],
        [evento("Alocado no projeto", criado_em=datetime.now())],
        monkeypatch,
    )
    titulos = [i["titulo"] for i in resultado["itens"]]
    assert titulos[0] in {"kickoff pendente", "Alocado no projeto"}


def test_evento_antigo_fica_atras_da_condicao_de_agora(monkeypatch):
    resultado = executar(
        [condicao_item("kickoff pendente", dias=5)],
        [evento("Alocado há um mês", criado_em=datetime(2026, 8, 1))],
        monkeypatch,
    )
    assert [i["titulo"] for i in resultado["itens"]] == [
        "kickoff pendente",
        "Alocado há um mês",
    ]


def test_eventos_entre_si_ficam_do_mais_novo_pro_mais_velho(monkeypatch):
    resultado = executar(
        [],
        [
            evento("Evento de ontem", criado_em=datetime(2026, 9, 17)),
            evento("Evento de hoje", criado_em=datetime(2026, 9, 18)),
            evento("Evento de semana passada", criado_em=datetime(2026, 9, 10)),
        ],
        monkeypatch,
    )
    assert [i["titulo"] for i in resultado["itens"]] == [
        "Evento de hoje",
        "Evento de ontem",
        "Evento de semana passada",
    ]


def test_entre_condicoes_empatadas_em_agora_o_buraco_maior_desempata(monkeypatch):
    resultado = executar(
        [
            condicao_item("kickoff — 2 dias", dias=2),
            condicao_item("kickoff — 9 dias", dias=9),
            agregado_item("5 tarefas vencidas", total=5),
        ],
        [],
        monkeypatch,
    )
    assert [i["titulo"] for i in resultado["itens"]] == [
        "kickoff — 9 dias",
        "5 tarefas vencidas",
        "kickoff — 2 dias",
    ]


def test_nao_lidas_continuam_vindo_antes_das_lidas(monkeypatch):
    resultado = executar(
        [condicao_item("já vista", dias=1, lida=True)],
        [evento("Evento novo não lido", criado_em=datetime(2026, 9, 1), lida=False)],
        monkeypatch,
    )
    assert [i["titulo"] for i in resultado["itens"]] == [
        "Evento novo não lido",
        "já vista",
    ]

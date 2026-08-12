"""§7.4: o "porquê" de um atraso, e QUAIS atrasos podem ser justificados.

⭐ O quarto tipo, `escopo`, é o que estes testes protegem. Os três antigos
vêm de `MotivoAtraso` (`utils/atraso_monitoramento.py`) e perguntam "o que
venceu e não aconteceu?" — banca não realizada, entrega que não saiu. O novo
pergunta outra coisa: "o trabalho passou do tempo que foi vendido?", que é a
coluna **Atraso** do card "Escopos vendidos" (§10).

A distinção não é decorativa: um escopo pode estourar a janela com a banca já
realizada e a entrega em dia, e aí nenhum dos três dispara — o projeto nem
aparece na lista de atrasos do Monitoramento. Sem um tipo próprio, esse atraso
não teria como ser explicado.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch` —
mesmo idioma de `test_dias_de_ajuste.py`.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.projeto import registrar_justificativa_atraso
from src.use_cases.projeto.registrar_justificativa_atraso import (
    MOTIVOS_VALIDOS,
    RegistrarJustificativaAtrasoRequest,
    RegistrarJustificativaAtrasoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor")


@pytest.fixture
def justificar(monkeypatch):
    """`(executar, estado)` — `estado.criadas` mostra o que foi gravado."""

    def _montar(*, projeto_id=3, escopo_do_projeto=3):
        estado = SimpleNamespace(criadas=[])

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, pid):
                return SimpleNamespace(id=pid) if pid == projeto_id else None

        class EscopoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id):
                return SimpleNamespace(id=_id, projeto_id=escopo_do_projeto)

        class JustificativaFake:
            def __init__(self, db): pass
            def create(self, **campos):
                estado.criadas.append(campos)
                return SimpleNamespace(
                    id=len(estado.criadas), registrado_em=None, **campos
                )

        for nome, dublê in (
            ("ProjetoRepository", ProjetoFake),
            ("ProjetoEscopoRepository", EscopoFake),
            ("ProjetoJustificativaAtrasoRepository", JustificativaFake),
        ):
            monkeypatch.setattr(registrar_justificativa_atraso, nome, dublê)

        uc = RegistrarJustificativaAtrasoUseCase(db=None)

        def executar(texto="Cliente parou de responder", escopo_id=7, tipo="escopo"):
            return uc.execute(
                projeto_id,
                RegistrarJustificativaAtrasoRequest(
                    texto=texto, projeto_escopo_id=escopo_id, motivo_tipo=tipo
                ),
                registrado_por=DANI.id,
            )

        return executar, estado

    return _montar


def test_escopo_e_um_motivo_valido():
    """⭐ A regra em uma linha: o atraso de JANELA pode ser justificado.

    Antes só existiam os três de `MotivoAtraso`, e o atraso do §10 — o que a
    tela do projeto mostra na coluna "Atraso" — não tinha como ser explicado.
    """
    assert "escopo" in MOTIVOS_VALIDOS


def test_registra_a_nota_do_atraso_de_janela(justificar):
    executar, estado = justificar()

    resposta = executar()

    (criada,) = estado.criadas
    assert criada["tipo"] == "escopo"
    assert criada["projeto_escopo_id"] == 7
    assert criada["texto"] == "Cliente parou de responder"
    assert resposta["motivo_tipo"] == "escopo"


def test_os_tres_motivos_antigos_continuam_valendo(justificar):
    """A adição não pode ter estreitado o que já era aceito."""
    executar, estado = justificar()

    for tipo in ("banca", "entrega_interna", "entrega_externa"):
        executar(tipo=tipo)

    assert [c["tipo"] for c in estado.criadas] == [
        "banca",
        "entrega_interna",
        "entrega_externa",
    ]


def test_tipo_inventado_continua_recusado(justificar):
    """A lista é fechada: `tipo` é `String(30)` no banco, então sem esta
    validação qualquer palavra entraria e nunca casaria com motivo nenhum."""
    executar, estado = justificar()

    with pytest.raises(RegraDeNegocioError, match="Tipo de motivo inválido"):
        executar(tipo="janela")

    assert estado.criadas == []


def test_texto_vazio_e_recusado(justificar):
    """Nota em branco é pior que nota nenhuma: some a cobrança sem explicar."""
    executar, estado = justificar()

    with pytest.raises(RegraDeNegocioError, match="não pode ficar vazia"):
        executar(texto="   ")

    assert estado.criadas == []


def test_escopo_de_outro_projeto_e_recusado(justificar):
    """A rota já checa acesso ao projeto; isto fecha o outro lado — justificar
    o atraso de um escopo que não é dele."""
    executar, estado = justificar(escopo_do_projeto=99)

    with pytest.raises(RegraDeNegocioError, match="não pertence a este projeto"):
        executar()

    assert estado.criadas == []

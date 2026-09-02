"""Quem é "do próprio grupo" de uma banca (§8).

⭐ **A equipe de uma banca tem duas fontes, e as duas valem.**

- `equipe_projeto` — a tabela LEGADA do módulo de bancas, preenchida à mão no
  formulário "Consultores do projeto" da tela `/bancas`;
- `projeto_membro` — a equipe REAL do projeto, que é o que existe quando a
  banca nasce pelo cronograma (`PUT /escopos-projeto/{id}/banca`).

Enquanto só a primeira era consultada, uma banca marcada pelo cronograma
aparecia para os próprios consultores do projeto em "Disponíveis para
alocação", e eles conseguiam se inscrever na própria banca — exatamente o que o
§8 proíbe. O caminho novo de marcar banca não escreve em `equipe_projeto` (nem
deve: aquela tabela duplica `projeto_membro`), então a regra tinha de aprender
a olhar os dois lados.

Função pura de composição: recebe repositórios já construídos e devolve ids.
"""

from typing import Iterable, Set


def membros_da_banca(
    banca,
    banca_escopo_repository,
    escopo_repository,
    membro_repository,
    equipe_projeto_repository=None,
) -> Set[int]:
    """Os usuários que NÃO podem avaliar esta banca por serem do grupo dela.

    Inclui o coordenador da banca, a equipe legada (`equipe_projeto`) e os
    membros atuais dos projetos de todos os escopos que a banca cobre.

    O vendedor NÃO entra. Entre 2026-08-20 e 2026-09-01 ele contava como grupo
    (a ideia era "quem prometeu escopo e prazo não julga o resultado"), mas o
    núcleo decidiu que quem vendeu pode avaliar normalmente: ele não executou o
    projeto, e vender não é o mesmo conflito que entregar. Voltou a ser um
    consultor comum para efeito de banca.

    Uma banca pode cobrir escopos de um projeto só, mas a varredura passa por
    todos assim mesmo: é barato e não depende dessa garantia continuar valendo.
    """
    ids: Set[int] = set()
    if getattr(banca, "coordenador_id", None):
        ids.add(banca.coordenador_id)

    if equipe_projeto_repository is not None:
        ids.update(
            e.usuario_id for e in equipe_projeto_repository.get_by_banca(banca.id)
        )

    for escopo_id in banca_escopo_repository.get_escopo_ids(banca.id):
        escopo = escopo_repository.get_by_id(escopo_id)
        if not escopo:
            continue
        ids.update(
            m.usuario_id
            for m in membro_repository.get_by_projeto(escopo.projeto_id, apenas_atuais=True)
        )

    return ids


def mapa_de_equipes(
    bancas: Iterable,
    banca_escopo_repository,
    escopo_repository,
    membro_repository,
    equipe_projeto_repository=None,
) -> dict:
    """O mesmo, para a listagem — `{banca_id: {usuario_id, …}}`.

    A tela de bancas monta três baldes (alocado, disponível, lotada) e cada um
    consulta "é do meu grupo?"; sem o mapa pronto, isso viraria uma consulta por
    card.
    """
    return {
        banca.id: membros_da_banca(
            banca,
            banca_escopo_repository,
            escopo_repository,
            membro_repository,
            equipe_projeto_repository,
        )
        for banca in bancas
    }

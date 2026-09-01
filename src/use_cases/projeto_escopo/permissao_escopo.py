"""Quem mexe na lista de **escopos vendidos** de um projeto (§4).

Até 2026-08-31 era `require_gestao`: diretoria de projetos e gerência de
frente. O coordenador ficava de fora, e na prática era ele quem descobria que
faltava um escopo ou que um tinha sido vendido em duplicidade — e precisava
pedir a alguém para corrigir.

⭐ **Agora são exatamente dois: o coordenador DO PROJETO e a diretoria de
projetos.**

- O coordenador entra pelo **papel na equipe**, não pela posição na
  plataforma: um coordenador de outro projeto não mexe neste. Mesma régua do
  §8 (`cronograma_reajuste/solicitar.py`) e da confirmação de entrega — as
  três respondem "quem conduz ESTE projeto?", e responder diferente em cada
  uma era a fonte de confusão que este módulo existe para não repetir.
- A diretoria de projetos entra pela **posição**, sem estar na equipe: ela
  enxerga o portfólio e corrige qualquer projeto.

⚠ **A gerência de frente PERDEU o acesso** (2026-08-31, a pedido). Antes
entrava por `require_gestao`, junto da diretoria. É uma redução deliberada de
permissão, e não um efeito colateral: um gerente que precise mexer nos escopos
de um projeto agora pede ao coordenador dele ou à diretoria.
"""

from sqlalchemy.orm import Session

from src.middlewares.authorization import tem_posicao, DIRETORIA_DE_PROJETOS
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.utils.exceptions import RegraDeNegocioError


def pode_editar_escopos(projeto_id: int, current_user, db: Session) -> bool:
    if tem_posicao(current_user, *DIRETORIA_DE_PROJETOS):
        return True
    usuario_id = getattr(current_user, "id", None)
    # `apenas_atuais`: quem passou o bastão perde o direito na hora, como em
    # todas as outras portas que perguntam pelo coordenador.
    membros = ProjetoMembroRepository(db).get_by_projeto(projeto_id, apenas_atuais=True)
    return any(
        m.usuario_id == usuario_id and m.papel == "coordenador" for m in membros
    )


def exigir_pode_editar_escopos(projeto_id: int, current_user, db: Session) -> None:
    if not pode_editar_escopos(projeto_id, current_user, db):
        raise RegraDeNegocioError(
            "Só o coordenador deste projeto ou a diretoria de projetos "
            "mexem nos escopos vendidos"
        )


#: Os três campos do PATCH em `/escopos-projeto/{id}` que ficam de fora do
#: que o coordenador mexe, ver `exigir_pode_editar_tipo_e_dias`.
CAMPOS_RESTRITOS_A_DIRETORIA = {"escopo_id", "nome_customizado", "dias_uteis_vendidos"}


def exigir_pode_editar_tipo_e_dias(current_user, campos_enviados) -> None:
    """Trocar o TIPO do escopo (item do catálogo, ou "Outro" com nome
    digitado) e os dias úteis vendidos ficam de fora do que o coordenador
    mexe (2026-09-01, a pedido): o tipo é a identidade do que foi vendido, e
    os dias vendidos são o registro comercial, diferente de reordenar, mudar
    o calendário base ou a entrega planejada, que continuam abertos ao
    coordenador do projeto.

    `campos_enviados` são as chaves de `UpdateEscopoProjetoRequest` que a
    request de fato mandou (`exclude_unset`), não o corpo inteiro: só entra
    aqui quem tentou mexer num dos três campos restritos.
    """
    if not (set(campos_enviados) & CAMPOS_RESTRITOS_A_DIRETORIA):
        return
    if not tem_posicao(current_user, *DIRETORIA_DE_PROJETOS):
        raise RegraDeNegocioError(
            "Trocar o tipo do escopo ou os dias úteis vendidos é restrito à diretoria de projetos"
        )

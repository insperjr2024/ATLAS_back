"""Permissões e recorte de visão.

Até 2026-08-07 eram duas dimensões (`cargo`, editável, decidia a maioria das
caixas; `posicao` decidia só o recorte de visão e o que não virou caixa).
Foram unificadas: as mesmas 13 caixas agora são editadas POR POSIÇÃO — só 4
linhas fixas (`posicao_permissao`), sem catálogo aberto. `cargo` foi removido
inteiro; a distinção não sobrevivia ao uso real (dava pra marcar "Admin" numa
pessoa sem isso ampliar quais projetos ela via, por exemplo).

`require_diretor` e `require_posicao(...)` continuam existindo para o que é
identidade organizacional, não permissão delegável (última pessoa na
diretoria, elegibilidade de coordenador/consultor num projeto, composição de
banca) — essas nunca viraram caixa.

O recorte de visão (`aplicar_recorte_visao`) é a regra mais importante daqui:
o front só ESCONDE, quem DECIDE é o backend.
"""

from typing import List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository


# -------------------------------------------------- permissão (as 13 caixas, por posição)

def usuario_tem_permissao(current_user, db: Session, campo: str) -> bool:
    registro = PosicaoPermissaoRepository(db).get_by_posicao(current_user.posicao)
    return bool(registro and getattr(registro, campo, False))


def _exigir_permissao(current_user, db: Session, campo: str, mensagem: str):
    if not usuario_tem_permissao(current_user, db, campo):
        raise HTTPException(status_code=403, detail=mensagem)
    return current_user


def _dependencia_permissao(campo: str, mensagem: str):
    """Fabrica a dependência de uma das 10 caixas.

    Escrever as 10 à mão era repetir o mesmo corpo dez vezes — e cada cópia é
    uma chance de checar o campo errado.
    """

    def _dependencia(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
        return _exigir_permissao(current_user, db, campo, mensagem)

    return _dependencia


# 1. Criar projeto e alocar equipe
require_pode_criar_projeto = _dependencia_permissao(
    "pode_criar_projeto", "Você não tem permissão para criar projetos")

# 2. Editar a equipe de um projeto
require_pode_editar_equipe = _dependencia_permissao(
    "pode_editar_equipe", "Você não tem permissão para editar a equipe do projeto")

# 3. Gerir membros (posição e status)
require_pode_gerir_membros = _dependencia_permissao(
    "pode_gerir_membros", "Você não tem permissão para gerir membros")

# 4. Marcar kickoff e data de entrega
require_pode_marcar_kickoff = _dependencia_permissao(
    "pode_marcar_kickoff", "Você não tem permissão para marcar kickoff e entrega")

# 5. Definir cronograma por escopo (etapas, banca)
require_pode_definir_cronograma = _dependencia_permissao(
    "pode_definir_cronograma", "Você não tem permissão para definir o cronograma")

# 7. Criar tarefa
require_pode_criar_tarefa = _dependencia_permissao(
    "pode_criar_tarefa", "Você não tem permissão para criar tarefas")

# 8. Mover e editar tarefa
require_pode_mover_editar_tarefa = _dependencia_permissao(
    "pode_mover_editar_tarefa", "Você não tem permissão para mover ou editar tarefas")

# 9. Ver os próprios projetos
require_pode_ver_proprios_projetos = _dependencia_permissao(
    "pode_ver_proprios_projetos", "Você não tem permissão para ver projetos")

# 10. Monitoramento e alocação
require_pode_ver_monitoramento = _dependencia_permissao(
    "pode_ver_monitoramento", "Você não tem permissão para ver o monitoramento")

# -------------------------------------------------- extensão além das 10 do §3
#
# O briefing não define permissão pra estas áreas — o docstring do módulo as
# lista como "o que ficou de fora da tabela" e elas nasceram travadas só por
# posição (diretor, ou diretor+gerente). A pedido explícito do usuário
# (2026-08-06), viraram caixa editável como as outras 9, pra dar pra
# delegar sem precisar tornar alguém "diretor" inteiro.
# `pode_administrar_configuracoes` é a mais sensível: quem a tem edita as
# permissões de TODAS as posições, inclusive a própria — mas só quem já tem
# a caixa consegue mexer nela, então a auto-escalada exige já ter a
# permissão de largada.

require_pode_administrar_desempenho = _dependencia_permissao(
    "pode_administrar_desempenho",
    "Você não tem permissão para administrar a Avaliação de Desempenho",
)

require_pode_editar_formularios_desempenho = _dependencia_permissao(
    "pode_editar_formularios_desempenho",
    "Você não tem permissão para editar os formulários de Avaliação de Desempenho",
)

require_pode_administrar_configuracoes = _dependencia_permissao(
    "pode_administrar_configuracoes",
    "Você não tem permissão para administrar as configurações",
)


def require_self_or_admin(usuario_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.id != usuario_id and not usuario_tem_permissao(current_user, db, "pode_gerir_membros"):
        raise HTTPException(status_code=403, detail="Você só pode acessar seus próprios dados")
    return current_user


# ---------------------------------------------------------------- posição (§3)

def tem_posicao(current_user, *posicoes: str) -> bool:
    return getattr(current_user, "posicao", None) in posicoes


def eh_lideranca(current_user) -> bool:
    """Diretor, gerente e coordenador. Consultor não é liderança."""
    return tem_posicao(current_user, "diretor", "gerente", "coordenador")


def require_posicao(*posicoes: str):
    """Dependência que exige uma das posições dadas.

    Uso: `_=Depends(require_posicao("diretor", "gerente"))`
    """
    permitidas = set(posicoes)

    def _dependencia(current_user=Depends(get_current_user)):
        if current_user.posicao not in permitidas:
            raise HTTPException(
                status_code=403,
                detail=f"Ação restrita a: {', '.join(sorted(permitidas))}",
            )
        return current_user

    return _dependencia


def require_diretor(current_user=Depends(get_current_user)):
    """Aprovar reajuste, gerir membros e justificar atraso são só da diretoria."""
    if current_user.posicao != "diretor":
        raise HTTPException(status_code=403, detail="Ação restrita à diretoria")
    return current_user


def require_gestao(current_user=Depends(get_current_user)):
    """Criar projeto, editar equipe e ver monitoramento: diretor e gerente."""
    if current_user.posicao not in ("diretor", "gerente"):
        raise HTTPException(
            status_code=403,
            detail="Ação restrita à diretoria e à gerência de frente",
        )
    return current_user


def require_lideranca(current_user=Depends(get_current_user)):
    """Conduzir o projeto (mudar status, definir cronograma): coordenador —
    com diretor e gerente herdando. O consultor não move o ciclo de vida (§4)."""
    if not eh_lideranca(current_user):
        raise HTTPException(
            status_code=403,
            detail="Ação restrita a coordenação, gerência e diretoria",
        )
    return current_user


# ---------------------------------------------------------------- avaliação de desempenho

def require_self(usuario_id: int, current_user=Depends(get_current_user)):
    """Só a própria pessoa — diferente de `require_self_or_admin`, aqui não
    tem override de admin (ex.: minha fila de avaliação, meus mentorados)."""
    if current_user.id != usuario_id:
        raise HTTPException(status_code=403, detail="Você só pode acessar seus próprios dados")
    return current_user


def require_self_mentor_ou_gestao(usuario_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Vê o relatório de desempenho de `usuario_id`: a própria pessoa, quem tem
    vínculo de mentoria com ela (`desempenho_mentoria`), ou diretor/gerente.

    A Avaliação de Desempenho não está na tabela das 10, então continua travada
    por posição, como o resto do painel.
    """
    if current_user.id == usuario_id or current_user.posicao in ("diretor", "gerente"):
        return current_user

    from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository

    vinculo = DesempenhoMentoriaRepository(db).first_by(mentor_id=current_user.id, mentorado_id=usuario_id)
    if vinculo:
        return current_user
    raise HTTPException(status_code=403, detail="Você não tem acesso a este relatório")


# ---------------------------------------------------------------- recorte de visão

def frentes_do_usuario(current_user, db: Session) -> List[int]:
    from src.repositories.usuario_frente_repository import UsuarioFrenteRepository

    vinculos = UsuarioFrenteRepository(db).get_by_usuario(current_user.id)
    return [v.frente_id for v in vinculos]


def aplicar_recorte_visao(query, current_user, db: Session, frente_id: Optional[int] = None):
    """Restringe uma query de projetos ao que o usuário pode enxergar (§3).

    - **diretor**: tudo, e pode filtrar por frente via `?frente_id=`;
    - **gerente**: só as frentes dele (o que inclui os sinérgicos que as
      envolvam) — o filtro é forçado, não vem da query string;
    - **coordenador / consultor**: só os projetos em que estão alocados hoje.

    Recebe e devolve a query, para poder ser encadeada antes do `.all()`.
    """
    from src.models.projeto_frente_model import ProjetoFrenteModel
    from src.models.projeto_membro_model import ProjetoMembroModel
    from src.models.projeto_model import ProjetoModel

    # A única caixa que muda QUAIS projetos aparecem — as outras 12 só
    # ligam/desligam funcionalidade, nunca o recorte. Uma posição com isto
    # marcado é tratada como diretor pra fins de visão (ver
    # `PosicaoPermissaoModel.pode_ver_todos_projetos`).
    if current_user.posicao == "diretor" or usuario_tem_permissao(
        current_user, db, "pode_ver_todos_projetos"
    ):
        if frente_id is not None:
            query = query.filter(
                ProjetoModel.id.in_(
                    db.query(ProjetoFrenteModel.projeto_id).filter(
                        ProjetoFrenteModel.frente_id == frente_id
                    )
                )
            )
        return query

    if current_user.posicao == "gerente":
        # O gerente fica travado nas próprias frentes: o ?frente_id= da query
        # string no máximo restringe, nunca amplia o que ele enxerga.
        minhas = frentes_do_usuario(current_user, db)
        alvo = [frente_id] if frente_id in minhas else minhas
        return query.filter(
            ProjetoModel.id.in_(
                db.query(ProjetoFrenteModel.projeto_id).filter(
                    ProjetoFrenteModel.frente_id.in_(alvo or [-1])
                )
            )
        )

    # Coordenador e consultor: só onde estão alocados HOJE (saiu_em vazio).
    return query.filter(
        ProjetoModel.id.in_(
            db.query(ProjetoMembroModel.projeto_id).filter(
                ProjetoMembroModel.usuario_id == current_user.id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
        )
    )


def pode_ver_projeto(projeto_id: int, current_user, db: Session) -> bool:
    """Mesma regra do recorte, para uma linha só (rotas de detalhe)."""
    from src.models.projeto_model import ProjetoModel

    query = aplicar_recorte_visao(
        db.query(ProjetoModel.id).filter(ProjetoModel.id == projeto_id),
        current_user,
        db,
    )
    return query.first() is not None


def exigir_acesso_ao_projeto(projeto_id: int, current_user, db: Session) -> None:
    if not pode_ver_projeto(projeto_id, current_user, db):
        # 404 e não 403: quem não enxerga o projeto não deve nem saber que ele existe.
        raise HTTPException(status_code=404, detail="Projeto não encontrado")


def eh_avaliador_do_projeto(projeto_id: int, current_user, db: Session) -> bool:
    """Está escalado para alguma banca deste projeto?

    ⭐ **Um visitante da aba Banca, e nada além dela.** O §3 dá visão de projeto
    a quem está ALOCADO nele, e o §8 proíbe que membro do projeto avalie a
    própria banca — os dois conjuntos são disjuntos por construção. O efeito
    colateral era que o avaliador escalado, a única pessoa que de fato vota,
    recebia 404 na página onde o voto mora: a tela existia e ninguém que
    precisava dela conseguia abrir.

    Isto NÃO amplia o recorte. `pode_ver_projeto` continua igual, a listagem de
    projetos continua igual, e as abas de cronograma, tarefas e histórico
    continuam fechadas. É uma porta nomeada, usada só onde a banca é o assunto.
    """
    from src.models.banca_escopo_model import BancaEscopoModel
    from src.models.candidatura_model import CandidaturaModel
    from src.models.projeto_escopo_model import ProjetoEscopoModel

    return (
        db.query(CandidaturaModel.id)
        .join(BancaEscopoModel, BancaEscopoModel.banca_id == CandidaturaModel.banca_id)
        .join(
            ProjetoEscopoModel,
            ProjetoEscopoModel.id == BancaEscopoModel.projeto_escopo_id,
        )
        .filter(
            CandidaturaModel.usuario_id == current_user.id,
            ProjetoEscopoModel.projeto_id == projeto_id,
        )
        .first()
        is not None
    )


def exigir_acesso_a_banca_do_projeto(projeto_id: int, current_user, db: Session) -> bool:
    """Acesso à aba Banca: quem vê o projeto **ou** quem foi escalado nele.

    Devolve `True` quando a pessoa entrou pela porta de visitante — o chamador
    usa isso para dizer à tela que só a aba Banca está disponível.
    """
    if pode_ver_projeto(projeto_id, current_user, db):
        return False
    if eh_avaliador_do_projeto(projeto_id, current_user, db):
        return True
    raise HTTPException(status_code=404, detail="Projeto não encontrado")
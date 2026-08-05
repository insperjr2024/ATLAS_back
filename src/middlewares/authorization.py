"""Permissões e recorte de visão.

Duas dimensões que convivem, e não devem ser confundidas:

- **`cargo`** (3 flags booleanas) → permissões do MÓDULO DE BANCAS (P2/P3).
  É o que já existia; continua mandando nas ações de banca e formulário.
- **`posicao`** (diretor · gerente · coordenador · consultor) → a matriz do §3,
  que manda no resto da plataforma.

O recorte de visão (`aplicar_recorte_visao`) é a regra mais importante daqui:
o front só ESCONDE, quem DECIDE é o backend.
"""

from typing import List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.cargo_repository import CargoRepository


# ---------------------------------------------------------------- cargo (bancas)

def usuario_tem_permissao(current_user, db: Session, campo: str) -> bool:
    cargo = CargoRepository(db).get_by_id(current_user.cargo_id)
    return bool(cargo and getattr(cargo, campo, False))


def _exigir_permissao(current_user, db: Session, campo: str, mensagem: str):
    if not usuario_tem_permissao(current_user, db, campo):
        raise HTTPException(status_code=403, detail=mensagem)
    return current_user


def require_pode_definir_formulario(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_definir_formulario",
                              "Apenas o Diretor de Projetos pode editar o formulário")


def require_pode_agendar_banca(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_agendar_banca",
                              "Você não tem permissão para gerenciar bancas")


def require_pode_gerenciar_membros(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_gerenciar_membros",
                              "Você não tem permissão para gerenciar membros")


def require_pode_gerenciar_nucleo(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return _exigir_permissao(current_user, db, "pode_gerenciar_nucleo",
                              "Você não tem permissão para gerenciar o núcleo")


def require_pode_gerenciar_cargos(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """🔒 Editar cargo é editar quem pode o quê — exige a caixa E a posição.

    Só a caixa era um furo de escalonamento: quem a tivesse abria o próprio
    cargo e marcava o resto. A posição fecha isso porque ela não se edita por
    aqui — muda em Membros, que já é da diretoria.
    """
    if current_user.posicao != "diretor":
        raise HTTPException(
            status_code=403,
            detail="Apenas a diretoria pode alterar cargos e permissões",
        )
    return _exigir_permissao(current_user, db, "pode_gerenciar_cargos",
                              "Você não tem permissão para alterar cargos")


def require_self_or_admin(usuario_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.id != usuario_id and not usuario_tem_permissao(current_user, db, "pode_gerenciar_membros"):
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

    if current_user.posicao == "diretor":
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
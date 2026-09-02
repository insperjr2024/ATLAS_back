"""Permissões e recorte de visão.

Até 2026-08-07 eram duas dimensões (`cargo`, editável, decidia a maioria das
caixas; `posicao` decidia só o recorte de visão e o que não virou caixa).
Foram unificadas: as mesmas caixas (13 na época, 14 hoje) agora são editadas POR POSIÇÃO — só 4
linhas fixas (`posicao_permissao`), sem catálogo aberto. `cargo` foi removido
inteiro; a distinção não sobrevivia ao uso real (dava pra marcar "Admin" numa
pessoa sem isso ampliar quais projetos ela via, por exemplo).

As guardas por POSIÇÃO continuam existindo para o que é identidade
organizacional, não permissão delegável (última pessoa na diretoria,
elegibilidade de coordenador/consultor num projeto, composição de banca) —
essas nunca viraram caixa.

⭐ **A diretoria são TRÊS cargos desde 2026-08-20** (antes era `diretor`, um
só):

- `diretor_projetos` — o diretor de antes, com tudo. Herdou as guardas que
  diziam `require_diretor`;
- `diretor_pessoas` — visualização + Avaliação de Desempenho + as ações de
  cadastro de gente;
- `diretor` — só visualização. Enxerga todos os projetos e administra Membros,
  e não conduz nada.

Os três enxergam o portfólio inteiro (`eh_diretoria`), e é só isso que eles
têm em comum. Toda guarda daqui para baixo sai de uma das constantes abaixo —
nenhuma compara `posicao` com string solta, porque foi assim que a regra
antiga se espalhou por ~40 lugares.

O recorte de visão (`aplicar_recorte_visao`) é a regra mais importante daqui:
o front só ESCONDE, quem DECIDE é o backend.
"""

from typing import List, Optional

import sqlalchemy as sa
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository


# ---------------------------------------------------------------- os cargos

#: Os três cargos da diretoria. O que os une é enxergar o portfólio inteiro
#: (`aplicar_recorte_visao`) — e mais nada.
DIRETORIA = ("diretor_projetos", "diretor_pessoas", "diretor")

#: Quem conduz a operação de PROJETO. É o herdeiro do `diretor` antigo: toda
#: guarda que dizia `require_diretor` aponta para cá.
DIRETORIA_DE_PROJETOS = ("diretor_projetos",)

#: Quem mexe no CADASTRO DE GENTE: registrar usuário, senha provisória, apagar
#: em definitivo, passar o bastão. O diretor de projetos entra junto porque é
#: quem faz isso hoje — tirar dele seria uma perda de poder que a divisão dos
#: cargos não pediu.
DIRETORIA_DE_PESSOAS = ("diretor_projetos", "diretor_pessoas")


def eh_diretoria(current_user) -> bool:
    """Qualquer um dos três cargos de diretoria."""
    return getattr(current_user, "posicao", None) in DIRETORIA


def eh_diretoria_de_projetos(current_user) -> bool:
    """O cargo que herdou os poderes do `diretor` de antes."""
    return getattr(current_user, "posicao", None) in DIRETORIA_DE_PROJETOS


# -------------------------------------------------- permissão (as 14 caixas, por posição)

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

# O Dashboard Bancas era a última área grande travada em POSIÇÃO pura
# (`require_diretor_projetos` + uma matriz no front), e não havia razão para
# ela ser diferente das três acima: ler as notas de banca é trabalho que se
# delega, e delegá-lo exigia promover a pessoa a diretora de projetos.
require_pode_ver_dashboard_bancas = _dependencia_permissao(
    "pode_ver_dashboard_bancas",
    "Você não tem permissão para ver o Dashboard Bancas",
)


def require_self_or_admin(usuario_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.id != usuario_id and not usuario_tem_permissao(current_user, db, "pode_gerir_membros"):
        raise HTTPException(status_code=403, detail="Você só pode acessar seus próprios dados")
    return current_user


# ---------------------------------------------------------------- posição (§3)

def tem_posicao(current_user, *posicoes: str) -> bool:
    return getattr(current_user, "posicao", None) in posicoes


def eh_lideranca(current_user) -> bool:
    """Quem conduz projeto: coordenador, gerente e diretoria DE PROJETOS.

    ⚠ O diretor só-visualização e o de gestão de pessoas ficam de fora — eles
    são diretoria, mas não conduzem projeto. É o par de `require_lideranca`.
    """
    return tem_posicao(current_user, *DIRETORIA_DE_PROJETOS, "gerente", "coordenador")


def _require_posicoes(posicoes, mensagem: str):
    """Fabrica uma dependência que exige uma das posições dadas.

    Substituiu o `require_posicao(*posicoes)` público, que estava definido,
    documentado e usado em ZERO rotas — a divisão da diretoria era a hora de
    tirá-lo em vez de atualizá-lo.
    """
    permitidas = tuple(posicoes)

    def _dependencia(current_user=Depends(get_current_user)):
        if getattr(current_user, "posicao", None) not in permitidas:
            raise HTTPException(status_code=403, detail=mensagem)
        return current_user

    return _dependencia


#: Conduzir a operação de projeto: aprovar reajuste, decidir exceção de banca,
#: registrar resultado, configurar o kanban. Era `require_diretor`.
require_diretor_projetos = _require_posicoes(
    DIRETORIA_DE_PROJETOS, "Ação restrita à diretoria de projetos"
)

#: Cadastro de gente. Ver `DIRETORIA_DE_PESSOAS`.
require_diretoria_de_pessoas = _require_posicoes(
    DIRETORIA_DE_PESSOAS,
    "Ação restrita à diretoria de projetos e à de gestão de pessoas",
)

#: Criar projeto, editar equipe, arquivar, mexer em escopo vendido.
require_gestao = _require_posicoes(
    DIRETORIA_DE_PROJETOS + ("gerente",),
    "Ação restrita à diretoria de projetos e à gerência de frente",
)

#: Conduzir o projeto (mudar status, marcar banca do escopo, justificar
#: atraso): coordenador, com gerência e diretoria de projetos herdando. O
#: consultor não move o ciclo de vida (§4), e o diretor só-visualização
#: também não.
require_lideranca = _require_posicoes(
    DIRETORIA_DE_PROJETOS + ("gerente", "coordenador"),
    "Ação restrita a coordenação, gerência e diretoria de projetos",
)


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
    por posição, como o resto do painel. O diretor só-visualização fica de
    fora: desempenho é justamente o que ele não vê.
    """
    if current_user.id == usuario_id or current_user.posicao in (
        *DIRETORIA_DE_PESSOAS,
        "gerente",
    ):
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

    - **diretoria** (os três cargos): tudo, e pode filtrar por frente via
      `?frente_id=`;
    - **gerente**: só as frentes dele (o que inclui os sinérgicos que as
      envolvam) — o filtro é forçado, não vem da query string;
    - **coordenador / consultor**: só os projetos em que estão alocados hoje.

    ⭐ **Quem VENDEU um projeto também o enxerga**, somado ao que já via — vale
    para gerente, coordenador e consultor (a diretoria já vê tudo). É só
    VISÃO: o acesso que vem por venda é somente leitura, e quem cuida disso é
    `exigir_acesso_ao_projeto`, não esta função.

    Recebe e devolve a query, para poder ser encadeada antes do `.all()`.
    """
    from src.models.projeto_frente_model import ProjetoFrenteModel
    from src.models.projeto_membro_model import ProjetoMembroModel
    from src.models.projeto_model import ProjetoModel

    # A única caixa que muda QUAIS projetos aparecem — as outras 12 só
    # ligam/desligam funcionalidade, nunca o recorte. Uma posição com isto
    # marcado é tratada como diretor pra fins de visão (ver
    # `PosicaoPermissaoModel.pode_ver_todos_projetos`).
    if eh_diretoria(current_user) or usuario_tem_permissao(
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
            sa.or_(
                ProjetoModel.id.in_(
                    db.query(ProjetoFrenteModel.projeto_id).filter(
                        ProjetoFrenteModel.frente_id.in_(alvo or [-1])
                    )
                ),
                ProjetoModel.id.in_(_projetos_vendidos_por(current_user, db)),
            )
        )

    # Coordenador e consultor: só onde estão alocados HOJE (saiu_em vazio),
    # MAIS o que a pessoa vendeu.
    return query.filter(
        sa.or_(
            ProjetoModel.id.in_(
                db.query(ProjetoMembroModel.projeto_id).filter(
                    ProjetoMembroModel.usuario_id == current_user.id,
                    ProjetoMembroModel.saiu_em.is_(None),
                )
            ),
            ProjetoModel.id.in_(_projetos_vendidos_por(current_user, db)),
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


def _projetos_vendidos_por(current_user, db: Session):
    """Subquery com os ids dos projetos que esta pessoa vendeu."""
    from src.models.projeto_vendedor_model import ProjetoVendedorModel

    return db.query(ProjetoVendedorModel.projeto_id).filter(
        ProjetoVendedorModel.usuario_id == getattr(current_user, "id", None)
    )


def vendeu_o_projeto(projeto_id: int, current_user, db: Session) -> bool:
    from src.models.projeto_vendedor_model import ProjetoVendedorModel

    return (
        db.query(ProjetoVendedorModel.id)
        .filter(
            ProjetoVendedorModel.projeto_id == projeto_id,
            ProjetoVendedorModel.usuario_id == getattr(current_user, "id", None),
        )
        .first()
        is not None
    )


def acesso_somente_por_venda(projeto_id: int, current_user, db: Session) -> bool:
    """A pessoa enxerga este projeto SÓ porque o vendeu?

    ⭐ É a pergunta que separa leitura de escrita. As permissões da plataforma
    são globais por posição, não por projeto: um consultor-vendedor tem
    `pode_criar_tarefa` em qualquer projeto que enxergue. Sem esta distinção,
    vender um projeto daria escrita nele.

    Quem entra por outra porta (está na equipe, é gerente da frente, é
    diretoria) NÃO é somente-leitura, mesmo que também tenha vendido — a porta
    mais forte vence.
    """
    if eh_diretoria(current_user) or usuario_tem_permissao(
        current_user, db, "pode_ver_todos_projetos"
    ):
        return False

    from src.models.projeto_frente_model import ProjetoFrenteModel
    from src.models.projeto_membro_model import ProjetoMembroModel

    na_equipe = (
        db.query(ProjetoMembroModel.id)
        .filter(
            ProjetoMembroModel.projeto_id == projeto_id,
            ProjetoMembroModel.usuario_id == current_user.id,
            ProjetoMembroModel.saiu_em.is_(None),
        )
        .first()
        is not None
    )
    if na_equipe:
        return False

    if current_user.posicao == "gerente":
        minhas = frentes_do_usuario(current_user, db)
        da_frente_dele = (
            db.query(ProjetoFrenteModel.id)
            .filter(
                ProjetoFrenteModel.projeto_id == projeto_id,
                ProjetoFrenteModel.frente_id.in_(minhas or [-1]),
            )
            .first()
            is not None
        )
        if da_frente_dele:
            return False

    return vendeu_o_projeto(projeto_id, current_user, db)


def exigir_acesso_ao_projeto(
    projeto_id: int, current_user, db: Session, *, somente_leitura_ok: bool = False
) -> None:
    """Barra quem não enxerga o projeto — e, por padrão, quem só o vê por ter
    vendido.

    ⚠ **O padrão é RECUSAR o vendedor**, e a permissão é dada rota a rota com
    `somente_leitura_ok=True`. É o contrário do que parece natural, e é de
    propósito: são 44 chamadas desta função, a maioria em rota de escrita.
    Liberando por padrão, cada uma teria que lembrar de barrar; recusando,
    quem esquece do parâmetro erra para o lado seguro — e uma rota de escrita
    escrita amanhã já nasce fechada para o vendedor.
    """
    if not pode_ver_projeto(projeto_id, current_user, db):
        # 404 e não 403: quem não enxerga o projeto não deve nem saber que ele existe.
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    if not somente_leitura_ok and acesso_somente_por_venda(projeto_id, current_user, db):
        raise HTTPException(
            status_code=403,
            detail="Você vendeu este projeto, mas não faz parte da equipe — o acesso é de leitura",
        )


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
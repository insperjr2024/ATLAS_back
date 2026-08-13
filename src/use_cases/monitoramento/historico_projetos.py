"""A aba **Histórico de projetos** do painel (§7) — só diretoria e gerência.

Lista os projetos ENCERRADOS — finalizados ou arquivados — do portfólio que o
usuário enxerga. Zero tabela nova, no idioma do resto do Monitoramento
(`monitoramento.py`): lê `projeto`, pega o carimbo de encerramento em
`projeto_status_historico` e cruza com a grade de `semestre` para dizer em qual
semestre cada projeto fechou.

🔐 **Sem autorização própria.** Abre com `aplicar_recorte_visao` (§7.5): o
gerente fica travado nas frentes dele — o `?frente_id=` no máximo restringe,
nunca amplia —, a diretoria vê tudo. A trava de posição (diretor + gerente)
fica na rota, com `require_gestao`.
"""

from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_model import ProjetoModel
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_repository import UsuarioRepository

FILTROS = ("todos", "finalizados", "arquivados")


class HistoricoProjetosUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.frente_repo = FrenteRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.status_repo = ProjetoStatusHistoricoRepository(db)
        self.semestre_repo = SemestreRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(
        self, current_user, frente_id: Optional[int] = None, filtro: str = "todos"
    ) -> list[dict]:
        filtro = filtro if filtro in FILTROS else "todos"

        # ⚠ NÃO filtramos `arquivado_em.is_(None)` como a listagem normal: o
        # projeto arquivado é justamente o que esta aba existe para mostrar.
        query = aplicar_recorte_visao(
            self.db.query(ProjetoModel), current_user, self.db, frente_id
        )
        projetos = [p for p in query.all() if _encerrado(p)]

        if filtro == "finalizados":
            projetos = [p for p in projetos if p.status == "finalizado"]
        elif filtro == "arquivados":
            projetos = [p for p in projetos if p.arquivado_em is not None]

        if not projetos:
            return []

        ids = [p.id for p in projetos]
        nome_da_frente = {f.id: f.nome for f in self.frente_repo.get_all()}
        nome_da_pessoa = {u.id: u.nome for u in self.usuario_repo.get_all()}
        semestres = self.semestre_repo.get_all()

        # Frentes e membros em bloco — uma consulta cada, não uma por projeto
        # (o portfólio inteiro pode ter centenas de linhas).
        frentes_por_projeto = defaultdict(list)
        for pf in self.db.query(ProjetoFrenteModel).filter(
            ProjetoFrenteModel.projeto_id.in_(ids)
        ):
            frentes_por_projeto[pf.projeto_id].append(pf.frente_id)

        membros_por_projeto = defaultdict(list)
        for m in self.membro_repo.get_by_projetos(ids):
            membros_por_projeto[m.projeto_id].append(m)

        encerrado_por_projeto = self._encerramentos(ids)

        linhas = []
        for p in projetos:
            encerrado_em = encerrado_por_projeto.get(p.id) or p.arquivado_em
            frente_ids = frentes_por_projeto.get(p.id, [])
            coord = self._coordenador(membros_por_projeto.get(p.id, []))
            semestre = _semestre_de(encerrado_em, semestres)
            linhas.append(
                {
                    "id": p.id,
                    "nome": p.nome,
                    "cliente": p.cliente,
                    # `status` é o do projeto ("finalizado", "pausado", …);
                    # `arquivado` diz se ele saiu de circulação, ortogonal ao
                    # status (dá para arquivar um pausado, por exemplo).
                    "status": p.status,
                    "arquivado": p.arquivado_em is not None,
                    "frentes": [nome_da_frente.get(fid) for fid in frente_ids],
                    "frente_ids": frente_ids,
                    "sinergico": len(frente_ids) > 1,
                    "coordenador": nome_da_pessoa.get(coord) if coord else None,
                    "coordenador_id": coord,
                    "data_kickoff": p.data_kickoff,
                    "encerrado_em": encerrado_em,
                    "semestre": semestre.nome if semestre else None,
                    "duracao_dias": _duracao(p.data_kickoff, encerrado_em),
                }
            )

        # Mais recente primeiro. `""` para o projeto sem carimbo nunca derrubar
        # a ordenação (arquivado sem transição de status, caso de dado antigo).
        linhas.sort(key=lambda l: l["encerrado_em"] or _MIN, reverse=True)
        return linhas

    def _encerramentos(self, ids: list[int]) -> dict[int, object]:
        """Quando cada projeto virou `finalizado`, em bloco.

        Pega a ÚLTIMA transição para `finalizado` — um projeto pode ter sido
        finalizado, reaberto e finalizado de novo, e o que interessa é o
        fechamento que vale hoje.
        """
        encerrado: dict[int, object] = {}
        for h in self.status_repo.get_by_projetos(ids):
            if h.status_novo == "finalizado":
                encerrado[h.projeto_id] = h.alterado_em  # ordenado por data asc
        return encerrado

    @staticmethod
    def _coordenador(membros) -> Optional[int]:
        """O coordenador do projeto: o atual (sem `saiu_em`) tem preferência;
        se todos já saíram — projeto encerrado com equipe desfeita —, o último
        a deixar o papel."""
        coords = [m for m in membros if m.papel == "coordenador"]
        if not coords:
            return None
        atual = next((m for m in coords if m.saiu_em is None), None)
        if atual:
            return atual.usuario_id
        return max(coords, key=lambda m: m.saiu_em or m.entrou_em).usuario_id


def _encerrado(projeto) -> bool:
    return projeto.status == "finalizado" or projeto.arquivado_em is not None


def _duracao(kickoff, encerrado_em) -> Optional[int]:
    if not kickoff or not encerrado_em:
        return None
    fim = encerrado_em.date() if hasattr(encerrado_em, "date") else encerrado_em
    return (fim - kickoff).days


def _semestre_de(data, semestres):
    """A grade de semestres não tem FK no projeto (ver o docstring do
    `monitoramento.py`): o vínculo é por DATA. Sem data de encerramento, sem
    semestre."""
    if not data:
        return None
    dia = data.date() if hasattr(data, "date") else data
    for s in semestres:
        if s.inicio <= dia <= s.fim:
            return s
    return None


class _Min:
    """Sentinela sempre "menor" que qualquer datetime, para a ordenação da
    linha sem carimbo ir para o fim sem estourar comparação de tipos."""

    def __lt__(self, _):
        return True

    def __gt__(self, _):
        return False


_MIN = _Min()

"""Composição de banca (§8) — piso POR frente e liderança da frente, além do
piso TOTAL que já existia em `piso_banca.py`.

Antes disto só existia um número total (soma do `piso_banca` das frentes
vinculadas): uma banca sinérgica Business+Tech (piso 3+2=5) fechava com 5
pessoas de Business e ZERO de Tech, porque nada conferia por frente. Aqui:

1. Cada frente vinculada precisa do próprio piso, cumprido POR gente daquela
   frente — não pelo total misturado.
2. Cada frente vinculada também precisa de liderança própria: pelo menos
   `lideranca_minima_por_frente` pessoas com `posicao` gerente DAQUELA frente,
   ou diretor (que cobre qualquer frente, por já enxergar todas — §3).
3. Só depois de 1 e 2 cumpridos é que o resto das vagas (até o teto de
   `configuracao.vagas_por_banca`) pode vir de QUALQUER frente.
4. O coordenador do PRÓPRIO projeto (e o resto da equipe dele) nunca conta
   pra liderança — mesmo que a posição global da pessoa seja gerente. Ele já
   não pode se candidatar à própria banca (`create_candidatura`); aqui é a
   mesma exclusão, agora também pra contagem.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from sqlalchemy.orm import Session

from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository

LIDERANCA_POSICOES = ("gerente", "diretor")


@dataclass
class DeficitFrente:
    frente_id: int
    frente_nome: str
    piso_faltando: int = 0
    lideranca_faltando: int = 0


@dataclass
class StatusComposicao:
    deficits: List[DeficitFrente] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.deficits

    @property
    def piso_ok(self) -> bool:
        return all(d.piso_faltando == 0 for d in self.deficits)

    @property
    def lideranca_ok(self) -> bool:
        return all(d.lideranca_faltando == 0 for d in self.deficits)


class ComposicaoBancaChecker:
    def __init__(self, db: Session):
        self.usuario_frente_repository = UsuarioFrenteRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)

    def verificar(
        self,
        banca,
        frentes: List,
        candidato_ids: Set[int],
        lideranca_minima_por_frente: int,
    ) -> StatusComposicao:
        excluidos = self._excluidos_do_projeto(banca)
        usuarios_por_id = {u.id: u for u in self.usuario_repository.get_all()}
        diretores_presentes = {
            uid
            for uid in candidato_ids
            if uid not in excluidos and usuarios_por_id.get(uid) and usuarios_por_id[uid].posicao == "diretor"
        }

        deficits: List[DeficitFrente] = []
        for frente in frentes:
            membros_da_frente = {
                v.usuario_id for v in self.usuario_frente_repository.get_by_frente(frente.id)
            }
            presentes_da_frente = candidato_ids & membros_da_frente
            faltando_piso = max(0, frente.piso_banca - len(presentes_da_frente))

            gerentes_da_frente_presentes = {
                uid
                for uid in presentes_da_frente
                if uid not in excluidos
                and usuarios_por_id.get(uid)
                and usuarios_por_id[uid].posicao == "gerente"
            }
            lideres_presentes = gerentes_da_frente_presentes | diretores_presentes
            faltando_lideranca = max(0, lideranca_minima_por_frente - len(lideres_presentes))

            if faltando_piso or faltando_lideranca:
                deficits.append(
                    DeficitFrente(frente.id, frente.nome, faltando_piso, faltando_lideranca)
                )

        return StatusComposicao(deficits=deficits)

    def _excluidos_do_projeto(self, banca) -> Set[int]:
        excluidos = {e.usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id)}
        if banca.coordenador_id:
            excluidos.add(banca.coordenador_id)
        return excluidos

"""O mapa da carteira (Health Track §8 e §9): todos os projetos em curso que
a pessoa enxerga, com a cor vigente de cada pilar, o status geral e quem
coordena e gerencia cada um.

Os KPIs do topo da página NÃO vêm daqui: a tela os conta a partir destas
linhas, depois de aplicar os filtros (§17 pede que os KPIs respondam ao
filtro). Uma conta só, no front, em vez de uma no back pra cada combinação.
"""

from collections import defaultdict
from itertools import groupby
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.projeto_model import ProjetoModel
from src.repositories.frente_repository import FrenteRepository
from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.repositories.health_track_pilar_repository import HealthTrackPilarRepository
from src.repositories.health_track_regra_repository import HealthTrackRegraRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.health_track.serializar import serializar_pilar
from src.utils.health_track_status import ReguasStatus, calcular_status_geral, status_geral_ou_nada

#: Fora do mapa: nenhum dos dois está sendo trabalhado, então não tem saúde
#: a acompanhar. Mesma régua da carga do monitoramento.
FORA_DA_CARTEIRA = ("finalizado", "pausado")


class GetCarteiraUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.pilar_repo = HealthTrackPilarRepository(db)
        self.avaliacao_repo = HealthTrackAvaliacaoRepository(db)
        self.regra_repo = HealthTrackRegraRepository(db)
        self.frente_repo = FrenteRepository(db)
        self.projeto_frente_repo = ProjetoFrenteRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.usuario_frente_repo = UsuarioFrenteRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, current_user, frente_id: Optional[int] = None) -> dict:
        projetos: List[ProjetoModel] = (
            aplicar_recorte_visao(self.db.query(ProjetoModel), current_user, self.db, frente_id)
            .filter(ProjetoModel.arquivado_em.is_(None))
            .filter(ProjetoModel.institucional.is_(False))
            .filter(ProjetoModel.status.notin_(FORA_DA_CARTEIRA))
            .order_by(ProjetoModel.nome)
            .all()
        )
        ids = [p.id for p in projetos]
        pilares = self.pilar_repo.get_ativos()
        ids_pilares = [p.id for p in pilares]
        reguas = ReguasStatus(self.regra_repo.get_versoes())
        pessoas = {u.id: u for u in self.usuario_repo.get_all()}
        frentes = {f.id: f for f in self.frente_repo.get_all()}

        # Quem é de cada projeto: coordenadores pela equipe atual, gerentes
        # pelo vínculo de frente (`usuario_frente`), nunca pela equipe. É a
        # mesma régua que decide quem preenche.
        frentes_do_projeto: Dict[int, List[int]] = defaultdict(list)
        for v in self.projeto_frente_repo.get_by_projetos(ids):
            frentes_do_projeto[v.projeto_id].append(v.frente_id)
        gerentes_da_frente: Dict[int, List[int]] = defaultdict(list)
        for v in self.usuario_frente_repo.get_all():
            pessoa = pessoas.get(v.usuario_id)
            if pessoa and pessoa.posicao == "gerente" and pessoa.status == "ativo":
                gerentes_da_frente[v.frente_id].append(v.usuario_id)
        coordenadores: Dict[int, List[int]] = defaultdict(list)
        for m in self.membro_repo.get_by_projetos(ids, apenas_atuais=True):
            if m.papel == "coordenador":
                coordenadores[m.projeto_id].append(m.usuario_id)

        historico: Dict[int, list] = defaultdict(list)
        for a in self.avaliacao_repo.get_por_projetos(ids):
            historico[a.projeto_id].append(a)

        def pessoa(uid: int) -> dict:
            p = pessoas.get(uid)
            return {"id": uid, "nome": p.nome if p else f"Usuário {uid}"}

        linhas = []
        for projeto in projetos:
            linhas.append(
                {
                    "id": projeto.id,
                    "nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "status": projeto.status,
                    "frentes": [
                        {"id": fid, "nome": frentes[fid].nome if fid in frentes else f"Frente {fid}"}
                        for fid in frentes_do_projeto.get(projeto.id, [])
                    ],
                    "coordenadores": [pessoa(uid) for uid in coordenadores.get(projeto.id, [])],
                    "gerentes": [
                        pessoa(uid)
                        for uid in sorted(
                            {g for fid in frentes_do_projeto.get(projeto.id, []) for g in gerentes_da_frente.get(fid, [])}
                        )
                    ],
                    **_saude(historico.get(projeto.id, []), ids_pilares, reguas),
                }
            )

        return {"pilares": [serializar_pilar(p) for p in pilares], "projetos": linhas}


def _saude(historico: list, ids_pilares: List[int], reguas: ReguasStatus) -> dict:
    """A parte do Health Track de uma linha: a cor vigente de cada pilar
    ativo, o status geral e a tendência contra o ciclo anterior.

    `historico` vem da linha mais nova pra mais antiga. A cor vigente de um
    pilar é a primeira dele que aparece; o ciclo é o grupo de linhas com o
    mesmo `avaliado_em`. A tendência compara o status (pela regra ATUAL, pra
    comparar réguas iguais) dos dois últimos ciclos completos.
    """
    ultimas: Dict[int, object] = {}
    for a in historico:
        ultimas.setdefault(a.pilar_id, a)
    cores = {pid: ultimas[pid].cor for pid in ids_pilares if pid in ultimas}
    pilares = {
        str(pid): {"cor": ultimas[pid].cor, "avaliado_em": ultimas[pid].avaliado_em} if pid in ultimas else None
        for pid in ids_pilares
    }
    mais_recente = max((a.avaliado_em for a in ultimas.values()), default=None)
    status = status_geral_ou_nada(
        [cores.get(pid) for pid in ids_pilares], mais_recente, reguas
    )

    regra_atual = reguas.atual()
    ciclos_completos = []
    for avaliado_em, grupo in groupby(historico, key=lambda a: a.avaliado_em):
        grupo = list(grupo)
        if regra_atual and {a.pilar_id for a in grupo} >= set(ids_pilares):
            ciclos_completos.append(calcular_status_geral([a.cor for a in grupo], regra_atual))
        if len(ciclos_completos) == 2:
            break
    status_anterior = ciclos_completos[1] if len(ciclos_completos) == 2 else None

    return {
        "pilares": pilares,
        "status_geral": status,
        "status_anterior": status_anterior,
        "avaliado_em": mais_recente,
        "total_ciclos": len({a.avaliado_em for a in historico}),
        "algum_vermelho": any(c == "vermelho" for c in cores.values()),
    }

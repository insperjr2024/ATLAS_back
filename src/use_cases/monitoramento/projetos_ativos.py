"""A aba **Projetos ativos** do painel (§7) — o retrato dos projetos EM CURSO.

O espelho da aba Histórico, mas para o que ainda está aberto: tudo que não foi
finalizado nem arquivado. Mesma régua do resto do Monitoramento — zero tabela
nova, abre com `aplicar_recorte_visao` (§7.5), e traz por projeto o coordenador,
as frentes, o status, há quantos dias está em execução e a próxima banca.

🔐 Sem autorização própria: o recorte de visão é a regra, e a rota exige
`pode_ver_monitoramento` como as outras abas de números.
"""

from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.middlewares.authorization import aplicar_recorte_visao
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository


class ProjetosAtivosUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.frente_repo = FrenteRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.escopo_repo = ProjetoEscopoRepository(db)
        self.banca_repo = BancaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, current_user, frente_id: Optional[int] = None) -> list[dict]:
        hoje = date.today()

        query = aplicar_recorte_visao(
            self.db.query(ProjetoModel), current_user, self.db, frente_id
        )
        # Ativo = ainda aberto: nem finalizado, nem arquivado. O `!=` cobre
        # todos os status do ciclo (vendido → período de ajustes) e o pausado.
        projetos = [
            p
            for p in query.all()
            if p.status != "finalizado" and p.arquivado_em is None
        ]
        if not projetos:
            return []

        ids = [p.id for p in projetos]
        nome_da_frente = {f.id: f.nome for f in self.frente_repo.get_all()}
        nome_da_pessoa = {u.id: u.nome for u in self.usuario_repo.get_all()}

        frentes_por_projeto = defaultdict(list)
        for pf in self.db.query(ProjetoFrenteModel).filter(
            ProjetoFrenteModel.projeto_id.in_(ids)
        ):
            frentes_por_projeto[pf.projeto_id].append(pf.frente_id)

        # Coordenador atual de cada projeto (o membro sem `saiu_em`), em bloco.
        coord_por_projeto: dict[int, int] = {}
        for m in self.membro_repo.get_by_projetos(ids, apenas_atuais=True):
            if m.papel == "coordenador":
                coord_por_projeto[m.projeto_id] = m.usuario_id

        proxima_por_projeto = self._proximas_bancas(ids)

        linhas = []
        for p in projetos:
            frente_ids = frentes_por_projeto.get(p.id, [])
            coord = coord_por_projeto.get(p.id)
            proxima = proxima_por_projeto.get(p.id)
            linhas.append(
                {
                    "id": p.id,
                    "nome": p.nome,
                    "cliente": p.cliente,
                    "status": p.status,
                    "frentes": [nome_da_frente.get(fid) for fid in frente_ids],
                    "frente_ids": frente_ids,
                    "sinergico": len(frente_ids) > 1,
                    "coordenador": nome_da_pessoa.get(coord) if coord else None,
                    "coordenador_id": coord,
                    "data_kickoff": p.data_kickoff,
                    # Sem kickoff, o projeto ainda não "está em execução" — é o
                    # alerta de kickoff pendente (§5.1), não zero dias.
                    "dias_em_execucao": (hoje - p.data_kickoff).days if p.data_kickoff else None,
                    "kickoff_pendente": p.data_kickoff is None,
                    # A banca mais próxima ainda não realizada, de qualquer escopo.
                    "proxima_banca": proxima.data_hora if proxima else None,
                }
            )

        # Do que está há mais tempo em execução para o mais novo — o topo é onde
        # a atenção costuma ser mais urgente. `-1` põe o sem-kickoff por último.
        linhas.sort(key=lambda l: l["dias_em_execucao"] if l["dias_em_execucao"] is not None else -1, reverse=True)
        return linhas

    def _proximas_bancas(self, ids: list[int]) -> dict[int, object]:
        """A próxima banca não realizada de cada projeto — busca em bloco, como
        a listagem de projetos (§6.2), para não virar uma query por linha."""
        escopos = self.escopo_repo.get_by_projetos(ids)
        projeto_por_escopo = {e.id: e.projeto_id for e in escopos}
        banca_por_escopo = self.banca_repo.mapa_por_escopo(list(projeto_por_escopo))

        proxima: dict[int, object] = {}
        for escopo_id, banca in banca_por_escopo.items():
            if banca.data_hora is None or banca.realizado_em is not None:
                continue
            projeto_id = projeto_por_escopo.get(escopo_id)
            atual = proxima.get(projeto_id)
            if projeto_id and (atual is None or banca.data_hora < atual.data_hora):
                proxima[projeto_id] = banca
        return proxima

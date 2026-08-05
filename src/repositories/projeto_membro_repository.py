from typing import Dict, List, Optional

from sqlalchemy import func

from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.repositories.base_repository import BaseRepository


class ProjetoMembroRepository(BaseRepository[ProjetoMembroModel]):
    model = ProjetoMembroModel

    def get_by_projeto(self, projeto_id: int, apenas_atuais: bool = False) -> List[ProjetoMembroModel]:
        query = self.db.query(ProjetoMembroModel).filter(ProjetoMembroModel.projeto_id == projeto_id)
        if apenas_atuais:
            query = query.filter(ProjetoMembroModel.saiu_em.is_(None))
        return query.all()

    def get_by_projetos(self, projeto_ids: List[int], apenas_atuais: bool = False) -> List[ProjetoMembroModel]:
        """Em lote — o monitoramento (§7.3) precisa da carga de todo mundo
        sem fazer uma consulta por projeto."""
        if not projeto_ids:
            return []
        query = self.db.query(ProjetoMembroModel).filter(
            ProjetoMembroModel.projeto_id.in_(projeto_ids)
        )
        if apenas_atuais:
            query = query.filter(ProjetoMembroModel.saiu_em.is_(None))
        return query.all()

    def get_atuais_por_usuario(self, usuario_id: int) -> List[ProjetoMembroModel]:
        return (
            self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .all()
        )

    def contar_ativos_por_usuario(self) -> Dict[int, int]:
        """Quantos projetos cada pessoa toca hoje, numa consulta só.

        Mesma régua de carga do §7.3 (`AlocacaoUseCase`): projeto finalizado
        ou arquivado não ocupa ninguém. Sem recorte de visão de propósito —
        quem monta a equipe precisa saber que a pessoa já está alocada mesmo
        em frente que ela própria não enxerga; vai só o número, nunca o nome
        dos projetos.
        """
        linhas = (
            self.db.query(
                ProjetoMembroModel.usuario_id,
                func.count(func.distinct(ProjetoMembroModel.projeto_id)),
            )
            .join(ProjetoModel, ProjetoModel.id == ProjetoMembroModel.projeto_id)
            .filter(
                ProjetoMembroModel.saiu_em.is_(None),
                ProjetoModel.arquivado_em.is_(None),
                ProjetoModel.status != "finalizado",
            )
            .group_by(ProjetoMembroModel.usuario_id)
            .all()
        )
        return {usuario_id: total for usuario_id, total in linhas}

    def get_atual_do_usuario_no_projeto(self, projeto_id: int, usuario_id: int) -> Optional[ProjetoMembroModel]:
        return (
            self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.projeto_id == projeto_id,
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .first()
        )

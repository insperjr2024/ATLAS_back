from typing import Optional
from sqlalchemy.orm import Session
from src.repositories.banca_repository import BancaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.utils.filtrar_historico_bancas import filtrar_historico_bancas
from src.utils.banca_nota import calcular_nota_final
from src.utils.identificar_semestre import identificar_semestre


class GetHistoricoBancasUseCase:
    def __init__(self, db: Session):
        self.banca_repository = BancaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.avaliacao_nota_repository = AvaliacaoNotaRepository(db)

    def execute(self, consultor_id: Optional[int] = None, coordenador_id: Optional[int] = None,
                escopo_id: Optional[int] = None, semestre_id: Optional[int] = None):
        bancas = self.banca_repository.get_all()
        equipes = self.equipe_projeto_repository.get_all()
        semestres = self.semestre_repository.get_all()

        bancas_filtradas = filtrar_historico_bancas(
            bancas, equipes, semestres,
            consultor_id=consultor_id,
            coordenador_id=coordenador_id,
            escopo_id=escopo_id,
            semestre_id=semestre_id
        )

        resultado = []
        for banca in bancas_filtradas:
            notas = self.avaliacao_nota_repository.get_by_banca(banca.id)
            semestre = identificar_semestre(banca.data_hora, semestres)
            resultado.append({
                "id": banca.id,
                "nome_projeto": banca.nome_projeto,
                "escopo_id": banca.escopo_id,
                "coordenador_id": banca.coordenador_id,
                "data_hora": banca.data_hora,
                "nota_final": calcular_nota_final(notas),
                "semestre_id": semestre.id if semestre else None,
                "semestre_nome": semestre.nome if semestre else None
            })
        return resultado
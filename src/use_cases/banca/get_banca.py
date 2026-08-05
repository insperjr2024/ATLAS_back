from sqlalchemy.orm import Session
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.identificar_semestre import identificar_semestre


class GetBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, banca_id: int):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None
        candidaturas = self.candidatura_repository.get_by_banca(banca_id)
        configuracao = self.configuracao_repository.get()
        vagas = configuracao.vagas_por_banca if configuracao else 5
        semestres = self.semestre_repository.get_all()
        semestre = identificar_semestre(banca.data_hora, semestres)
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            "projeto_escopo_id": banca.projeto_escopo_id,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            "vagas": vagas,
            "alocados": len(candidaturas),
            "piso_minimo_override": banca.piso_minimo_override,
            "semestre_id": semestre.id if semestre else None,
            "semestre_nome": semestre.nome if semestre else None
        }


class ListBancasUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self):
        bancas = self.repository.get_all()
        configuracao = self.configuracao_repository.get()
        vagas = configuracao.vagas_por_banca if configuracao else 5
        semestres = self.semestre_repository.get_all()
        resultado = []
        for b in bancas:
            candidaturas = self.candidatura_repository.get_by_banca(b.id)
            semestre = identificar_semestre(b.data_hora, semestres)
            resultado.append({
                "id": b.id,
                "nome_projeto": b.nome_projeto,
                "escopo_id": b.escopo_id,
                "coordenador_id": b.coordenador_id,
                "data_hora": b.data_hora,
                "projeto_escopo_id": b.projeto_escopo_id,
                "realizado_em": b.realizado_em,
                "resultado": b.resultado,
                "status": calcular_status_banca(b.data_hora, b.realizado_em),
                "vagas": vagas,
                "alocados": len(candidaturas),
                "piso_minimo_override": b.piso_minimo_override,
                "semestre_id": semestre.id if semestre else None,
                "semestre_nome": semestre.nome if semestre else None
            })
        return resultado
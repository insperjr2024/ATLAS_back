from typing import Optional
from sqlalchemy.orm import Session
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.utils.escopos_da_banca import nome_do_escopo
from src.utils.filtrar_historico_bancas import filtrar_historico_bancas
from src.utils.banca_nota import calcular_nota_final
from src.utils.identificar_semestre import identificar_semestre


class GetHistoricoBancasUseCase:
    def __init__(self, db: Session):
        self.banca_repository = BancaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.avaliacao_nota_repository = AvaliacaoNotaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

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

        # ⭐ Uma banca pode cobrir MAIS de um escopo do projeto de uma sentada
        # (`banca_escopo`) — `escopo_id` sozinho é só o campo legado de UM, e
        # mandar só ele escondia o resto quando a banca cobria mais de um
        # (mesmo buraco já corrigido no "ver mais" da tela de Bancas). Duas
        # consultas em lote em vez de uma por banca — é lista, não ficha.
        escopo_ids_por_banca = self.banca_escopo_repository.get_escopo_ids_por_banca(
            [b.id for b in bancas_filtradas]
        )
        todos_os_escopo_ids = {eid for ids in escopo_ids_por_banca.values() for eid in ids}
        pe_por_id = {
            pe.id: pe for pe in self.escopo_repository.get_by_ids(list(todos_os_escopo_ids))
        }

        linhas = []
        for banca in bancas_filtradas:
            notas = self.avaliacao_nota_repository.get_by_banca(banca.id)
            semestre = identificar_semestre(banca.data_hora, semestres)
            escopo_ids_da_banca = escopo_ids_por_banca.get(banca.id, [])
            if escopo_ids_da_banca:
                escopos_nomes = [
                    nome_do_escopo(pe_por_id[eid], self.catalogo_repository)
                    for eid in escopo_ids_da_banca
                    if eid in pe_por_id
                ]
            elif banca.escopo_id:
                # Banca legada, sem `banca_escopo`: o único escopo dela é o
                # do catálogo gravado direto na coluna.
                do_catalogo = self.catalogo_repository.get_by_id(banca.escopo_id)
                escopos_nomes = [do_catalogo.nome] if do_catalogo else []
            else:
                escopos_nomes = []
            linhas.append({
                "id": banca.id,
                "nome_projeto": banca.nome_projeto,
                "escopo_id": banca.escopo_id,
                # Plural resolvido — banca legada (sem `banca_escopo`) cai
                # numa lista de 1 com o mesmo nome que `escopo_id` já dava.
                "escopos": escopos_nomes,
                "coordenador_id": banca.coordenador_id,
                "data_hora": banca.data_hora,
                "nota_final": calcular_nota_final(notas),
                "semestre_id": semestre.id if semestre else None,
                "semestre_nome": semestre.nome if semestre else None,
                # O relato do coordenador ao lado da nota dos avaliadores — os
                # dois lados da mesma banca na mesma tela de acompanhamento.
                "descricao_coordenador": banca.descricao_coordenador,
                "descricao_coordenador_enviada_em": banca.descricao_coordenador_enviada_em,
                # ⭐ "aprovada" | "nao_aprovada" | `None` (aconteceu, mas ainda
                # esperando diretoria ou gerente decidir — ver
                # `use_cases/banca/aprovar_banca.py`). Sem isto, o histórico
                # de bancas não tinha onde mostrar o veredito.
                "resultado": banca.resultado,
            })
        return linhas
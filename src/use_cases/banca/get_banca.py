from sqlalchemy.orm import Session
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.identificar_semestre import identificar_semestre
from src.utils.piso_banca import calcular_piso_banca
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.utils.equipe_banca import membros_da_banca


class GetBancaUseCase:
    def __init__(self, db: Session):
        #: A sessão, para `calcular_piso_banca` ler a matriz de composição.
        self.db = db
        self.repository = BancaRepository(db)
        self.vendedor_repository = ProjetoVendedorRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)

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
            # Os escopos vendidos que esta banca cobre — vazio nas legadas.
            "projeto_escopo_ids": self.banca_escopo_repository.get_escopo_ids(banca.id),
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            "vagas": vagas,
            "alocados": len(candidaturas),
            "piso_minimo_override": banca.piso_minimo_override,
            "descricao_coordenador": banca.descricao_coordenador,
            "descricao_coordenador_enviada_em": banca.descricao_coordenador_enviada_em,
            # O piso REAL da composição (§8), já resolvido: override, senão a
            # soma do `piso_banca` das frentes. `vagas` acima é outra coisa —
            # é o teto de quantos cabem. Sem este campo a tela tinha de
            # reimplementar a regra, e usava o teto por engano.
            "piso_minimo": self._piso(banca),
            # ⭐ §8: quem NÃO pode avaliar esta banca por ser do grupo dela.
            # Sai daqui, e não do `equipe_projeto` sozinho, porque banca
            # marcada pelo cronograma não escreve naquela tabela legada — a
            # equipe real é a do projeto dos escopos cobertos.
            "equipe_ids": sorted(
                membros_da_banca(
                    banca,
                    self.banca_escopo_repository,
                    self.escopo_repository,
                    self.membro_repository,
                    self.equipe_projeto_repository,
                    self.vendedor_repository,
                )
            ),
            "semestre_id": semestre.id if semestre else None,
            "semestre_nome": semestre.nome if semestre else None
        }

    def _piso(self, banca) -> int:
        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        frentes = [f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos) if f]
        return calcular_piso_banca(banca, frentes, self.db)


class ListBancasUseCase:
    def __init__(self, db: Session):
        # ⚠ A sessão em si, e não só os repositórios: `calcular_piso_banca`
        # precisa dela para ler a matriz de composição (2026-09-01). Sem esta
        # linha, `GET /bancas` devolve 500 — foi o que aconteceu, pela segunda
        # vez nesta classe, pelo mesmo motivo descrito abaixo.
        self.db = db
        self.repository = BancaRepository(db)
        # ⚠ Este arquivo tem DUAS classes, e as duas chamam `membros_da_banca`.
        # Quando o vendedor entrou no §8 (2026-08-20), o repositório foi
        # acrescentado só no `__init__` da primeira — esta ficou usando um
        # atributo que nunca existiu, e `GET /bancas` passou a devolver 500.
        self.vendedor_repository = ProjetoVendedorRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)

    def execute(self):
        bancas = self.repository.get_all()
        configuracao = self.configuracao_repository.get()
        vagas = configuracao.vagas_por_banca if configuracao else 5
        semestres = self.semestre_repository.get_all()
        escopos_por_banca = self.banca_escopo_repository.get_escopo_ids_por_banca(
            [b.id for b in bancas]
        )
        # As frentes uma vez só: o piso de cada banca é a soma dos pisos delas,
        # e buscar por banca dentro do laço seria N+1.
        frentes_por_id = {f.id: f for f in self.frente_repository.get_all()}
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
                "projeto_escopo_ids": escopos_por_banca.get(b.id, []),
                "realizado_em": b.realizado_em,
                "resultado": b.resultado,
                "status": calcular_status_banca(b.data_hora, b.realizado_em),
                "vagas": vagas,
                "alocados": len(candidaturas),
                "piso_minimo_override": b.piso_minimo_override,
                "descricao_coordenador": b.descricao_coordenador,
                "descricao_coordenador_enviada_em": b.descricao_coordenador_enviada_em,
                "piso_minimo": calcular_piso_banca(
                    b,
                    [
                        frentes_por_id[v.frente_id]
                        for v in self.banca_frente_repository.get_by_banca(b.id)
                        if v.frente_id in frentes_por_id
                    ],
                    self.db,
                ),
                "equipe_ids": sorted(
                    membros_da_banca(
                        b,
                        self.banca_escopo_repository,
                        self.escopo_repository,
                        self.membro_repository,
                        self.equipe_projeto_repository,
                        self.vendedor_repository,
                    )
                ),
                "semestre_id": semestre.id if semestre else None,
                "semestre_nome": semestre.nome if semestre else None
            })
        return resultado
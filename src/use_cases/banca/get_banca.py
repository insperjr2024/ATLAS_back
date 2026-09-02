from sqlalchemy.orm import Session
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.identificar_semestre import identificar_semestre
from src.utils.piso_banca import calcular_piso_banca
from src.utils.teto_banca import calcular_vagas_banca
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.utils.composicao_banca import ComposicaoBancaChecker
from src.utils.equipe_banca import membros_da_banca


def composicao_da_banca(banca, frentes, candidatura_usuario_ids, checker, resolver) -> list:
    """⭐ A composição desta banca, frente a frente — o que a matriz de
    Configurações exige e o que a banca TEM (2026-09-02).

    Existe porque `piso_minimo` é uma soma: ele diz "faltam 2" e não diz de
    quê. A aba Bancas precisa da quebra para dizer "falta 1 de Direito", e
    calculá-la no front exigiria repetir aqui a regra da liderança, a exclusão
    da equipe do projeto e a leitura da matriz — três coisas que já vivem no
    `ComposicaoBancaChecker`.

    `checker` e `resolver` vêm de fora porque a listagem monta isto para todas
    as bancas do semestre: um por requisição, com os caches deles quentes,
    em vez de um por banca.
    """
    if not frentes:
        # Banca legada, sem frente vinculada: não há combinação e não há o que
        # exigir por frente. Devolver `[]` (e não erro) deixa a tela mostrar
        # só o teto, que é o que sempre valeu para ela.
        return []
    regras = resolver.para([f.id for f in frentes])
    return [
        {
            "frente_id": c.frente_id,
            "frente_nome": c.frente_nome,
            "min_membros": c.min_membros,
            "max_membros": c.max_membros,
            "min_lideranca": c.min_lideranca,
            "max_lideranca": c.max_lideranca,
            "membros": c.membros,
            "liderancas": c.liderancas,
        }
        for c in checker.contar(banca, regras, set(candidatura_usuario_ids))
    ]


class GetBancaUseCase:
    def __init__(self, db: Session):
        #: A sessão, para `calcular_piso_banca` ler a matriz de composição.
        self.db = db
        self.repository = BancaRepository(db)
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
        # Uma vez só: os três números abaixo (teto, piso e composição) saem
        # todos das frentes vinculadas, e cada `_frentes` é uma consulta.
        frentes = self._frentes(banca)
        # ⭐ O teto é da COMBINAÇÃO de frentes desde 2026-09-02 (antes era o
        # global `configuracao.vagas_por_banca`, o mesmo em toda banca). Quem
        # não configurou continua no global — ver `utils/teto_banca.py`.
        vagas = calcular_vagas_banca(frentes, self.db)
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
            "piso_minimo": calcular_piso_banca(banca, frentes, self.db),
            # A mesma exigência do `piso_minimo` acima, aberta por frente —
            # ver `composicao_da_banca`.
            "composicao": self._composicao(banca, frentes, candidaturas),
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
                )
            ),
            "semestre_id": semestre.id if semestre else None,
            "semestre_nome": semestre.nome if semestre else None
        }

    def _frentes(self, banca):
        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        return [f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos) if f]

    def _composicao(self, banca, frentes, candidaturas) -> list:
        from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

        return composicao_da_banca(
            banca,
            frentes,
            [c.usuario_id for c in candidaturas],
            ComposicaoBancaChecker(self.db),
            ResolverComposicaoUseCase(self.db),
        )


class ListBancasUseCase:
    def __init__(self, db: Session):
        # ⚠ A sessão em si, e não só os repositórios: `calcular_piso_banca`
        # precisa dela para ler a matriz de composição (2026-09-01). Sem esta
        # linha, `GET /bancas` devolve 500 — foi o que aconteceu, pela segunda
        # vez nesta classe, pelo mesmo motivo descrito abaixo.
        self.db = db
        self.repository = BancaRepository(db)
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
        from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

        bancas = self.repository.get_all()
        # ⚠ Um checker e um resolver para a listagem INTEIRA: os dois guardam
        # em cache o que leram (usuários, vínculos de frente, regras), e um
        # por banca devolveria a varredura de usuários por linha que este
        # `execute` evita desde sempre.
        checker = ComposicaoBancaChecker(self.db)
        resolver = ResolverComposicaoUseCase(self.db)
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
            frentes_da_banca = [
                frentes_por_id[v.frente_id]
                for v in self.banca_frente_repository.get_by_banca(b.id)
                if v.frente_id in frentes_por_id
            ]
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
                # O teto da combinação desta banca — o resolver acima já
                # guarda em cache o que leu, então a lista não repete a
                # consulta por linha.
                "vagas": resolver.vagas_da_combinacao([f.id for f in frentes_da_banca]),
                "alocados": len(candidaturas),
                "piso_minimo_override": b.piso_minimo_override,
                "descricao_coordenador": b.descricao_coordenador,
                "descricao_coordenador_enviada_em": b.descricao_coordenador_enviada_em,
                "piso_minimo": calcular_piso_banca(b, frentes_da_banca, self.db),
                "composicao": composicao_da_banca(
                    b,
                    frentes_da_banca,
                    [c.usuario_id for c in candidaturas],
                    checker,
                    resolver,
                ),
                "equipe_ids": sorted(
                    membros_da_banca(
                        b,
                        self.banca_escopo_repository,
                        self.escopo_repository,
                        self.membro_repository,
                        self.equipe_projeto_repository,
                    )
                ),
                "semestre_id": semestre.id if semestre else None,
                "semestre_nome": semestre.nome if semestre else None
            })
        return resultado
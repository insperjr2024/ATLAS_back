"""A regra de composição que vale para uma banca — configurada ou padrão.

⭐ **Ausência de configuração não é erro.** A tela de Configurações lista as
2ⁿ−1 combinações possíveis (15 com as 4 frentes de hoje), e ninguém vai
preencher todas. A combinação sem linha em `banca_composicao_regra` cai no
PADRÃO, derivado do que já existia antes desta tabela:

- `min_membros` = `frente.piso_banca` (Business 3 · Tech 2 · Processos 2 ·
  Direito 1);
- `min_lideranca` = `configuracao.lideranca_minima_por_frente` (hoje 1);
- os máximos ficam soltos (`SEM_TETO`), que é o comportamento de sempre — não
  havia teto por frente antes desta mudança.

É isso que faz a virada não mexer em nenhuma banca já marcada, e que deixa uma
frente cadastrada amanhã já ter regra em toda combinação sem migration.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.repositories.banca_composicao_regra_repository import (
    BancaComposicaoRegraRepository,
)
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.frente_repository import FrenteRepository
from pydantic import BaseModel

from src.utils.combinacao_frentes import chave, ler, todas
from src.utils.exceptions import RegraDeNegocioError

#: O teto de quem não configurou teto. Um número, e não `None`, para a
#: comparação na checagem ser sempre a mesma — `presentes > teto` funciona
#: igual configurado ou não, sem um `if` para o caso nulo.
SEM_TETO = 99


@dataclass
class RegraDaFrente:
    frente_id: int
    frente_nome: str
    min_membros: int
    max_membros: int
    min_lideranca: int
    max_lideranca: int
    #: `False` quando estes números são o padrão, e não algo que alguém gravou.
    #: A tela mostra isso para a diretoria saber o que está herdado.
    configurada: bool = False

    @property
    def minimo_de_pessoas(self) -> int:
        """⚠ Liderança é vaga A MAIS (2026-09-01): a banca de Business pede 3
        membros **e** 1 liderança, quatro pessoas. Antes o gerente cabia
        dentro do piso."""
        return self.min_membros + self.min_lideranca


class ResolverComposicaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaComposicaoRegraRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)

    def para(self, frente_ids: List[int]) -> List[RegraDaFrente]:
        """A regra de cada frente da combinação, na ordem dos ids."""
        combinacao = chave(frente_ids)
        gravadas = self.repository.get_por_frente(combinacao)
        frentes = {f.id: f for f in self.frente_repository.get_all()}
        padrao_lideranca = self._lideranca_padrao()

        regras = []
        for frente_id in sorted(set(frente_ids)):
            frente = frentes.get(frente_id)
            if not frente:
                continue
            gravada = gravadas.get(frente_id)
            if gravada:
                regras.append(
                    RegraDaFrente(
                        frente_id=frente_id,
                        frente_nome=frente.nome,
                        min_membros=gravada.min_membros,
                        max_membros=gravada.max_membros,
                        min_lideranca=gravada.min_lideranca,
                        max_lideranca=gravada.max_lideranca,
                        configurada=True,
                    )
                )
            else:
                regras.append(
                    RegraDaFrente(
                        frente_id=frente_id,
                        frente_nome=frente.nome,
                        min_membros=frente.piso_banca,
                        max_membros=SEM_TETO,
                        min_lideranca=padrao_lideranca,
                        max_lideranca=SEM_TETO,
                        configurada=False,
                    )
                )
        return regras

    def _lideranca_padrao(self) -> int:
        config = self.configuracao_repository.get()
        return getattr(config, "lideranca_minima_por_frente", 1) if config else 1

    def listar_combinacoes(self) -> List[dict]:
        """O seletor da tela: toda combinação possível, com o resumo do que
        ela exige hoje. Só ATIVAS — frente desativada não entra em banca nova,
        e listá-la dobraria o seletor com combinações que ninguém usa."""
        frentes = [f for f in self.frente_repository.get_all() if f.ativa]
        combinacoes = []
        for ids in todas([f.id for f in frentes]):
            regras = self.para(ids)
            combinacoes.append(
                {
                    "combinacao": chave(ids),
                    "frente_ids": ids,
                    "rotulo": " + ".join(r.frente_nome for r in regras),
                    "sinergica": len(ids) > 1,
                    "minimo_total": sum(r.minimo_de_pessoas for r in regras),
                    "configurada": any(r.configurada for r in regras),
                }
            )
        return combinacoes


class SalvarComposicaoRequest(BaseModel):
    """O que a tela manda ao salvar UMA combinação.

    ⚠ A lista traz todas as frentes da combinação, sempre — a tela edita a
    combinação inteira de uma vez, e o repositório apaga e recria. Mandar só a
    frente alterada deixaria as outras sem linha, caindo no padrão em
    silêncio.
    """

    frentes: List["FrenteRegraRequest"]


class FrenteRegraRequest(BaseModel):
    frente_id: int
    min_membros: int
    max_membros: int
    min_lideranca: int
    max_lideranca: int


SalvarComposicaoRequest.model_rebuild()


class SalvarComposicaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaComposicaoRegraRepository(db)
        self.resolver = ResolverComposicaoUseCase(db)

    def execute(self, frente_ids: List[int], request: SalvarComposicaoRequest) -> dict:
        combinacao = chave(frente_ids)
        if not combinacao:
            raise RegraDeNegocioError("Escolha ao menos uma frente")

        esperadas = set(ler(combinacao))
        enviadas = {f.frente_id for f in request.frentes}
        # ⚠ Salvar uma combinação sem uma das frentes dela deixaria essa frente
        # caindo no padrão sem ninguém perceber — e a tela mostraria números
        # que não são os que estão valendo.
        if enviadas != esperadas:
            raise RegraDeNegocioError(
                "A regra precisa trazer exatamente as frentes desta combinação"
            )

        for f in request.frentes:
            self._validar(f)

        self.repository.definir(
            combinacao,
            [
                {
                    "frente_id": f.frente_id,
                    "min_membros": f.min_membros,
                    "max_membros": f.max_membros,
                    "min_lideranca": f.min_lideranca,
                    "max_lideranca": f.max_lideranca,
                }
                for f in request.frentes
            ],
        )
        return {"combinacao": combinacao, "frentes": len(request.frentes)}

    def _validar(self, f: "FrenteRegraRequest") -> None:
        if f.min_membros < 0 or f.min_lideranca < 0:
            raise RegraDeNegocioError("Os mínimos não podem ser negativos")
        if f.max_membros < f.min_membros:
            raise RegraDeNegocioError(
                "O máximo de membros não pode ser menor que o mínimo"
            )
        if f.max_lideranca < f.min_lideranca:
            raise RegraDeNegocioError(
                "O máximo de lideranças não pode ser menor que o mínimo"
            )
        # Uma banca sem ninguém não avalia nada. O zero é legítimo em UM dos
        # dois (uma frente pode entrar só com liderança, ou só com membros),
        # mas não nos dois.
        if f.min_membros == 0 and f.min_lideranca == 0:
            raise RegraDeNegocioError(
                "Cada frente precisa exigir ao menos uma pessoa, membro ou liderança"
            )

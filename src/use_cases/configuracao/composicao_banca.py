"""A regra de composição que vale para uma banca — configurada ou padrão.

⭐ **Ausência de configuração não é erro.** A tela de Configurações lista as
2ⁿ−1 combinações possíveis (15 com as 4 frentes de hoje), e ninguém vai
preencher todas. A combinação sem linha em `banca_composicao_regra` cai no
PADRÃO, derivado do que já existia antes desta tabela:

- `min_membros` = `frente.piso_banca` (Business 3 · Tech 2 · Processos 2 ·
  Direito 1);
- `min_lideranca` = `configuracao.lideranca_minima_por_frente` (hoje 1).

É isso que faz a virada não mexer em nenhuma banca já marcada, e que deixa uma
frente cadastrada amanhã já ter regra em toda combinação sem migration.

⚠ **Não há teto por frente (2026-09-03).** O piso tem de ser gente daquela
frente; completar acima dele, até o TOTAL da banca (`vagas`), é "tanto faz a
frente". Os campos `max_membros`/`max_lideranca` foram removidos da tabela e
da tela.
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


@dataclass
class RegraDaFrente:
    frente_id: int
    frente_nome: str
    min_membros: int
    min_lideranca: int
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
        self._cache: Dict[str, List[RegraDaFrente]] = {}
        self._cache_frentes: Optional[Dict[int, object]] = None
        self._cache_lideranca: Optional[int] = None
        self._cache_vagas: Dict[str, Optional[int]] = {}

    def para(self, frente_ids: List[int]) -> List[RegraDaFrente]:
        """A regra de cada frente da combinação, na ordem dos ids.

        ⚠ O resultado fica em cache NA INSTÂNCIA. `GET /bancas` pergunta uma
        vez por banca, e a maioria das bancas do semestre repete um punhado de
        combinações — sem o cache, cada linha da lista custava uma varredura
        de frentes, uma leitura da configuração e uma consulta às regras. O
        cache dura o que a instância durar: uma requisição.
        """
        combinacao = chave(frente_ids)
        if combinacao in self._cache:
            return self._cache[combinacao]
        gravadas = self.repository.get_por_frente(combinacao)
        frentes = self._frentes()
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
                        min_lideranca=gravada.min_lideranca,
                        configurada=True,
                    )
                )
            else:
                regras.append(
                    RegraDaFrente(
                        frente_id=frente_id,
                        frente_nome=frente.nome,
                        min_membros=frente.piso_banca,
                        min_lideranca=padrao_lideranca,
                        configurada=False,
                    )
                )
        self._cache[combinacao] = regras
        return regras

    def vagas_da_combinacao(self, frente_ids: List[int]) -> int:
        """⭐ Quantas pessoas cabem numa banca desta combinação (2026-09-02).

        O teto era um número só para a plataforma inteira: a banca de Direito
        sozinha (que exige 2 pessoas) e a de Business + Tech + Processos (que
        exige 9) cabiam o mesmo tanto de gente.

        Combinação sem valor próprio cai em `configuracao.vagas_por_banca` —
        o global continua sendo o padrão, e é o que vale também para a banca
        legada, que não tem frente vinculada e por isso não cai em combinação
        nenhuma.
        """
        propria = self.vagas_proprias_da_combinacao(frente_ids)
        return propria if propria is not None else self._vagas_padrao()

    def vagas_proprias_da_combinacao(self, frente_ids: List[int]) -> Optional[int]:
        """O teto GRAVADO desta combinação, ou `None` se ela não tem um.

        Separado de `vagas_da_combinacao` para quem já tem em mãos o padrão a
        aplicar e só quer saber se a combinação manda outra coisa — é o caso
        do push automático, que lê o global uma vez para a passada inteira.
        """
        combinacao = chave(frente_ids)
        if not combinacao:
            return None
        if combinacao not in self._cache_vagas:
            gravadas = self.repository.get_por_frente(combinacao)
            self._cache_vagas[combinacao] = next(
                (r.vagas for r in gravadas.values() if getattr(r, "vagas", None) is not None),
                None,
            )
        return self._cache_vagas[combinacao]

    def _vagas_padrao(self) -> int:
        config = self.configuracao_repository.get()
        # `getattr` com padrão: o mesmo motivo de `_lideranca_padrao` — a
        # configuração pode não existir ainda em base recém-criada.
        return getattr(config, "vagas_por_banca", 5) if config else 5

    def _frentes(self) -> Dict[int, object]:
        if self._cache_frentes is None:
            self._cache_frentes = {f.id: f for f in self.frente_repository.get_all()}
        return self._cache_frentes

    def _lideranca_padrao(self) -> int:
        if self._cache_lideranca is None:
            config = self.configuracao_repository.get()
            self._cache_lideranca = (
                getattr(config, "lideranca_minima_por_frente", 1) if config else 1
            )
        return self._cache_lideranca

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
                    "vagas": self.vagas_da_combinacao(ids),
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
    #: O teto de quantos cabem numa banca desta combinação. `None` = seguir o
    #: global (`configuracao.vagas_por_banca`), que é o padrão de sempre.
    vagas: Optional[int] = None


class FrenteRegraRequest(BaseModel):
    frente_id: int
    min_membros: int
    min_lideranca: int


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

        minimo_total = sum(f.min_membros + f.min_lideranca for f in request.frentes)
        if request.vagas is not None:
            if request.vagas < 1:
                raise RegraDeNegocioError("O teto de vagas precisa ser de ao menos 1")
            # ⚠ Teto menor que o mínimo é uma banca impossível: ela nunca
            # fecharia a composição, e a inscrição recusaria com "banca
            # lotada" antes de alguém completar o que ela exige.
            if request.vagas < minimo_total:
                raise RegraDeNegocioError(
                    f"O teto de {request.vagas} vagas é menor que o mínimo que esta "
                    f"combinação exige ({minimo_total} pessoas)"
                )

        self.repository.definir(
            combinacao,
            [
                {
                    "frente_id": f.frente_id,
                    "min_membros": f.min_membros,
                    "min_lideranca": f.min_lideranca,
                }
                for f in request.frentes
            ],
            vagas=request.vagas,
        )
        return {
            "combinacao": combinacao,
            "frentes": len(request.frentes),
            "vagas": request.vagas,
        }

    def _validar(self, f: "FrenteRegraRequest") -> None:
        if f.min_membros < 0 or f.min_lideranca < 0:
            raise RegraDeNegocioError("Os mínimos não podem ser negativos")
        # Uma banca sem ninguém não avalia nada. O zero é legítimo em UM dos
        # dois (uma frente pode entrar só com liderança, ou só com membros),
        # mas não nos dois.
        if f.min_membros == 0 and f.min_lideranca == 0:
            raise RegraDeNegocioError(
                "Cada frente precisa exigir ao menos uma pessoa, membro ou liderança"
            )

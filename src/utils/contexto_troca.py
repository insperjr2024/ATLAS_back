"""Contexto de uma troca aberta (2026-09-15, a pedido).

Quem pede troca larga uma vaga — mas nem toda vaga é igual. Se a saída dessa
pessoa quebra o piso ou a liderança mínima da FRENTE dela nesta banca, só
alguém da mesma frente (e, se for liderança que falta, só quem lidera a
frente) pode assumir o lugar — senão a troca "arruma" o número da banca e
destrói o motivo de terem posto aquela pessoa ali. Se a vaga era excedente
(a composição já fecha sem ela — o mesmo caso do líder que sobra em
`push_alocacao_automatica.py`), qualquer elegível serve, como sempre.

Usa a MESMA `ComposicaoBancaChecker` que a inscrição manual e a ficha da
banca — comparar o "com" e o "sem" essa pessoa é o único jeito de saber se a
saída dela É a causa do buraco, e não um buraco que já existia por outro
motivo.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from src.models.banca_model import BancaModel
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.composicao_banca import ComposicaoBancaChecker, LIDERANCA_DA_FRENTE_POSICOES


@dataclass
class ContextoTroca:
    frente_id: Optional[int] = None
    frente_nome: Optional[str] = None
    #: A saída de quem pediu a troca quebra o piso/liderança da frente dela.
    vaga_precisada: bool = False
    #: Dentre o que quebrou, é a LIDERANÇA da frente que fica faltando — só
    #: gerente/coordenador da frente cobre, não qualquer membro.
    precisa_lideranca: bool = False
    #: Quem pode de fato assumir esta vaga, dado o que ela exige.
    elegiveis_ids: List[int] = field(default_factory=list)


def calcular_contexto_troca(
    db: Session,
    banca: BancaModel,
    usuario_saindo_id: int,
    excluidos: Set[int],
) -> ContextoTroca:
    # Importado aqui, não no topo: mesmo motivo de `piso_banca.py` — evita o
    # ciclo `use_cases` -> `utils` -> `use_cases`.
    from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

    ativos = UsuarioRepository(db).get_ativos()
    ativos_por_id = {u.id: u for u in ativos}
    pool_generico = [
        uid for uid in ativos_por_id if uid not in excluidos and uid != usuario_saindo_id
    ]

    vinculos = BancaFrenteRepository(db).get_by_banca(banca.id)
    frente_ids_banca = [v.frente_id for v in vinculos]
    if not frente_ids_banca:
        return ContextoTroca(elegiveis_ids=pool_generico)

    minhas_frentes = {
        uf.frente_id for uf in UsuarioFrenteRepository(db).get_by_usuario(usuario_saindo_id)
    }
    frentes_relevantes = minhas_frentes & set(frente_ids_banca)
    if not frentes_relevantes:
        # A pessoa não é de nenhuma frente vinculada a esta banca (ex.:
        # liderança sem frente, ou entrou pelo preenchimento geral) — a saída
        # dela não pode "faltar" pra uma frente que ela nunca cobriu.
        return ContextoTroca(elegiveis_ids=pool_generico)

    regras = ResolverComposicaoUseCase(db).para(frente_ids_banca)
    candidatos_atuais = {c.usuario_id for c in CandidaturaRepository(db).get_by_banca(banca.id)}
    checker = ComposicaoBancaChecker(db)
    deficit_com = {
        d.frente_id: d for d in checker.verificar(banca, regras, candidatos_atuais).deficits
    }
    deficit_sem = {
        d.frente_id: d
        for d in checker.verificar(
            banca, regras, candidatos_atuais - {usuario_saindo_id}
        ).deficits
    }

    for frente_id in frentes_relevantes:
        antes = deficit_com.get(frente_id)
        depois = deficit_sem.get(frente_id)
        piso_antes = antes.piso_faltando if antes else 0
        piso_depois = depois.piso_faltando if depois else 0
        lid_antes = antes.lideranca_faltando if antes else 0
        lid_depois = depois.lideranca_faltando if depois else 0

        if piso_depois <= piso_antes and lid_depois <= lid_antes:
            # A saída dela não piora nada desta frente — era vaga excedente
            # (ex.: 2º líder além do mínimo). Segue pra próxima frente dela,
            # se tiver mais de uma.
            continue

        precisa_lideranca = lid_depois > lid_antes
        frente_nome = next((r.frente_nome for r in regras if r.frente_id == frente_id), None)
        membros_da_frente = {
            uf.usuario_id for uf in UsuarioFrenteRepository(db).get_by_frente(frente_id)
        }
        elegiveis = [
            uid
            for uid in membros_da_frente
            if uid in ativos_por_id
            and uid not in excluidos
            and uid != usuario_saindo_id
            and (
                not precisa_lideranca
                or ativos_por_id[uid].posicao in LIDERANCA_DA_FRENTE_POSICOES
            )
        ]
        return ContextoTroca(
            frente_id=frente_id,
            frente_nome=frente_nome,
            vaga_precisada=True,
            precisa_lideranca=precisa_lideranca,
            elegiveis_ids=elegiveis,
        )

    return ContextoTroca(elegiveis_ids=pool_generico)

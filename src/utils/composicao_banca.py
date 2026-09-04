"""Composição de banca (§8) — quanta gente de cada frente a banca exige.

Duas coisas mudaram em 2026-09-01, a pedido da diretoria:

1. **Os números vêm da COMBINAÇÃO de frentes**, não de `frente.piso_banca`.
   Business pode pedir 3 sozinho e 2 quando divide a banca com outras três.
   Quem resolve o que vale é `use_cases/configuracao/composicao_banca.py`;
   aqui só se conta gente contra a regra já resolvida.
2. **Liderança é vaga A MAIS.** O gerente que cobre a liderança de Business
   não conta entre os 3 membros de Business — a banca pede quatro pessoas.
   Antes ele cabia dentro do piso.

O que mudou em 2026-09-03, também a pedido da diretoria:

3. **Coordenador conta como liderança.** Antes era só gerente e diretoria; o
   coordenador caía entre os membros. Agora gerente E coordenador cobrem a
   liderança DA FRENTE deles.
4. **Não há mais TETO por frente.** O piso (membros e liderança) continua
   tendo de ser gente DAQUELA frente. Mas, para completar a banca acima do
   piso, tanto faz a frente — o único teto é o TOTAL da banca (`vagas` da
   combinação, em `calcular_vagas_banca`), conferido em `create_candidatura`.
   Sumiram daqui `max_membros`, `max_lideranca` e o `recusa_por_teto`.

O que mudou em 2026-09-04, de novo a pedido:

5. **Diretoria também é liderança SEM frente.** Até aqui a diretoria cobria o
   `min_lideranca` de QUALQUER frente, por "enxergar todas" (§3, 2026-09-03).
   Isso saiu: agora diretor_projetos, diretor_pessoas e diretor têm o MESMO
   tratamento do coordenador de vendas — mesma categoria, `LIDERANCA_SEM_FRENTE`.

E o que não mudou:

- **Liderança da frente é gerente ou coordenador DELA.** Consultor nunca é
  liderança.
- **Liderança SEM frente** — coordenador de vendas e toda a diretoria.
  Aparece na ficha entre as lideranças (`eh_lideranca` continua `True`), mas
  não cobre o `min_lideranca` de frente nenhuma nem entra no `min_membros` —
  some da contagem por frente como a equipe do projeto, e só conta no TOTAL
  da banca (`calcular_vagas_banca`). É a liderança que "pode ir, mas não
  fecha o piso de frente nenhuma".
- **A equipe do próprio projeto nunca conta**, nem como membro nem como
  liderança. Ela já não pode se candidatar à própria banca
  (`create_candidatura`); aqui é a mesma exclusão, e ela vale ANTES de
  qualquer contagem — quem está na equipe some da frente inteira.

⚠ **Este checker esteve SEM USO entre 2026-08-12 e 2026-09-02.** O piso por
frente e a liderança tinham sido removidos da porta de registro
(`marcar_banca_escopo._exigir_composicao`) porque barravam banca que já tinha
acontecido — o núcleo não garantia a composição exata e a banca ficava
impossível de registrar.

⭐ **Ele voltou pela porta da ALOCAÇÃO (2026-09-02), não pela do registro.**
Recusar na alocação é dizer "escolha outra banca", e a pessoa ainda tem o
semestre pela frente. No registro (depois), a banca já aconteceu e recusar
não desfaz nada — lá vale só o TOTAL (`_exigir_composicao`), com `forcar`
para a diretoria.

Os mínimos por frente não barram a alocação: são MOSTRADOS na aba Bancas e na
ficha (`contar`, servido em `GET /bancas` e `GET /bancas/{id}/detalhes`) para
quem escala saber o que falta antes de a banca acontecer.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from sqlalchemy.orm import Session

from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.middlewares.authorization import DIRETORIA

#: Gerente e coordenador cobrem a liderança DA FRENTE deles. A diretoria NÃO
#: entra aqui (2026-09-04): ela é liderança SEM frente, como o coordenador de
#: vendas — ver `LIDERANCA_SEM_FRENTE_POSICOES`.
LIDERANCA_DA_FRENTE_POSICOES = ("gerente", "coordenador")
LIDERANCA_POSICOES = (*LIDERANCA_DA_FRENTE_POSICOES, *DIRETORIA)
#: Quem é liderança mas não cobre o piso de frente nenhuma — só o coordenador
#: de vendas é identificado pela FLAG (`coordenador_vendas`, cruza com
#: qualquer posição); a diretoria é identificada pela POSIÇÃO.
LIDERANCA_SEM_FRENTE_POSICOES = DIRETORIA


def eh_lideranca(posicao: str) -> bool:
    """A categoria da pessoa para AGRUPAR a lista de avaliadores na ficha da
    banca (liderança x membro).

    ⚠ É mais grosso que a CONTAGEM (`ComposicaoBancaChecker.contar`): aqui um
    coordenador é sempre liderança; lá ele só cobre a cota da frente a que
    está vinculado. A ficha quer dizer "esta pessoa é gestão", a contagem quer
    saber se a cota daquela frente foi coberta — perguntas diferentes.
    """
    return posicao in LIDERANCA_POSICOES


@dataclass
class ContagemFrente:
    """Quanta gente de uma frente a banca TEM, ao lado do que ela exige.

    Existe porque duas perguntas diferentes se apoiam na mesma contagem: a
    checagem (`verificar`, que devolve o que está errado) e a aba Bancas, que
    precisa do número cru para dizer "1 de 3 membros" sem reimplementar a
    regra da liderança — foi reimplementá-la que este módulo veio evitar.
    """

    frente_id: int
    frente_nome: str
    min_membros: int
    min_lideranca: int
    #: Já com a cota de liderança descontada: o gerente que cobre a liderança
    #: não conta aqui (é vaga a mais), e a equipe do projeto nunca entra.
    membros: int = 0
    liderancas: int = 0


@dataclass
class DeficitFrente:
    frente_id: int
    frente_nome: str
    piso_faltando: int = 0
    lideranca_faltando: int = 0


@dataclass
class StatusComposicao:
    deficits: List[DeficitFrente] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.deficits

    @property
    def piso_ok(self) -> bool:
        return all(d.piso_faltando == 0 for d in self.deficits)

    @property
    def lideranca_ok(self) -> bool:
        return all(d.lideranca_faltando == 0 for d in self.deficits)


class ComposicaoBancaChecker:
    def __init__(self, db: Session):
        self.usuario_frente_repository = UsuarioFrenteRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)

    @classmethod
    def com_dados(
        cls,
        *,
        usuarios_por_id: Dict[int, object],
        membros_por_frente: Dict[int, Set[int]],
        equipe_do_projeto: Dict[int, Set[int]],
    ) -> "ComposicaoBancaChecker":
        """Um checker que já vem com tudo lido — não consulta banco nenhum.

        ⭐ Para o push automático, que carrega esses mesmos três conjuntos para
        montar a escalação e consulta o teto uma vez POR PESSOA da fila.
        Construí-lo com a sessão faria cada consulta reler a tabela de
        usuários e os vínculos de frente.

        ⚠ `equipe_do_projeto` é só a equipe + o coordenador (quem não avalia o
        próprio trabalho), indexada por banca. **Não** é o conjunto mais largo
        de quem o push não pode escalar: quem já está alocado CONTA na
        composição, e passá-lo aqui faria o gerente escalado deixar de cobrir
        a liderança da frente dele.
        """
        checker = cls.__new__(cls)
        checker._cache_usuarios = usuarios_por_id
        checker._cache_frentes = dict(membros_por_frente)
        checker._cache_excluidos = dict(equipe_do_projeto)
        return checker

    def contar(self, banca, regras, candidato_ids: Set[int]) -> List[ContagemFrente]:
        """Quanta gente de cada frente esta banca tem hoje, contra a regra.

        Separado de `verificar` para servir também a quem só quer MOSTRAR os
        números (a aba Bancas): a regra da liderança e a exclusão da equipe do
        projeto ficam em um lugar só.
        """
        excluidos = self._excluidos_do_projeto(banca)
        usuarios_por_id = self._usuarios_por_id()
        elegiveis = {uid for uid in candidato_ids if uid not in excluidos}
        # Liderança SEM frente (2026-09-04): coordenador de vendas e TODA a
        # diretoria — os três cargos, sem distinção. Pode ir à banca, mas não
        # cobre o `min_lideranca` de nenhuma frente nem entra no `min_membros`.
        # Sai da contagem por frente inteira — como a equipe do projeto —, e
        # só conta no TOTAL da banca. `getattr` porque os fakes dos testes de
        # `contar` nem sempre trazem `coordenador_vendas`.
        lideranca_sem_frente = {
            uid
            for uid in elegiveis
            if usuarios_por_id.get(uid)
            and (
                getattr(usuarios_por_id[uid], "coordenador_vendas", False)
                or usuarios_por_id[uid].posicao in LIDERANCA_SEM_FRENTE_POSICOES
            )
        }

        contagens: List[ContagemFrente] = []
        for regra in regras:
            da_frente = self._da_frente(regra.frente_id)
            # ⚠ A exclusão da equipe do projeto e da liderança sem frente vale
            # ANTES de contar: as duas somem da frente inteira, não só da
            # lista de membros.
            presentes = (elegiveis & da_frente) - lideranca_sem_frente
            # Gerente E coordenador da frente cobrem a liderança dela
            # (2026-09-03). Consultor nunca, e quem é liderança SEM frente já
            # saiu de `presentes` acima.
            lideres = {
                uid
                for uid in presentes
                if usuarios_por_id.get(uid)
                and usuarios_por_id[uid].posicao in LIDERANCA_DA_FRENTE_POSICOES
            }

            # ⭐ **Liderança é vaga A MAIS** (2026-09-01, a pedido). Quem ocupa
            # a cota de liderança sai da conta de membros: a banca de Business
            # pede 3 membros E 1 liderança, quatro pessoas.
            lideranca_usada = min(len(lideres), regra.min_lideranca)

            contagens.append(
                ContagemFrente(
                    frente_id=regra.frente_id,
                    frente_nome=regra.frente_nome,
                    min_membros=regra.min_membros,
                    min_lideranca=regra.min_lideranca,
                    membros=len(presentes) - lideranca_usada,
                    liderancas=len(lideres),
                )
            )
        return contagens

    def verificar(self, banca, regras, candidato_ids: Set[int]) -> StatusComposicao:
        """Confere o PISO da banca contra as `regras` da combinação de frentes.

        `regras` são `RegraDaFrente` de
        `use_cases/configuracao/composicao_banca.py` — quem resolve o que vale
        (configurado à mão ou padrão) é aquele use case; aqui só se conta.

        ⚠ Só o piso (membros e liderança FALTANDO por frente). Não há mais
        teto por frente (2026-09-03): completar acima do piso é "tanto faz a
        frente", e o único teto é o TOTAL da banca (`calcular_vagas_banca`),
        conferido em `create_candidatura`.
        """
        deficits: List[DeficitFrente] = []
        for c in self.contar(banca, regras, candidato_ids):
            deficit = DeficitFrente(
                frente_id=c.frente_id,
                frente_nome=c.frente_nome,
                piso_faltando=max(0, c.min_membros - c.membros),
                lideranca_faltando=max(0, c.min_lideranca - c.liderancas),
            )
            if deficit.piso_faltando or deficit.lideranca_faltando:
                deficits.append(deficit)

        return StatusComposicao(deficits=deficits)

    def _usuarios_por_id(self) -> Dict[int, object]:
        """A tabela inteira, uma vez por checker.

        `GET /bancas` monta a composição de TODAS as bancas do semestre com um
        checker só: sem este cache seria uma varredura de usuários por banca.
        Guardado em `getattr` porque os testes constroem o checker com
        `__new__` e repositórios falsos, sem passar pelo `__init__`.
        """
        cache = getattr(self, "_cache_usuarios", None)
        if cache is None:
            cache = {u.id: u for u in self.usuario_repository.get_all()}
            self._cache_usuarios = cache
        return cache

    def _da_frente(self, frente_id: int) -> Set[int]:
        cache = getattr(self, "_cache_frentes", None)
        if cache is None:
            cache = {}
            self._cache_frentes = cache
        if frente_id not in cache:
            cache[frente_id] = {
                v.usuario_id for v in self.usuario_frente_repository.get_by_frente(frente_id)
            }
        return cache[frente_id]

    def _excluidos_do_projeto(self, banca) -> Set[int]:
        # Cache pelo mesmo motivo dos outros dois: `GET /bancas` monta a
        # composição de todas as bancas do semestre com um checker só, e o
        # push chama `contar` uma vez por pessoa da fila. Sem ele, uma
        # consulta a `equipe_projeto` em cada passada.
        cache = getattr(self, "_cache_excluidos", None)
        if cache is None:
            cache = {}
            self._cache_excluidos = cache
        if banca.id not in cache:
            excluidos = {
                e.usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id)
            }
            if banca.coordenador_id:
                excluidos.add(banca.coordenador_id)
            cache[banca.id] = excluidos
        return cache[banca.id]

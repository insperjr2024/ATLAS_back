"""Composição de banca (§8) — quanta gente de cada frente a banca exige.

Duas coisas mudaram em 2026-09-01, a pedido da diretoria:

1. **Os números vêm da COMBINAÇÃO de frentes**, não de `frente.piso_banca`.
   Business pode pedir 3 sozinho e 2 quando divide a banca com outras três.
   Quem resolve o que vale é `use_cases/configuracao/composicao_banca.py`;
   aqui só se conta gente contra a regra já resolvida.
2. **Liderança é vaga A MAIS.** O gerente que cobre a liderança de Business
   não conta entre os 3 membros de Business — a banca pede quatro pessoas.
   Antes ele cabia dentro do piso.

E o que não mudou:

- **Liderança é gerente DAQUELA frente ou diretoria** (os três cargos, que
  cobrem qualquer frente por enxergarem todas — §3). Coordenador não é
  liderança aqui.
- **A equipe do próprio projeto nunca conta.** Ela já não pode se candidatar
  à própria banca (`create_candidatura`); aqui é a mesma exclusão, agora
  também para a contagem.

⚠ **Este checker esteve SEM USO entre 2026-08-12 e 2026-09-02.** O piso por
frente e a liderança tinham sido removidos da porta de registro
(`marcar_banca_escopo._exigir_composicao`) porque barravam banca que já tinha
acontecido — o núcleo não garantia a composição exata e a banca ficava
impossível de registrar.

⭐ **Ele voltou pela porta da ALOCAÇÃO (2026-09-02), não pela do registro.**
São momentos diferentes, e é a diferença que resolve o impasse acima:

- **Alocar** é antes: recusar aqui é dizer "escolha outra banca", e a pessoa
  ainda tem o semestre inteiro pela frente. É o que `create_candidatura` faz
  com os TETOS por frente — os números que a diretoria configura em
  Configurações e que, até aqui, não tinham efeito nenhum.
- **Registrar** é depois: a banca já aconteceu, e recusar não desfaz o que
  foi feito — só deixa a banca `atrasada` para sempre. Lá continua valendo só
  o TOTAL (`_exigir_composicao`), com `forcar` para a diretoria.

Os mínimos por frente também não barram nada: eles são MOSTRADOS na aba
Bancas (`contar`, servido em `GET /bancas`) para quem escala saber o que falta
antes de a banca acontecer.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.middlewares.authorization import DIRETORIA

#: ⚠ Constante sem uso hoje — mantida em dia com o resto do módulo para
#: não virar armadilha se alguém voltar a lê-la.
LIDERANCA_POSICOES = ("gerente", *DIRETORIA)


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
    max_membros: int
    min_lideranca: int
    max_lideranca: int
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
    #: Quantos passam do teto. Zero quando cabe.
    membros_sobrando: int = 0
    lideranca_sobrando: int = 0


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

    @property
    def teto_ok(self) -> bool:
        return all(
            d.membros_sobrando == 0 and d.lideranca_sobrando == 0 for d in self.deficits
        )


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
        # O diretor cobre a liderança de QUALQUER frente, por enxergar todas
        # (§3) — inclusive de uma a que ele não está vinculado. Os três cargos
        # de diretoria contam: o critério é enxergar tudo, e isso os três têm.
        diretores = {
            uid
            for uid in elegiveis
            if usuarios_por_id.get(uid) and usuarios_por_id[uid].posicao in DIRETORIA
        }

        contagens: List[ContagemFrente] = []
        for regra in regras:
            da_frente = self._da_frente(regra.frente_id)
            presentes = candidato_ids & da_frente
            gerentes = {
                uid
                for uid in presentes & elegiveis
                if usuarios_por_id.get(uid) and usuarios_por_id[uid].posicao == "gerente"
            }
            lideres = gerentes | diretores

            # ⭐ **Liderança é vaga A MAIS** (2026-09-01, a pedido). O gerente
            # que ocupa a cota de liderança sai da conta de membros: a banca de
            # Business pede 3 membros E 1 liderança, quatro pessoas. Antes ele
            # cabia dentro dos 3.
            #
            # Só sai da conta quem é DA FRENTE: o diretor cobre a liderança sem
            # estar vinculado a ela, e por isso nunca ocupava vaga de membro
            # dela para começar.
            lideranca_usada = min(len(lideres), regra.min_lideranca)
            gerentes_consumidos = min(len(gerentes), lideranca_usada)

            contagens.append(
                ContagemFrente(
                    frente_id=regra.frente_id,
                    frente_nome=regra.frente_nome,
                    min_membros=regra.min_membros,
                    max_membros=regra.max_membros,
                    min_lideranca=regra.min_lideranca,
                    max_lideranca=regra.max_lideranca,
                    membros=len(presentes) - gerentes_consumidos,
                    liderancas=len(lideres),
                )
            )
        return contagens

    def verificar(self, banca, regras, candidato_ids: Set[int]) -> StatusComposicao:
        """Confere a banca contra as `regras` da combinação de frentes dela.

        `regras` são `RegraDaFrente` de
        `use_cases/configuracao/composicao_banca.py` — quem resolve o que vale
        (configurado à mão ou padrão) é aquele use case; aqui só se conta.

        ⚠ **A assinatura mudou em 2026-09-01.** Antes recebia `frentes` e um
        `lideranca_minima_por_frente` global, e lia `frente.piso_banca`. Os
        números agora dependem da COMBINAÇÃO, e o checker não tem como
        resolvê-los sozinho.
        """
        deficits: List[DeficitFrente] = []
        for c in self.contar(banca, regras, candidato_ids):
            deficit = DeficitFrente(
                frente_id=c.frente_id,
                frente_nome=c.frente_nome,
                piso_faltando=max(0, c.min_membros - c.membros),
                lideranca_faltando=max(0, c.min_lideranca - c.liderancas),
                membros_sobrando=max(0, c.membros - c.max_membros),
                lideranca_sobrando=max(0, c.liderancas - c.max_lideranca),
            )
            if (
                deficit.piso_faltando
                or deficit.lideranca_faltando
                or deficit.membros_sobrando
                or deficit.lideranca_sobrando
            ):
                deficits.append(deficit)

        return StatusComposicao(deficits=deficits)

    def recusa_por_teto(
        self, banca, regras, candidato_ids: Set[int], novo_usuario_id: int
    ) -> Optional[str]:
        """A frase de recusa se alocar `novo_usuario_id` estourar algum teto —
        `None` quando cabe. É o que dá efeito aos "Máx." de Configurações.

        ⚠ **Só recusa o que ESTE alocado piora.** Uma banca já acima do teto
        (a diretoria apertou o número depois de a banca encher, ou alguém saiu
        de uma frente e entrou noutra) travaria toda alocação seguinte,
        inclusive a da frente que ainda está vazia — e o jeito de consertar
        seria justamente alocar mais gente.
        """
        antes = {c.frente_id: c for c in self.contar(banca, regras, candidato_ids)}
        depois = self.contar(banca, regras, candidato_ids | {novo_usuario_id})
        for c in depois:
            anterior = antes.get(c.frente_id)
            if not anterior:
                continue
            if c.membros > c.max_membros and c.membros > anterior.membros:
                return (
                    f"{c.frente_nome} já tem o máximo de {c.max_membros} "
                    "avaliadores nesta banca"
                )
            if c.liderancas > c.max_lideranca and c.liderancas > anterior.liderancas:
                return (
                    f"{c.frente_nome} já tem o máximo de {c.max_lideranca} "
                    "de liderança nesta banca"
                )
        return None

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
        # Cache pelo mesmo motivo dos outros dois: `recusa_por_teto` conta
        # duas vezes (antes e depois), e o push chama isso uma vez por pessoa
        # da fila. Sem ele, uma consulta a `equipe_projeto` em cada passada.
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

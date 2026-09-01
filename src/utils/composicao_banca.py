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

⚠ **Este checker esteve SEM USO entre 2026-08-12 e 2026-09-01.** O piso por
frente e a liderança tinham sido removidos da porta de registro
(`marcar_banca_escopo._exigir_composicao`) porque barravam banca que já tinha
acontecido — o núcleo não garantia a composição exata e a banca ficava
impossível de registrar. Voltaram com os TETOS e a matriz por combinação, que
é o que os torna afrouxáveis onde apertavam. A saída de emergência continua
sendo `forcar`, e só para a diretoria.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from sqlalchemy.orm import Session

from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.middlewares.authorization import DIRETORIA

#: ⚠ Constante sem uso hoje — mantida em dia com o resto do módulo para
#: não virar armadilha se alguém voltar a lê-la.
LIDERANCA_POSICOES = ("gerente", *DIRETORIA)


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
        excluidos = self._excluidos_do_projeto(banca)
        usuarios_por_id = {u.id: u for u in self.usuario_repository.get_all()}
        elegiveis = {uid for uid in candidato_ids if uid not in excluidos}
        # O diretor cobre a liderança de QUALQUER frente, por enxergar todas
        # (§3) — inclusive de uma a que ele não está vinculado. Os três cargos
        # de diretoria contam: o critério é enxergar tudo, e isso os três têm.
        diretores = {
            uid
            for uid in elegiveis
            if usuarios_por_id.get(uid) and usuarios_por_id[uid].posicao in DIRETORIA
        }

        deficits: List[DeficitFrente] = []
        for regra in regras:
            da_frente = {
                v.usuario_id
                for v in self.usuario_frente_repository.get_by_frente(regra.frente_id)
            }
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
            membros = len(presentes) - gerentes_consumidos

            deficit = DeficitFrente(
                frente_id=regra.frente_id,
                frente_nome=regra.frente_nome,
                piso_faltando=max(0, regra.min_membros - membros),
                lideranca_faltando=max(0, regra.min_lideranca - len(lideres)),
                membros_sobrando=max(0, membros - regra.max_membros),
                lideranca_sobrando=max(0, len(lideres) - regra.max_lideranca),
            )
            if (
                deficit.piso_faltando
                or deficit.lideranca_faltando
                or deficit.membros_sobrando
                or deficit.lideranca_sobrando
            ):
                deficits.append(deficit)

        return StatusComposicao(deficits=deficits)

    def _excluidos_do_projeto(self, banca) -> Set[int]:
        excluidos = {e.usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id)}
        if banca.coordenador_id:
            excluidos.add(banca.coordenador_id)
        return excluidos

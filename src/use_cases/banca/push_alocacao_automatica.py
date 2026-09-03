"""Alocação automática de bancas por rodízio (§8).

Uma semana antes da banca, se ainda não bateu o piso mínimo de gente, o
sistema escala consultores automaticamente — primeiro da mesma frente,
depois de qualquer frente se precisar — dando prioridade a quem foi alocado
há mais tempo (rodízio justo: quem acabou de ir para o final da fila).

Roda pelo agendador (`src/app.py`: de 5 em 5 minutos, e também na subida do
app) e sob demanda (`POST /bancas/push-alocacao`, diretoria).

A varredura é idempotente de propósito — é o que permite rodar com essa
frequência sem medo: ela preenche até o piso e para, quem já está inscrito
entra em `_excluidos`, e a notificação carrega chave de deduplicação.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from src.models.banca_model import BancaModel
from src.models.usuario_model import UsuarioModel
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.grade_horaria_repository import GradeHorariaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.equipe_banca import membros_da_banca
from src.utils.fuso import para_hora_local
from src.utils.notificar import notificar
from src.utils.composicao_banca import LIDERANCA_DA_FRENTE_POSICOES
from src.utils.piso_banca import calcular_piso_banca
from src.middlewares.authorization import DIRETORIA

JANELA_PUSH_DIAS = 7


class PushAlocacaoAutomaticaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.banca_repository = BancaRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.usuario_frente_repository = UsuarioFrenteRepository(db)
        self.grade_horaria_repository = GradeHorariaRepository(db)
        self.semestre_repository = SemestreRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self) -> List[dict]:
        agora = datetime.now()
        bancas = self.banca_repository.get_por_periodo(agora, agora + timedelta(days=JANELA_PUSH_DIAS))

        # Passada ociosa termina aqui. Sem banca na janela não há teto a ler
        # nem rodízio a montar, e a varredura de 5 em 5 minutos passa a custar
        # uma query só — fora de semestre, é a esmagadora maioria delas.
        if not bancas:
            return []

        configuracao = self.configuracao_repository.get()
        teto = configuracao.vagas_por_banca if configuracao else 5

        ultima_alocacao = self._ultima_alocacao_por_usuario()

        resumo = []
        for banca in bancas:
            resultado = self._processar_banca(banca, teto, ultima_alocacao)
            if resultado:
                resumo.append(resultado)
        return resumo

    def _ultima_alocacao_por_usuario(self) -> Dict[int, datetime]:
        return self.candidatura_repository.ultima_alocacao_por_usuario()

    def _processar_banca(
        self, banca: BancaModel, teto: int, ultima_alocacao: Dict[int, datetime]
    ) -> Optional[dict]:
        vinculos_frente = self.banca_frente_repository.get_by_banca(banca.id)
        frentes = [f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos_frente) if f]
        if not frentes and banca.piso_minimo_override is None:
            return None

        piso_total = calcular_piso_banca(banca, frentes, self.db)
        if piso_total <= 0:
            return None

        # ⭐ A régua de cada frente vem da MATRIZ por combinação (2026-09-01),
        # a mesma que `calcular_piso_banca` somou acima. Ler
        # `configuracao.lideranca_minima_por_frente` e `frente.piso_banca`
        # direto aqui, como era, fazia o push preencher por uma régua e o
        # registro cobrar por outra — a banca fechava no push e era recusada
        # no registro, ou o contrário.
        from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

        resolver = ResolverComposicaoUseCase(self.db)
        regra_por_frente = {r.frente_id: r for r in resolver.para([f.id for f in frentes])}

        # ⭐ E o TETO também pode ser da combinação (2026-09-02). `teto` é o
        # global, lido uma vez para a passada inteira; a combinação que tem
        # número próprio manda nele.
        propria = resolver.vagas_proprias_da_combinacao([f.id for f in frentes])
        if propria is not None:
            teto = propria

        candidaturas_atuais = self.candidatura_repository.get_by_banca(banca.id)
        alocados_antes = len(candidaturas_atuais)
        vaga_disponivel = teto - alocados_antes
        if vaga_disponivel <= 0:
            return None

        excluidos = self._excluidos(banca, candidaturas_atuais)
        ja_presentes = {c.usuario_id for c in candidaturas_atuais}

        ativos = self.usuario_repository.get_ativos()
        usuarios_por_id = {u.id: u for u in ativos}
        membros_por_frente = {
            f.id: {v.usuario_id for v in self.usuario_frente_repository.get_by_frente(f.id)}
            for f in frentes
        }

        selecionados: List[UsuarioModel] = []

        def contabilizados() -> Set[int]:
            return ja_presentes | {u.id for u in selecionados}

        def vagas_restantes() -> int:
            return vaga_disponivel - len(selecionados)

        # §8: piso e liderança são POR FRENTE — cada frente vinculada puxa
        # gente DELA MESMA primeiro, liderança antes do resto do piso (um
        # gerente/coordenador presente também conta como membro da frente,
        # então puxá-lo primeiro nunca desperdiça vaga). Só o que sobrar —
        # frente sem gente suficiente pra cobrir o próprio piso, ou vaga extra
        # até o total — é que pode vir de qualquer frente, no bloco depois.
        for frente in frentes:
            if vagas_restantes() <= 0:
                break
            membros_ids = membros_por_frente[frente.id]

            lideres_presentes = {
                uid
                for uid in contabilizados()
                if uid not in excluidos
                and usuarios_por_id.get(uid)
                and (
                    (
                        uid in membros_ids
                        and usuarios_por_id[uid].posicao in LIDERANCA_DA_FRENTE_POSICOES
                    )
                    or usuarios_por_id[uid].posicao in DIRETORIA
                )
            }
            regra = regra_por_frente.get(frente.id)
            lideranca_minima = regra.min_lideranca if regra else 1
            falta_lideranca = max(0, lideranca_minima - len(lideres_presentes))
            if falta_lideranca > 0:
                # Puxa GERENTE ou COORDENADOR da frente automaticamente —
                # diretor conta pra liderança se já estiver lá por conta
                # própria, mas o push não escala diretoria pra rotina de banca.
                pool_lideres = [
                    u
                    for u in ativos
                    if u.id in membros_ids
                    and u.id not in excluidos
                    and u.id not in contabilizados()
                    and u.posicao in LIDERANCA_DA_FRENTE_POSICOES
                ]
                fila_lideres = self._ordenar_por_rodizio(pool_lideres, ultima_alocacao)
                selecionados.extend(fila_lideres[: min(falta_lideranca, vagas_restantes())])

            if vagas_restantes() <= 0:
                continue
            # ⚠ A liderança já puxada acima NÃO abate o piso: ela é vaga a
            # mais desde 2026-09-01, e descontá-la aqui devolveria o
            # comportamento antigo por uma porta lateral.
            min_membros = regra.min_membros if regra else frente.piso_banca
            ja_da_frente = len(contabilizados() & membros_ids)
            lideres_da_frente = len(lideres_presentes & membros_ids)
            falta_piso = max(0, min_membros - max(0, ja_da_frente - lideres_da_frente))
            if falta_piso > 0:
                pool_frente = [
                    u
                    for u in ativos
                    if u.id in membros_ids and u.id not in excluidos and u.id not in contabilizados()
                ]
                fila_frente = self._ordenar_por_rodizio(pool_frente, ultima_alocacao)
                selecionados.extend(fila_frente[: min(falta_piso, vagas_restantes())])

        # O que sobrar — frente que não tinha gente suficiente pro próprio
        # piso — qualquer frente cobre, senão a banca fica presa sem nunca
        # bater o mínimo total.
        deficit_restante = min(max(0, piso_total - len(contabilizados())), vagas_restantes())
        if deficit_restante > 0:
            # ⚠ **Diretoria fica de fora daqui também** (2026-09-01). A regra
            # já valia para a cota de liderança logo acima — "o push não escala
            # diretoria pra rotina de banca" — mas este preenchimento final
            # ignorava a posição e alcançava um diretor sempre que o piso não
            # fechasse. Só não aparecia porque o piso era pequeno; com a
            # liderança virando vaga a mais, o caso passou a ser rotina.
            pool_geral = [
                u
                for u in ativos
                if u.id not in excluidos
                and u.id not in contabilizados()
                and u.posicao not in DIRETORIA
            ]
            fila_geral = self._ordenar_por_rodizio(pool_geral, ultima_alocacao)
            # Este bloco enche a banca ACIMA do piso — daqui em diante tanto
            # faz a frente (2026-09-03: o teto por frente saiu). O único limite
            # é `vaga_disponivel`, o total da banca, já respeitado no `break`.
            for usuario in fila_geral:
                if len(selecionados) >= vaga_disponivel or deficit_restante <= 0:
                    break
                selecionados.append(usuario)
                deficit_restante -= 1

        if not selecionados:
            return None

        agora = datetime.now()
        data_formatada = banca.data_hora.strftime("%d/%m/%Y às %H:%M") if banca.data_hora else ""
        for usuario in selecionados:
            self.candidatura_repository.create(
                banca_id=banca.id, usuario_id=usuario.id, criado_em=agora, confirmado=False
            )
            notificar(
                self.db,
                usuario.id,
                f"Você foi alocado(a) para a banca de {banca.nome_projeto} em {data_formatada}. "
                "Se não puder comparecer, peça uma troca em Bancas.",
                banca_id=banca.id,
                tipo="escalacao_banca",
                # Com chave: o push roda repetidamente até a banca encher, e sem
                # ela a mesma escalação viraria uma linha por passada.
                chave=f"escalacao_banca:banca={banca.id}:usuario={usuario.id}",
            )

        return {
            "banca_id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "alocados_antes": alocados_antes,
            "alocados_depois": alocados_antes + len(selecionados),
            "usuarios_alocados": [u.id for u in selecionados],
        }

    def _equipe_do_projeto(self, banca: BancaModel) -> Set[int]:
        """A equipe do projeto desta banca, mais o coordenador.

        Só esta parte de `_excluidos` interessa à checagem de composição: lá o
        conjunto é mais largo (já alocados, aula no horário), e quem já está
        alocado precisa CONTAR na composição — senão o gerente escalado
        deixaria de cobrir a liderança da frente dele na hora de conferir o
        teto.
        """
        equipe = set(
            membros_da_banca(
                banca,
                self.banca_escopo_repository,
                self.escopo_repository,
                self.membro_repository,
                self.equipe_projeto_repository,
            )
        )
        if banca.coordenador_id:
            equipe.add(banca.coordenador_id)
        return equipe

    def _excluidos(self, banca: BancaModel, candidaturas_atuais: list) -> Set[int]:
        """Quem o push não pode escalar nesta banca.

        ⭐ É o ÚNICO portão: tanto o laço por frente quanto o fallback geral em
        `_processar_banca` filtram por este conjunto, então somar alguém aqui
        o tira de todos os caminhos de uma vez.

        ⚠ A equipe do projeto vem de `membros_da_banca`, não da legada
        `equipe_projeto` sozinha. Só o coordenador estava protegido de verdade
        (é coluna da banca); os CONSULTORES do projeto ficavam elegíveis, e o
        rodízio podia escalá-los para avaliar o próprio trabalho — o mesmo
        buraco que a inscrição manual já tinha fechado.
        """
        excluidos = {c.usuario_id for c in candidaturas_atuais}
        excluidos.update(self._equipe_do_projeto(banca))
        excluidos.update(self._com_aula_no_horario(banca))
        return excluidos

    def _com_aula_no_horario(self, banca: BancaModel) -> Set[int]:
        """Quem tem aula na hora da banca (§8 e §11).

        📐 A trava vale só para o push. Quem quiser se inscrever por vontade
        própria mesmo tendo aula continua podendo — o §8 é explícito nisso, e
        `create_candidatura` não checa grade nenhuma.

        📐 Quem não preencheu a grade não é barrado: ausência de linha quer
        dizer "não sei", não "está livre". Barrar por falta de dado esvaziaria
        o rodízio no primeiro semestre, antes de alguém preencher.

        ⚠ Compara pelo INÍCIO da banca. A banca não guarda duração, então uma
        que comece 13:00 e avance sobre a aula das 14:15 não é detectada. Para
        pegar isso seria preciso gravar quanto dura cada banca.

        ⚠ **Em hora LOCAL, não no valor cru.** `banca.data_hora` é gravado em
        UTC (o front manda `toISOString()`); a grade é preenchida em horário de
        aula. Comparar os dois direto errava por 3 horas e invertia a regra —
        quem tinha aula na hora da banca era escalado e quem estava livre era
        barrado. O `weekday()` sofria do mesmo: banca da noite vira o dia
        seguinte em UTC.
        """
        if not banca.data_hora:
            return set()

        quando = para_hora_local(banca.data_hora)

        # `weekday()` já é 0=segunda … 6=domingo, a mesma convenção da grade.
        dia_semana = quando.weekday()
        if dia_semana > 4:
            return set()

        semestre = self.semestre_repository.get_por_data(quando.date())
        if not semestre:
            return set()

        hora = quando.time()
        return {
            faixa.usuario_id
            for faixa in self.grade_horaria_repository.get_por_semestre(semestre.id)
            if faixa.dia_semana == dia_semana
            and faixa.hora_inicio <= hora < faixa.hora_fim
        }

    def _ordenar_por_rodizio(
        self, usuarios: List[UsuarioModel], ultima_alocacao: Dict[int, datetime]
    ) -> List[UsuarioModel]:
        # Quem nunca foi alocado (sem entrada no dict) entra primeiro; entre
        # os já alocados, quem foi há mais tempo vem antes de quem foi há
        # pouco — rodízio justo (§8).
        return sorted(usuarios, key=lambda u: ultima_alocacao.get(u.id, datetime.min))

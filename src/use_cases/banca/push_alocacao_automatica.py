"""Alocação automática de bancas por rodízio (§8).

Uma semana antes da banca, se ainda não bateu o piso mínimo de gente, o
sistema escala consultores automaticamente — primeiro da mesma frente,
depois de qualquer frente se precisar — dando prioridade a quem tem MENOS
bancas futuras no momento (rodízio justo: quem está mais livre entra
primeiro; empate é sorteado).

Roda pelo agendador (`src/app.py`: de 5 em 5 minutos, e também na subida do
app) e sob demanda (`POST /bancas/push-alocacao`, diretoria).

⭐ **UMA VEZ só por banca, não a cada passada (2026-09-16, a pedido).** Assim
que a banca entra na janela de 7 dias, a primeira passada que a encontra
avalia o piso, preenche o que faltar e marca `push_executado_em` — tenha
escalado alguém ou não. `get_por_periodo` exclui banca já marcada, então
nenhuma passada seguinte volta a mexer nela.

⚠ Isto é diferente de idempotência: o rodízio já era idempotente (rodar duas
vezes com o mesmo estado não duplicava nada), mas rodava a cada passada
enquanto a banca estivesse na janela — e se a diretoria tirasse depois
alguém necessário pro piso, a passada seguinte reagia sozinha, escalando
outra pessoa sem ninguém ter pedido. Agora não: passado o UM push, cobrir um
buraco que a diretoria abriu é decisão manual dela, de propósito — ela tem
as ferramentas para isso (adicionar/remover candidatura de banca já
realizada inclusive, ver `create_candidatura`/`update_candidatura`).
"""

import random
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
from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.equipe_banca import membros_da_banca
from src.utils.fuso import para_hora_local
from src.utils.notificar import notificar
from src.utils.composicao_banca import (
    LIDERANCA_DA_FRENTE_POSICOES,
    eh_lideranca_sem_frente,
)
from src.middlewares.authorization import DIRETORIA
from src.utils.piso_banca import calcular_piso_banca

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
        self.posicao_permissao_repository = PosicaoPermissaoRepository(db)

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

        # ⚠ Ranking por CARGA TOTAL (já realizada + futura), não por recência
        # (2026-09-15). O critério antigo (`ultima_alocacao_por_usuario`) só
        # olhava há quanto tempo a pessoa tinha sido alocada pela ÚLTIMA vez —
        # alguém com várias bancas de inscrição MANUAL, mas nunca escalado
        # pelo push, entrava primeiro na fila mesmo já carregado. E contar só
        # a agenda FUTURA também falhava: quem já tinha acabado de realizar
        # uma banca parecia "livre" de novo, quando já tinha carregado a
        # parte dele. Mutável de propósito: quem é escalado numa banca desta
        # MESMA passada já entra mais carregado pro ranking da banca seguinte.
        contagem_bancas = self.candidatura_repository.contagem_bancas_por_usuario()

        resumo = []
        for banca in bancas:
            resultado = self._processar_banca(banca, teto, contagem_bancas)
            # ⭐ Marca JÁ, resultado tendo escalado alguém ou não — é isto que
            # torna esta a ÚNICA passada que mexe nesta banca (o filtro mora
            # em `get_por_periodo`). Escalou 0 porque o piso já estava
            # coberto? Também marca: não é "tentei e não achei ninguém",
            # é "avaliei esta banca, ponto final".
            self.banca_repository.update(banca.id, push_executado_em=agora)
            if resultado:
                resumo.append(resultado)
        return resumo

    def _processar_banca(
        self, banca: BancaModel, teto: int, contagem_bancas: Dict[int, int]
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

        # ⚠ **CONTAR ≠ PODER ESCALAR.** `excluidos` é largo (equipe do projeto
        # + já alocados + com aula) e serve pra escolher QUEM puxar. Mas a
        # contagem de composição não pode tirar quem já está alocado — senão a
        # liderança que o push escalou às 21:45 fica invisível na passada das
        # 21:50 e ele escala OUTRA. Para contar, o único conjunto que sai é a
        # equipe do próprio projeto (quem não avalia o próprio trabalho).
        equipe_do_projeto = self._equipe_do_projeto(banca)

        ativos = self.usuario_repository.get_ativos()
        usuarios_por_id = {u.id: u for u in ativos}
        # ⚠ Liderança SEM frente — coordenador de vendas + toda a diretoria.
        # Pode ir à banca (conta no total), mas NÃO cobre `min_lideranca` nem
        # `min_membros` de frente nenhuma, e o push não a escala pra rotina.
        # `ComposicaoBancaChecker.contar` (a ficha e a trava de inscrição) já
        # usava esta regra; o push não — foi por isso que a banca do ATLAS I
        # fechou "lotada" com a liderança de Business ainda faltando.
        #
        # ⭐ 2026-09-16: "coordenador de vendas" virou permissão por cargo
        # (`pode_coordenar_vendas`), não mais o booleano solto `usuario.
        # coordenador_vendas` — `posicoes_coordenam_vendas` é o conjunto de
        # slugs de `posicao` com essa caixa ligada.
        posicoes_coordenam_vendas = self.posicao_permissao_repository.get_posicoes_com_permissao(
            "pode_coordenar_vendas"
        )
        sem_frente = {
            u.id for u in ativos if eh_lideranca_sem_frente(u, posicoes_coordenam_vendas)
        }
        membros_por_frente = {
            f.id: {v.usuario_id for v in self.usuario_frente_repository.get_by_frente(f.id)}
            for f in frentes
        }

        selecionados: List[UsuarioModel] = []

        def contabilizados() -> Set[int]:
            return ja_presentes | {u.id for u in selecionados}

        def vagas_restantes() -> int:
            return vaga_disponivel - len(selecionados)

        # ⭐ Quanto de liderança faltou por FALTA DE POOL — nenhum
        # gerente/coordenador daquela frente disponível pra puxar (2026-09-04,
        # a pedido). Essas vagas ficam RESERVADAS lá embaixo: o preenchimento
        # geral não pode gastá-las com quem não é líder da frente, senão a
        # banca bate o piso TOTAL com a liderança ainda de fato faltando —
        # espelha a reserva de `create_candidatura` pro mesmo caso.
        lideranca_nao_coberta = 0

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

            # ⚠ Diretoria e coordenador de vendas NÃO cobrem aqui: são
            # liderança SEM frente (`sem_frente`) — espelha
            # `ComposicaoBancaChecker.contar`. E o corte é por
            # `equipe_do_projeto`, NÃO por `excluidos`: quem já está alocado
            # (inclusive uma liderança que ESTE push escalou numa passada
            # anterior) tem de continuar contando, senão a passada seguinte
            # acha que a liderança falta de novo e escala outra.
            lideres_presentes = {
                uid
                for uid in contabilizados()
                if uid not in equipe_do_projeto
                and uid not in sem_frente
                and usuarios_por_id.get(uid)
                and uid in membros_ids
                and usuarios_por_id[uid].posicao in LIDERANCA_DA_FRENTE_POSICOES
            }
            regra = regra_por_frente.get(frente.id)
            lideranca_minima = regra.min_lideranca if regra else 1
            falta_lideranca = max(0, lideranca_minima - len(lideres_presentes))
            if falta_lideranca > 0:
                # Puxa GERENTE ou COORDENADOR da frente automaticamente — o
                # push não escala diretoria nem coordenador de vendas
                # (`sem_frente`) pra rotina de banca: nenhum dos dois cobre a
                # cota de liderança da frente.
                pool_lideres = [
                    u
                    for u in ativos
                    if u.id in membros_ids
                    and u.id not in excluidos
                    and u.id not in contabilizados()
                    and u.id not in sem_frente
                    and u.posicao in LIDERANCA_DA_FRENTE_POSICOES
                ]
                fila_lideres = self._ordenar_por_rodizio(pool_lideres, contagem_bancas)
                escalados_lideranca = fila_lideres[: min(falta_lideranca, vagas_restantes())]
                selecionados.extend(escalados_lideranca)
                # Sorteia SÓ entre quem cobre a cota (`pool_lideres`, acima).
                # O que sobrar sem pool pra puxar fica reservado, não vai pro
                # preenchimento geral do fim da função.
                lideranca_nao_coberta += falta_lideranca - len(escalados_lideranca)

            if vagas_restantes() <= 0:
                continue
            # ⚠ A liderança MÍNIMA exigida não abate o piso — ela é vaga a
            # mais desde 2026-09-01, e descontar todo mundo que lidera aqui
            # devolveria o comportamento antigo por uma porta lateral. Mas
            # liderança EXCEDENTE (além do `min_lideranca`) volta a contar
            # como membro comum, até o tanto que ainda falta de piso
            # (2026-09-07 em `ComposicaoBancaChecker.contar` — o push nunca
            # tinha ganhado essa parte, e ficou puxando gente que a banca não
            # precisava: 2 líderes presentes com `min_lideranca=1` descontava
            # os DOIS do piso, quando só o primeiro é vaga extra de verdade).
            min_membros = regra.min_membros if regra else frente.piso_banca
            # `sem_frente` sai da conta de membros também: um coordenador de
            # vendas ligado à frente não fecha o `min_membros` dela (espelha
            # `ComposicaoBancaChecker.contar`).
            ja_da_frente = len((contabilizados() & membros_ids) - sem_frente)
            lideres_da_frente = len(lideres_presentes & membros_ids)
            nao_lideres_da_frente = ja_da_frente - lideres_da_frente
            lideres_excedentes = max(0, lideres_da_frente - lideranca_minima)
            buraco_de_membro = max(0, min_membros - nao_lideres_da_frente)
            membros_contados = nao_lideres_da_frente + min(lideres_excedentes, buraco_de_membro)
            falta_piso = max(0, min_membros - membros_contados)
            if falta_piso > 0:
                pool_frente = [
                    u
                    for u in ativos
                    if u.id in membros_ids
                    and u.id not in excluidos
                    and u.id not in contabilizados()
                    and u.id not in sem_frente
                ]
                fila_frente = self._ordenar_por_rodizio(pool_frente, contagem_bancas)
                selecionados.extend(fila_frente[: min(falta_piso, vagas_restantes())])

        # O que sobrar — frente que não tinha gente suficiente pro próprio
        # piso — qualquer frente cobre, senão a banca fica presa sem nunca
        # bater o mínimo total.
        deficit_restante = min(max(0, piso_total - len(contabilizados())), vagas_restantes())
        # ⚠ Menos o que é liderança sem pool pra cobrir: essas vagas ficam
        # vazias de propósito (ver `lideranca_nao_coberta` acima) — vão pra
        # quem se alocar sozinho depois cobrindo a cota, não pro primeiro
        # nome da fila geral.
        deficit_restante = max(0, deficit_restante - lideranca_nao_coberta)
        if deficit_restante > 0:
            # ⚠ **Só a diretoria fica de fora daqui** — "o push não escala
            # diretoria pra rotina de banca". O coordenador de vendas PODE
            # entrar: cumpridos os pisos por frente, o resto da banca é
            # "qualquer cargo, qualquer frente" (é o que
            # `ComposicaoBancaChecker` também faz — vendas não fecha piso de
            # frente, mas conta no TOTAL). O que ele NÃO pode é cobrir a cota
            # de liderança/piso de uma frente, e isso já é barrado lá em cima
            # (`sem_frente` em `pool_lideres`/`pool_frente`).
            pool_geral = [
                u
                for u in ativos
                if u.id not in excluidos
                and u.id not in contabilizados()
                and u.posicao not in DIRETORIA
            ]
            fila_geral = self._ordenar_por_rodizio(pool_geral, contagem_bancas)
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

        # Conta pra próxima banca desta mesma passada — senão a mesma pessoa
        # pode ser escalada em duas bancas seguidas achando, em ambas, que
        # está "menos carregada" que o resto.
        for usuario in selecionados:
            contagem_bancas[usuario.id] = contagem_bancas.get(usuario.id, 0) + 1

        agora = datetime.now()
        # ⚠ Horário LOCAL: `banca.data_hora` é UTC. Sem converter, o e-mail
        # da escalação dizia "às 15:00" para uma banca de meio-dia.
        data_formatada = (
            para_hora_local(banca.data_hora).strftime("%d/%m/%Y às %H:%M")
            if banca.data_hora
            else ""
        )
        for usuario in selecionados:
            self.candidatura_repository.create(
                banca_id=banca.id, usuario_id=usuario.id, criado_em=agora, confirmado=False
            )
            notificar(
                self.db,
                usuario.id,
                # ⚠ Diz que foi AUTOMÁTICO (2026-09-07, a pedido): quem não se
                # inscreveu precisa entender por que apareceu numa banca — sem
                # isso, "você foi alocado(a)" parece coisa que ele fez.
                f"Você foi escalado(a) automaticamente, por rodízio, para a banca de "
                f"{banca.nome_projeto} em {data_formatada} — não precisou se inscrever. "
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
        self, usuarios: List[UsuarioModel], contagem_bancas: Dict[int, int]
    ) -> List[UsuarioModel]:
        # Quem tem MENOS bancas futuras entra primeiro — rodízio justo (§8).
        # Empate é sorteio: embaralha antes de ordenar, e como `sorted` é
        # estável, a ordem embaralhada sobrevive entre quem tem a mesma
        # contagem.
        embaralhados = list(usuarios)
        random.shuffle(embaralhados)
        return sorted(embaralhados, key=lambda u: contagem_bancas.get(u.id, 0))

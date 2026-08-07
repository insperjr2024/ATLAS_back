"""Alocação automática de bancas por rodízio (§8).

Uma semana antes da banca, se ainda não bateu o piso mínimo de gente, o
sistema escala consultores automaticamente — primeiro da mesma frente,
depois de qualquer frente se precisar — dando prioridade a quem foi alocado
há mais tempo (rodízio justo: quem acabou de ir para o final da fila).

Roda tanto pelo agendador (`src/app.py`, uma vez por dia) quanto sob demanda
(`POST /bancas/push-alocacao`, diretoria).
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from src.models.banca_model import BancaModel
from src.models.usuario_model import UsuarioModel
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.notificar import notificar
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
        self.frente_repository = FrenteRepository(db)
        self.usuario_frente_repository = UsuarioFrenteRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self) -> List[dict]:
        agora = datetime.now()
        bancas = self.banca_repository.get_por_periodo(agora, agora + timedelta(days=JANELA_PUSH_DIAS))

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
        ultima: Dict[int, datetime] = {}
        for candidatura in self.candidatura_repository.get_all():
            atual = ultima.get(candidatura.usuario_id)
            if atual is None or candidatura.criado_em > atual:
                ultima[candidatura.usuario_id] = candidatura.criado_em
        return ultima

    def _processar_banca(
        self, banca: BancaModel, teto: int, ultima_alocacao: Dict[int, datetime]
    ) -> Optional[dict]:
        vinculos_frente = self.banca_frente_repository.get_by_banca(banca.id)
        frentes = [f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos_frente) if f]
        if not frentes and banca.piso_minimo_override is None:
            return None

        piso_total = calcular_piso_banca(banca, frentes)
        if piso_total <= 0:
            return None

        candidaturas_atuais = self.candidatura_repository.get_by_banca(banca.id)
        alocados_antes = len(candidaturas_atuais)
        vaga_disponivel = teto - alocados_antes
        if vaga_disponivel <= 0:
            return None

        excluidos = self._excluidos(banca, candidaturas_atuais)
        ja_presentes = {c.usuario_id for c in candidaturas_atuais}

        configuracao = self.configuracao_repository.get()
        lideranca_minima = configuracao.lideranca_minima_por_frente if configuracao else 1

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
        # gerente presente também conta como membro da frente, então puxá-lo
        # primeiro nunca desperdiça vaga). Só o que sobrar — frente sem gente
        # suficiente pra cobrir o próprio piso, ou vaga extra até o teto — é
        # que pode vir de qualquer frente, no bloco depois deste laço.
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
                    (uid in membros_ids and usuarios_por_id[uid].posicao == "gerente")
                    or usuarios_por_id[uid].posicao == "diretor"
                )
            }
            falta_lideranca = max(0, lideranca_minima - len(lideres_presentes))
            if falta_lideranca > 0:
                # Só puxa GERENTE automaticamente — diretor conta pra
                # liderança se já estiver lá por conta própria, mas o push
                # não escala diretoria pra rotina de banca.
                pool_lideres = [
                    u
                    for u in ativos
                    if u.id in membros_ids
                    and u.id not in excluidos
                    and u.id not in contabilizados()
                    and u.posicao == "gerente"
                ]
                fila_lideres = self._ordenar_por_rodizio(pool_lideres, ultima_alocacao)
                selecionados.extend(fila_lideres[: min(falta_lideranca, vagas_restantes())])

            if vagas_restantes() <= 0:
                continue
            falta_piso = max(0, frente.piso_banca - len(contabilizados() & membros_ids))
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
            pool_geral = [u for u in ativos if u.id not in excluidos and u.id not in contabilizados()]
            fila_geral = self._ordenar_por_rodizio(pool_geral, ultima_alocacao)
            selecionados.extend(fila_geral[:deficit_restante])

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

    def _excluidos(self, banca: BancaModel, candidaturas_atuais: list) -> Set[int]:
        """Quem já é candidato, e a equipe do próprio projeto (que não pode
        se candidatar à própria banca — mesma regra de `create_candidatura`)."""
        excluidos = {c.usuario_id for c in candidaturas_atuais}
        excluidos.add(banca.coordenador_id)
        excluidos.update(e.usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id))
        return excluidos

    def _ordenar_por_rodizio(
        self, usuarios: List[UsuarioModel], ultima_alocacao: Dict[int, datetime]
    ) -> List[UsuarioModel]:
        # Quem nunca foi alocado (sem entrada no dict) entra primeiro; entre
        # os já alocados, quem foi há mais tempo vem antes de quem foi há
        # pouco — rodízio justo (§8).
        return sorted(usuarios, key=lambda u: ultima_alocacao.get(u.id, datetime.min))

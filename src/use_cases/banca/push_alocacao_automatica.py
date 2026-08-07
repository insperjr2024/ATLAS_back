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
from src.repositories.grade_horaria_repository import GradeHorariaRepository
from src.repositories.semestre_repository import SemestreRepository
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
        self.grade_horaria_repository = GradeHorariaRepository(db)
        self.semestre_repository = SemestreRepository(db)
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

        piso = calcular_piso_banca(banca, frentes)
        if piso <= 0:
            return None

        candidaturas_atuais = self.candidatura_repository.get_by_banca(banca.id)
        alocados_antes = len(candidaturas_atuais)
        deficit = piso - alocados_antes
        vaga_disponivel = teto - alocados_antes
        a_alocar = min(deficit, vaga_disponivel)
        if a_alocar <= 0:
            return None

        excluidos = self._excluidos(banca, candidaturas_atuais)

        pool_prioritario = self._pool_por_frentes(frentes, excluidos)
        fila = self._ordenar_por_rodizio(pool_prioritario, ultima_alocacao)

        if len(fila) < a_alocar:
            excluidos_com_prioritario = excluidos | {u.id for u in pool_prioritario}
            complemento = self._ordenar_por_rodizio(
                self._pool_geral(excluidos_com_prioritario), ultima_alocacao
            )
            fila = fila + complemento

        selecionados = fila[:a_alocar]
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
        """Quem o push não pode escalar nesta banca.

        ⭐ É o ÚNICO portão: os dois pools (`_pool_por_frentes` e `_pool_geral`)
        filtram por este conjunto, então somar alguém aqui o tira de todos os
        caminhos de uma vez, inclusive o de emergência que busca fora da frente.
        """
        excluidos = {c.usuario_id for c in candidaturas_atuais}
        excluidos.add(banca.coordenador_id)
        excluidos.update(e.usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id))
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
        """
        if not banca.data_hora:
            return set()

        # `weekday()` já é 0=segunda … 6=domingo, a mesma convenção da grade.
        dia_semana = banca.data_hora.weekday()
        if dia_semana > 4:
            return set()

        semestre = self.semestre_repository.get_por_data(banca.data_hora.date())
        if not semestre:
            return set()

        hora = banca.data_hora.time()
        return {
            faixa.usuario_id
            for faixa in self.grade_horaria_repository.get_por_semestre(semestre.id)
            if faixa.dia_semana == dia_semana
            and faixa.hora_inicio <= hora < faixa.hora_fim
        }

    def _pool_por_frentes(self, frentes: list, excluidos: Set[int]) -> List[UsuarioModel]:
        ids_das_frentes: Set[int] = set()
        for frente in frentes:
            ids_das_frentes.update(
                v.usuario_id for v in self.usuario_frente_repository.get_by_frente(frente.id)
            )
        ativos = self.usuario_repository.get_ativos()
        return [u for u in ativos if u.id in ids_das_frentes and u.id not in excluidos]

    def _pool_geral(self, excluidos: Set[int]) -> List[UsuarioModel]:
        ativos = self.usuario_repository.get_ativos()
        return [u for u in ativos if u.id not in excluidos]

    def _ordenar_por_rodizio(
        self, usuarios: List[UsuarioModel], ultima_alocacao: Dict[int, datetime]
    ) -> List[UsuarioModel]:
        # Quem nunca foi alocado (sem entrada no dict) entra primeiro; entre
        # os já alocados, quem foi há mais tempo vem antes de quem foi há
        # pouco — rodízio justo (§8).
        return sorted(usuarios, key=lambda u: ultima_alocacao.get(u.id, datetime.min))

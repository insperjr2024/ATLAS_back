from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.use_cases.notificacao.eventos import notificar_escalacao_banca
from src.utils.banca_status import calcular_status_banca
from src.utils.composicao_banca import ComposicaoBancaChecker
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc
from src.utils.piso_banca import calcular_piso_banca

#: A menos de tantos dias da banca, sair não pode QUEBRAR uma composição que
#: já estava completa (2026-09-09, refinado em 2026-09-11 a pedido).
#:
#: ⚠ **A trava é POR PESSOA, não da banca inteira.** A versão original travava
#: todo mundo assim que o total batia o piso — quem tinha acabado de entrar
#: sobrando, ou a 4ª pessoa de uma frente que só precisa de 3, ficava tão presa
#: quanto quem era, de fato, a única cobertura do piso. Agora só trava quem a
#: SAÍDA de fato descobriria: espelha, ao contrário, a reserva de vaga de
#: `create_candidatura` — lá se pergunta "esta vaga está reservada pro piso?",
#: aqui "sem esta pessoa, o piso continua coberto?". A diretoria
#: (`pode_gerir_membros`) ainda passa por cima, caso a caso.
PRAZO_TRAVA_DESALOCACAO_DIAS = 7


class UpdateCandidaturaRequest(BaseModel):
    banca_id: Optional[int] = None
    confirmado: Optional[bool] = None


class UpdateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, candidatura_id: int, request: UpdateCandidaturaRequest):
        data = request.dict(exclude_unset=True)
        confirmava_antes = getattr(self.repository.get_by_id(candidatura_id), "confirmado", None)
        candidatura = self.repository.update(candidatura_id, **data)
        if not candidatura:
            return None

        # Só na virada para confirmado: um PATCH que não mexe em `confirmado`
        # (ou que reconfirma o que já estava) não é notícia nenhuma.
        if candidatura.confirmado and not confirmava_antes:
            banca = self.banca_repository.get_by_id(candidatura.banca_id)
            if banca:
                notificar_escalacao_banca(
                    self.db,
                    banca.id,
                    candidatura.usuario_id,
                    banca.nome_projeto,
                    banca.data_hora,
                )

        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }


class DeleteCandidaturaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)

    def execute(self, candidatura_id: int, eh_gestao: bool = False) -> bool:
        candidatura = self.repository.get_by_id(candidatura_id)
        if not candidatura:
            return False

        banca = self.banca_repository.get_by_id(candidatura.banca_id)

        # Mesma virada do create: só a realização tranca. Antes da F5, uma
        # banca que escorregava deixava as pessoas presas na inscrição.
        if banca and calcular_status_banca(banca.data_hora, banca.realizado_em, cancelada_em=getattr(banca, "cancelada_em", None)) == "realizada":
            raise RegraDeNegocioError("Não é possível se desalocar: esta banca já foi realizada")

        # ⭐ Trava dos 7 dias, por pessoa (2026-09-09, refinada 2026-09-11).
        # A menos de uma semana da banca, sai livre quem quiser — A MENOS que
        # a saída dessa pessoa especificamente derrube um piso (membros ou
        # liderança) que hoje está coberto. A diretoria de projetos passa por
        # cima de qualquer jeito.
        if banca and not eh_gestao and self._saida_quebraria_composicao(banca, candidatura):
            raise RegraDeNegocioError(
                "Não dá mais para sair desta banca: é em menos de "
                f"{PRAZO_TRAVA_DESALOCACAO_DIAS} dias e sua saída deixaria a composição "
                "mínima descoberta. Fale com a diretoria de projetos."
            )

        return self.repository.delete(candidatura_id)

    def _saida_quebraria_composicao(self, banca, candidatura) -> bool:
        """A pergunta é sempre "SEM esta pessoa, a composição continua
        completa?" — nunca "quantos tem no total".

        ⚠ **Só trava quando a composição ESTÁ completa agora.** Uma banca já
        abaixo do piso (faltou gente puxar, o push ainda não rodou) não trava
        ninguém: não há o que proteger, e travar mais gente aí só pioraria uma
        situação que já vai precisar de intervenção de qualquer jeito. Mesma
        régua de quando isto era por banca — só mudou o "quem".

        📐 O `alocados == piso` do caso total legado é exatamente essa mesma
        conta, sem enxergar frente: só a pessoa que fecha o número exato entre
        "no piso" e "abaixo dele" fica presa; sobrando alguém, ninguém trava.
        """
        if not banca.data_hora:
            return False
        # `data_hora` é UTC sem tzinfo; `agora_utc()` também. Faltam N dias:
        dias = (banca.data_hora - agora_utc()).total_seconds() / 86400
        if dias > PRAZO_TRAVA_DESALOCACAO_DIAS:
            return False

        candidaturas = self.repository.get_by_banca(banca.id)
        ids_com_todos = {c.usuario_id for c in candidaturas}
        ids_sem_essa = ids_com_todos - {candidatura.usuario_id}

        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        if not vinculos:
            # Banca legada, sem vínculo de frente: não há composição por
            # frente a proteger, só o TOTAL — mesma régua de antes disto virar
            # por pessoa.
            piso = calcular_piso_banca(banca, [], self.db)
            if piso <= 0:
                return False
            return len(ids_com_todos) >= piso and len(ids_sem_essa) < piso

        # Mesma matriz que `create_candidatura` e o push automático leem —
        # import local pelo mesmo motivo dos dois: `use_cases` importa
        # `utils`, e a volta no nível do módulo fecharia o ciclo.
        from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

        regras = ResolverComposicaoUseCase(self.db).para([v.frente_id for v in vinculos])
        checker = ComposicaoBancaChecker(self.db)
        if not checker.verificar(banca, regras, ids_com_todos).ok:
            return False
        return not checker.verificar(banca, regras, ids_sem_essa).ok
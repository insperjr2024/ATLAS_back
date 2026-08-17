from datetime import date
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.utils.exceptions import RegraDeNegocioError


class UpdateDiasAmbientacaoRequest(BaseModel):
    dias_ambientacao: int = Field(ge=0, le=60)


class UpdateDiasAmbientacaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateDiasAmbientacaoRequest):
        projeto = self.repository.update(projeto_id, dias_ambientacao=request.dias_ambientacao)
        if not projeto:
            return None
        # 🤖 Encurtar a ambientação pode tê-la encerrado agora (§5.3): de 10
        # para 3 dias num projeto que já rodou 5. A virada sai junto com a
        # edição, não no dia seguinte.
        EncerrarAmbientacaoUseCase(self.db).executar_para(projeto_id)
        atualizado = self.repository.get_by_id(projeto_id)
        return {
            "id": atualizado.id,
            "dias_ambientacao": atualizado.dias_ambientacao,
            "status": atualizado.status,
        }


class UpdateDiaReuniaoPadraoRequest(BaseModel):
    # 1=segunda … 5=sexta (mesmo catálogo do cadastro, `DIAS_REUNIAO` no
    # front) — None tira o dia padrão sem apagar as reuniões já marcadas
    # em `ReuniaoSemanalModel`, que são registros à parte.
    dia_reuniao_padrao: Optional[int] = Field(default=None, ge=1, le=5)


class UpdateDiaReuniaoPadraoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateDiaReuniaoPadraoRequest):
        projeto = self.repository.update(projeto_id, dia_reuniao_padrao=request.dia_reuniao_padrao)
        if not projeto:
            return None
        return {"id": projeto.id, "dia_reuniao_padrao": projeto.dia_reuniao_padrao}


class UpdateMaxConsultoresRequest(BaseModel):
    max_consultores: int = Field(ge=0, le=20)


class UpdateMaxConsultoresUseCase:
    """O teto de consultores, editável depois do cadastro — até aqui só dava
    pra escolher na criação do projeto (§6.3: é o número que `validar_equipe`
    usa pra recusar equipe grande demais, e que Vagas usa pra calcular
    quantas vagas ainda tem).

    ⚠ Não deixa baixar o teto abaixo da equipe atual: `validar_equipe` já
    recusaria a próxima edição de equipe com um erro sem contexto nenhum de
    onde veio o descompasso. Aqui, no momento em que o número mudaria, dá pra
    dizer exatamente quem sobra.
    """

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, projeto_id: int, request: UpdateMaxConsultoresRequest):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        atuais = self.membro_repository.get_by_projeto(projeto_id, apenas_atuais=True)
        consultores = [m for m in atuais if m.papel == "consultor"]
        if len(consultores) > request.max_consultores:
            raise RegraDeNegocioError(
                f"A equipe tem {len(consultores)} consultores, mas o novo teto seria "
                f"{request.max_consultores}. Tire alguém da equipe antes de baixar o teto."
            )

        atualizado = self.repository.update(projeto_id, max_consultores=request.max_consultores)
        return {"id": atualizado.id, "max_consultores": atualizado.max_consultores}


class UpdateEntregaPrevistaClienteRequest(BaseModel):
    #: `None` limpa a promessa — venda que ainda não fechou data, ou correção
    #: de um valor digitado errado. Não apaga entrega nenhuma: a data REAL é
    #: derivada dos escopos e não passa por aqui.
    data_entrega_prevista_cliente: Optional[date] = None


class UpdateEntregaPrevistaClienteUseCase:
    """⭐ A promessa feita ao cliente — a data combinada na venda.

    ⚠ **Não confundir com a entrega ao cliente que aparece ao lado dela.**
    Aquela é DERIVADA (a entrega do último escopo) e não se edita: ela conta o
    que aconteceu. Esta guarda o que foi prometido, e é a diferença entre as
    duas que responde "entregamos no prazo?" no nível do projeto.

    ⚠ **Sem a trava do §5.5.** Registrar a entrega de um ESCOPO exige banca
    aprovada, porque é registro de fato consumado. Isto é planejamento
    comercial: prometer uma data não afirma que algo foi entregue, e travá-la
    atrás da banca impediria a venda de registrar o combinado.
    """

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateEntregaPrevistaClienteRequest):
        projeto = self.repository.update(
            projeto_id,
            data_entrega_prevista_cliente=request.data_entrega_prevista_cliente,
        )
        if not projeto:
            return None
        return {
            "id": projeto.id,
            "data_entrega_prevista_cliente": projeto.data_entrega_prevista_cliente,
        }

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.semestre_repository import SemestreRepository
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


class UpdateCalendarioRequest(BaseModel):
    #: O rótulo de um calendário existente na frente do projeto, ou `None` para
    #: seguir o padrão dela. Ver `dia_nao_letivo.variante`.
    calendario: Optional[str] = Field(default=None, max_length=30)


class UpdateCalendarioUseCase:
    """Qual calendário acadêmico este projeto segue (§5.4).

    Uma frente pode cobrir cursos com calendários diferentes — dentro da Tech,
    Ciência da Computação não tem as semanas de avaliação das engenharias. O
    calendário escolhido aqui é o que a contagem de dias úteis do projeto usa:
    janela de escopo, atraso, ambientação e o cinza do cronograma.

    Só aceita nome de calendário que EXISTA em alguma frente do projeto. Um
    rótulo digitado errado não daria erro nenhum na hora — simplesmente não
    casaria com dia algum, e o projeto passaria a contar a semana de provas de
    ninguém.
    """

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, projeto_id: int, request: UpdateCalendarioRequest):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        escolhido = (request.calendario or "").strip() or None
        if escolhido:
            semestre = self.semestre_repository.get_ativo()
            if not semestre:
                raise RegraDeNegocioError(
                    "Não há gestão ativa, então ainda não existe calendário para escolher"
                )
            frentes = {e.frente_id for e in self.escopo_repository.get_by_projeto(projeto_id)}
            disponiveis = {
                nome
                for frente_id in frentes
                for nome in self.dia_nao_letivo_repository.listar_variantes(
                    semestre.id, frente_id
                )
            }
            if escolhido not in disponiveis:
                raise RegraDeNegocioError(
                    f"Nenhuma frente deste projeto tem um calendário chamado {escolhido}. "
                    "Carregue o calendário em Calendários base antes de apontar para ele."
                )

        atualizado = self.repository.update(projeto_id, calendario=escolhido)
        return {"id": atualizado.id, "calendario": atualizado.calendario}


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


class UpdateFrentesRequest(BaseModel):
    frente_ids: List[int] = Field(min_length=1)

    @field_validator("frente_ids")
    @classmethod
    def frentes_unicas(cls, v: List[int]) -> List[int]:
        if len(set(v)) != len(v):
            raise ValueError("Frentes repetidas")
        return v


class UpdateFrentesUseCase:
    """Quais frentes venderam o projeto (§2: 2+ frentes = sinérgico) —
    editável depois do cadastro pelo mesmo motivo do teto de consultores:
    só dava pra fixar na criação, e cadastro errado só se percebe depois.

    ⚠ Não deixa tirar uma frente que já tem escopo vendido nela: o escopo
    guarda `frente_id` (`escopos-projeto`), e um escopo apontando pra uma
    frente que o projeto não tem mais é um estado que nada mais no sistema
    sabe representar. Tirar o escopo primeiro é decisão de quem edita, não
    algo pra esta rota inferir sozinha.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.frente_catalogo = FrenteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, projeto_id: int, request: UpdateFrentesRequest):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        for frente_id in request.frente_ids:
            if not self.frente_catalogo.get_by_id(frente_id):
                raise RegraDeNegocioError(f"Frente {frente_id} não encontrada")

        atuais = {f.frente_id for f in self.frente_repository.get_by_projeto(projeto_id)}
        removidas = atuais - set(request.frente_ids)
        if removidas:
            escopos = self.escopo_repository.get_by_projeto(projeto_id)
            presas = {e.frente_id for e in escopos if e.frente_id in removidas}
            if presas:
                nomes = ", ".join(
                    f.nome for f in (self.frente_catalogo.get_by_id(fid) for fid in presas) if f
                )
                raise RegraDeNegocioError(
                    f"Não é possível remover a(s) frente(s) {nomes}: há escopo vendido "
                    "nela(s). Remova o escopo primeiro."
                )

        self.frente_repository.delete_by_projeto(projeto_id)
        for frente_id in request.frente_ids:
            self.frente_repository.create(projeto_id=projeto_id, frente_id=frente_id)

        return {
            "id": projeto.id,
            "frente_ids": request.frente_ids,
            "sinergico": len(request.frente_ids) > 1,
        }

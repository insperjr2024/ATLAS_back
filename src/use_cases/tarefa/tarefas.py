"""Tarefas do kanban (§6.4) e reuniões semanais.

⚠ Nenhuma checagem de POSIÇÃO aqui, de propósito: o §3 dá "criar tarefa" e
"mover e editar tarefa" aos **quatro** perfis. A trava é só "você enxerga
este projeto" (`exigir_acesso_ao_projeto` na rota), que já recorta gerente
por frente e coord/consultor por alocação.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.cronograma.podar_escopo import (
    exigir_poda_permitida,
    podar_cronograma_do_escopo,
    resumir_a_poda,
)
from src.use_cases.tarefa.comentarios import exigir_permissao_de_edicao
from src.utils.exceptions import RegraDeNegocioError
from src.utils.tarefa_status import (
    calcular_urgencia,
    dias_para_prazo,
    eh_vencida,
    janela_semana,
)

def serializar_tarefa(tarefa, coluna, hoje: Optional[date] = None) -> dict:
    """`coluna` é obrigatória porque "vencida" depende de `encerra_tarefa`
    dela — não de uma lista fixa de status."""
    encerra = bool(coluna and coluna.encerra_tarefa)
    return {
        "id": tarefa.id,
        "projeto_id": tarefa.projeto_id,
        "projeto_escopo_id": tarefa.projeto_escopo_id,
        "titulo": tarefa.titulo,
        "responsavel_id": tarefa.responsavel_id,
        "prazo": tarefa.prazo,
        "coluna_id": tarefa.coluna_id,
        "criado_por": tarefa.criado_por,
        "criado_em": tarefa.criado_em,
        "movida_em": tarefa.movida_em,
        # 🧮 Todos derivados, nunca gravados.
        "vencida": eh_vencida(tarefa.prazo, encerra, hoje),
        # ⏰ A gradação que o card usa para avisar ANTES do prazo estourar.
        "urgencia": calcular_urgencia(tarefa.prazo, encerra, hoje),
        "dias_para_prazo": dias_para_prazo(tarefa.prazo, hoje),
    }


class CreateTarefaRequest(BaseModel):
    titulo: str
    responsavel_id: int
    prazo: date
    projeto_escopo_id: Optional[int] = None
    #: Vazio = a primeira coluna do board.
    coluna_id: Optional[int] = None


class UpdateTarefaRequest(BaseModel):
    titulo: Optional[str] = None
    responsavel_id: Optional[int] = None
    prazo: Optional[date] = None
    coluna_id: Optional[int] = None
    projeto_escopo_id: Optional[int] = None


class ListTarefasUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)
        self.coluna_repository = TarefaColunaRepository(db)

    def execute(self, projeto_id: int) -> List[dict]:
        hoje = date.today()
        colunas = {c.id: c for c in self.coluna_repository.listar(projeto_id)}
        return [
            serializar_tarefa(t, colunas.get(t.coluna_id), hoje)
            for t in self.repository.get_by_projeto(projeto_id)
        ]


class CreateTarefaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.coluna_repository = TarefaColunaRepository(db)

    def execute(self, projeto_id: int, request: CreateTarefaRequest, criado_por: int):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None
        if not request.titulo.strip():
            raise RegraDeNegocioError("A tarefa precisa de um título")
        if not self.usuario_repository.get_by_id(request.responsavel_id):
            raise RegraDeNegocioError("Responsável não encontrado")

        coluna = (
            self.coluna_repository.get_by_id(request.coluna_id)
            if request.coluna_id
            else self.coluna_repository.primeira(projeto_id)
        )
        # A coluna tem que ser DESTE projeto — cada board é o seu.
        if not coluna or coluna.projeto_id != projeto_id:
            raise RegraDeNegocioError("Coluna inválida")

        tarefa = self.repository.create(
            projeto_id=projeto_id,
            projeto_escopo_id=request.projeto_escopo_id,
            titulo=request.titulo.strip(),
            responsavel_id=request.responsavel_id,
            prazo=request.prazo,
            coluna_id=coluna.id,
            criado_por=criado_por,
        )
        return serializar_tarefa(tarefa, coluna)


class UpdateTarefaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)
        self.coluna_repository = TarefaColunaRepository(db)

    def execute(self, tarefa_id: int, request: UpdateTarefaRequest, current_user=None):
        tarefa = self.repository.get_by_id(tarefa_id)
        if not tarefa:
            return None

        dados = request.dict(exclude_unset=True)

        # ⭐ Mover ≠ editar. Trocar a COLUNA é do time inteiro (§3: os quatro
        # perfis movem tarefa) — é o kanban funcionando. Mexer no CONTEÚDO
        # (título, responsável, prazo) é da diretoria e de quem criou.
        campos_de_conteudo = set(dados) - {"coluna_id"}
        if campos_de_conteudo and current_user is not None:
            exigir_permissao_de_edicao(tarefa, current_user)

        if "coluna_id" in dados and dados["coluna_id"] is not None:
            destino = self.coluna_repository.get_by_id(dados["coluna_id"])
            if not destino or destino.projeto_id != tarefa.projeto_id:
                raise RegraDeNegocioError("Coluna não encontrada")
            # `movida_em` só é tocado quando a COLUNA muda de fato — é o que
            # torna a "última movimentação" do §7.2 significativa. Renomear a
            # tarefa não pode fingir atividade.
            if dados["coluna_id"] != tarefa.coluna_id:
                dados["movida_em"] = datetime.now()

        atualizada = self.repository.update(tarefa_id, **dados)
        return serializar_tarefa(
            atualizada, self.coluna_repository.get_by_id(atualizada.coluna_id)
        )


class DeleteTarefaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)

    def execute(self, tarefa_id: int) -> bool:
        return self.repository.delete(tarefa_id)


# ------------------------------------------------------------------ reuniões


class ReuniaoRequest(BaseModel):
    data_reuniao: date
    #: ⭐ Sobre qual escopo foi. Preenchido = **reunião inicial**, que abre a
    #: janela do escopo. Vazio = **reunião geral** do projeto, que conta para o
    #: §7.2 ("projeto sem reunião na semana") mas não mexe em contagem nenhuma.
    projeto_escopo_id: Optional[int] = None
    #: Texto livre — a ata informal da reunião geral (§12). Sem estrutura de
    #: propósito: campos obrigatórios aqui fariam ninguém preencher.
    observacoes: Optional[str] = None


def serializar_reuniao(reuniao) -> dict:
    return {
        "id": reuniao.id,
        "projeto_id": reuniao.projeto_id,
        "projeto_escopo_id": reuniao.projeto_escopo_id,
        "data_reuniao": reuniao.data_reuniao,
        "observacoes": reuniao.observacoes,
        # Derivado, não gravado: um campo "tipo" poderia divergir do vínculo e
        # criar uma reunião "geral" com escopo preenchido.
        "tipo": "inicial" if reuniao.projeto_escopo_id else "geral",
        "registrado_por": reuniao.registrado_por,
    }


def _nome_do_escopo(escopo, catalogo_repository) -> str:
    """Mesma régua do resto do sistema: "Outro" tem nome customizado e não tem
    linha de catálogo (§4)."""
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = (
        catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
    )
    return do_catalogo.nome if do_catalogo else "escopo"


def _exigir_escopo_do_projeto(db: Session, projeto_id: int, projeto_escopo_id: int):
    escopo = ProjetoEscopoRepository(db).get_by_id(projeto_escopo_id)
    if not escopo or escopo.projeto_id != projeto_id:
        raise RegraDeNegocioError("Escopo não encontrado neste projeto")
    if escopo.status == "cancelado":
        raise RegraDeNegocioError("Este escopo foi cancelado")
    return escopo


def sincronizar_inicio_do_escopo(db: Session, projeto_escopo_id: Optional[int]) -> bool:
    """⭐ `projeto_escopo.data_inicio` = a data da PRIMEIRA reunião do escopo.

    Não é um campo digitado: é derivado das reuniões registradas, recalculado
    a cada criar/mover/apagar. É isso que faz "movi a reunião inicial de quarta
    para quinta" e "apaguei a reunião errada" acertarem a contagem sozinhos,
    sem ninguém lembrar de corrigir uma data em outra tela.

    🔒 Escopo entregue não se mexe: `data_entrega_real` congelou a janela
    (§5.4) e reabrir o início mudaria dias já fechados.

    Devolve `True` quando a contagem começou agora — é o que a rota usa para
    avisar a tela.
    """
    if not projeto_escopo_id:
        return False

    repository = ProjetoEscopoRepository(db)
    escopo = repository.get_by_id(projeto_escopo_id)
    if not escopo or escopo.data_entrega_real or escopo.status == "cancelado":
        return False

    reunioes = ReuniaoSemanalRepository(db).get_by_escopo(projeto_escopo_id)
    primeira = reunioes[0].data_reuniao if reunioes else None
    if primeira == escopo.data_inicio:
        return False

    if primeira is None:
        # Sumiu a última reunião do escopo: ele volta a não ter começado, e a
        # contagem devolve zero de novo (regra 1 de `contagem_dias.py`).
        repository.update(projeto_escopo_id, data_inicio=None, status="nao_iniciado")
        return False

    comecou_agora = escopo.data_inicio is None
    repository.update(projeto_escopo_id, data_inicio=primeira, status="em_andamento")
    return comecou_agora


class ListReunioesUseCase:
    def __init__(self, db: Session):
        self.repository = ReuniaoSemanalRepository(db)

    def execute(self, projeto_id: int) -> dict:
        reunioes = self.repository.get_by_projeto(projeto_id)
        inicio, fim = janela_semana()
        return {
            "reunioes": [serializar_reuniao(r) for r in reunioes],
            "semana_atual": {"inicio": inicio, "fim": fim},
            # 🧮 "Sem reunião esta semana" = ausência de linha na janela.
            "tem_reuniao_esta_semana": any(
                inicio <= r.data_reuniao <= fim for r in reunioes
            ),
        }


class CreateReuniaoUseCase:
    """Marcar a reunião no calendário do cronograma — e, quando ela é a
    primeira de um escopo, **abrir a janela dele** (§5.4, §12).

    ⭐ Não existe mais pré-requisito de banca. A ordem do §6 é reunião inicial
    → etapas → banca → entrega, e era exatamente o inverso que a trava antiga
    impunha (a banca precisava estar marcada ANTES da reunião inicial).
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ReuniaoSemanalRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: ReuniaoRequest, registrado_por: int):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None
        # Por dia E por escopo: a reunião geral e a inicial de um escopo cabem
        # no mesmo dia, mas duas do mesmo escopo (ou duas gerais) não.
        if self.repository.get_por_data(
            projeto_id, request.data_reuniao, request.projeto_escopo_id
        ):
            raise RegraDeNegocioError(
                "Já existe uma reunião deste tipo registrada neste dia"
            )

        if request.projeto_escopo_id:
            _exigir_escopo_do_projeto(self.db, projeto_id, request.projeto_escopo_id)
            self._exigir_uma_reuniao_inicial(request.projeto_escopo_id)

        reuniao = self.repository.create(
            projeto_id=projeto_id,
            projeto_escopo_id=request.projeto_escopo_id,
            data_reuniao=request.data_reuniao,
            observacoes=(request.observacoes or "").strip() or None,
            registrado_por=registrado_por,
        )
        iniciou = sincronizar_inicio_do_escopo(self.db, request.projeto_escopo_id)
        return {**serializar_reuniao(reuniao), "escopo_iniciado": iniciou}

    def _exigir_uma_reuniao_inicial(self, projeto_escopo_id: int) -> None:
        """⭐ **Um escopo tem UMA reunião inicial.**

        ⚠ O estrago que isto evita é silencioso. `data_inicio` do escopo é
        DERIVADA da reunião mais antiga (ver `sincronizar_inicio_do_escopo`),
        e é dela que sai a janela inteira: prazo das etapas, data-limite da
        banca, cálculo de atraso. Uma segunda reunião marcada numa data
        anterior reescrevia todas essas contas sem ninguém pedir nada — o
        cronograma "andava" sozinho.

        📐 Não existe reunião de escopo que não seja a inicial. A tela só
        oferece dois modos: "Reunião inicial", que exige escopo, e "Reunião
        geral", que é do projeto e vai sem escopo. E o serializador marca como
        `inicial` TODA reunião com escopo — então duas viravam duas "Reunião
        inicial" no mesmo calendário, o que também não se explica a ninguém.

        Mudar a data continua possível: move-se a reunião que já existe, e a
        janela é recalculada junto. O que não se faz é criar outra.
        """
        existentes = self.repository.get_by_escopo(projeto_escopo_id)
        if not existentes:
            return
        quando = existentes[0].data_reuniao.strftime("%d/%m/%Y")
        raise RegraDeNegocioError(
            f"Este escopo já teve a reunião inicial, em {quando}, e é ela que abre a "
            "janela de dias vendidos. Para corrigir a data, abra a reunião que já "
            "existe no calendário e mova para o dia certo — assim a janela é "
            "recalculada junto."
        )


class UpdateReuniaoUseCase:
    """Mover a reunião de dia (registrou quarta, aconteceu quinta) ou corrigir
    sobre qual escopo ela foi.

    **Mover a reunião INICIAL poda o cronograma do escopo** (ver
    `cronograma/podar_escopo.py`): a data dela é a origem da janela, e o que
    fica fora da janela nova é apagado. O que continua dentro fica. Só a
    diretoria faz isso direto; para os demais é pedido.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ReuniaoSemanalRepository(db)

    def execute(self, reuniao_id: int, request: ReuniaoRequest, eh_diretor_projetos: bool = False):
        reuniao = self.repository.get_by_id(reuniao_id)
        if not reuniao:
            return None
        escopo_anterior = reuniao.projeto_escopo_id

        # `exclude_unset`: quem só move o dia não manda o escopo, e não pode
        # perder o vínculo por omissão. Mandar `null` explícito é que desliga.
        dados = request.dict(exclude_unset=True)
        escopo_alvo = dados.get("projeto_escopo_id", escopo_anterior)

        # A largada mudou de dia: a janela anda, e o que não couber nela é
        # podado. `nova_largada` é a data que o escopo VAI ter — `None` quando
        # a reunião vai para outro escopo e este fica sem largada nenhuma, e aí
        # nada cabe (é o reset inteiro, o único caso em que ele ainda acontece).
        muda_a_largada = (
            escopo_anterior is not None and reuniao.data_reuniao != request.data_reuniao
        )
        nova_largada = request.data_reuniao if escopo_alvo == escopo_anterior else None
        if muda_a_largada:
            exigir_poda_permitida(self.db, escopo_anterior)
            if not eh_diretor_projetos:
                resumo = resumir_a_poda(self.db, escopo_anterior, nova_largada)
                raise RegraDeNegocioError(
                    "Mudar a data da reunião inicial reposiciona a janela deste escopo"
                    f"{_descrever_perda(resumo)}. Por isso a mudança é decisão da "
                    "diretoria — peça a ela, explicando por que a data precisa mudar."
                )

        existente = self.repository.get_por_data(
            reuniao.projeto_id, request.data_reuniao, escopo_alvo
        )
        if existente and existente.id != reuniao_id:
            raise RegraDeNegocioError("Já existe uma reunião deste tipo registrada neste dia")

        if escopo_alvo and escopo_alvo != escopo_anterior:
            _exigir_escopo_do_projeto(self.db, reuniao.projeto_id, escopo_alvo)

        campos = {
            "data_reuniao": request.data_reuniao,
            "projeto_escopo_id": escopo_alvo,
        }
        # Mesma regra do escopo: só mexe nas observações quem as mandou.
        if "observacoes" in dados:
            campos["observacoes"] = (request.observacoes or "").strip() or None

        # A poda recebe a largada nova de fora, então não depende de o update já
        # ter rodado — mas continua ANTES dele porque `data_entrega_planejada` e
        # a data da banca são lidas do estado atual.
        podado = (
            podar_cronograma_do_escopo(self.db, escopo_anterior, nova_largada)
            if muda_a_largada
            else None
        )

        atualizada = self.repository.update(reuniao_id, **campos)
        # Os DOIS lados: o escopo que perdeu a reunião pode ter perdido a
        # largada dele, e o que ganhou pode estar começando agora.
        iniciou = sincronizar_inicio_do_escopo(self.db, escopo_alvo)
        if escopo_anterior and escopo_anterior != escopo_alvo:
            sincronizar_inicio_do_escopo(self.db, escopo_anterior)
        return {
            **serializar_reuniao(atualizada),
            "escopo_iniciado": iniciou,
            # A tela usa isto para contar o que a poda mexeu — silêncio depois
            # de apagar ou encurtar etapa é o pior desfecho possível.
            "cronograma_podado": podado,
        }


class DeleteReuniaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ReuniaoSemanalRepository(db)

    def execute(self, reuniao_id: int) -> bool:
        reuniao = self.repository.get_by_id(reuniao_id)
        escopo_id = reuniao.projeto_escopo_id if reuniao else None
        apagou = self.repository.delete(reuniao_id)
        if apagou:
            sincronizar_inicio_do_escopo(self.db, escopo_id)
        return apagou


def _descrever_perda(resumo: dict) -> str:
    """"— apagando 1 etapa, encurtando 2 e desmarcando a banca de 20/08".

    A frase entra no meio da recusa, e nasce vazia quando a poda não mexe em
    nada: dizer "reposiciona a janela, apagando 0 etapas" faria a pessoa achar
    que a plataforma está confusa. E agora ela costuma nascer vazia mesmo — o
    caso comum de mover a largada um ou dois dias não perde etapa nenhuma.

    Apagar e encurtar são frases separadas de propósito: a diferença entre
    "some" e "encolhe" é exatamente o que a pessoa precisa para decidir se vale
    pedir à diretoria.
    """
    partes = []
    apagadas = resumo.get("etapas_apagadas") or 0
    if apagadas:
        partes.append(
            f"apagando {apagadas} etapa{'s' if apagadas > 1 else ''} "
            f"que fica{'m' if apagadas > 1 else ''} fora dela"
        )
    aparadas = resumo.get("etapas_aparadas") or 0
    if aparadas:
        partes.append(f"encurtando outra{'s' if aparadas > 1 else ''} {aparadas}")
    if resumo.get("banca_desmarcada"):
        dia = resumo["banca_desmarcada"][8:10] + "/" + resumo["banca_desmarcada"][5:7]
        partes.append(f"desmarcando a banca de {dia}")
    if not partes:
        return ""
    return " — " + (" e ".join(partes) if len(partes) < 3 else ", ".join(partes))

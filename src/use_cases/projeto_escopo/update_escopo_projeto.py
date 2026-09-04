"""Editar, iniciar e entregar um escopo vendido.

🔒 A trava do §5.5 mora em `RegistrarEntregaEscopoUseCase`: "nenhum escopo é
apresentado ao cliente sem antes passar pela banca — a plataforma deve
IMPEDIR esse pulo". O front esconde o botão; quem barra é este use case.
"""

import logging
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.entrega_alteracao_repository import EntregaAlteracaoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository
from src.use_cases.notificacao.eventos import notificar_entrega, notificar_entrega_alterada
from src.use_cases.projeto_escopo.create_escopo_projeto import (
    validar_calendario_do_escopo,
)
from src.utils.exceptions import RegraDeNegocioError

logger = logging.getLogger(__name__)


def _nome_escopo(escopo, catalogo_repository) -> str:
    """Mesma régua do resto do sistema: "Outro" tem nome customizado e não tem
    linha de catálogo (§4).

    Função de módulo, não método: os dois use cases daqui precisam dela, e o
    de entrega já a tinha copiada.
    """
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
    return do_catalogo.nome if do_catalogo else "escopo"


class UpdateEscopoProjetoRequest(BaseModel):
    #: Qual item do catálogo este escopo é. Editável porque o cadastro erra o
    #: tipo (um escopo entra como "Pesquisa de mercado" quando devia ser
    #: "Plano de marketing"), e sem isso a correção só existia apagando a
    #: linha e recriando, o que também apaga reunião inicial e banca já
    #: pendurados nela.
    #:
    #: Vale junto de `nome_customizado`: os dois formam a mesma invariante do
    #: cadastro (exatamente um preenchido), e por isso os dois dependem de
    #: `exclude_unset` para mandar só um não deixar o outro num valor antigo
    #: que quebra a invariante.
    escopo_id: Optional[int] = None
    nome_customizado: Optional[str] = None
    dias_uteis_vendidos: Optional[int] = None
    data_entrega_planejada: Optional[date] = None
    ordem: Optional[int] = None
    #: ⭐ O calendário base do escopo (§5.4). Editável porque o cadastro erra:
    #: um escopo entra em "Engenharias" e o time é de Ciência da Computação, e
    #: até alguém corrigir a janela inteira é contada na semana de avaliação
    #: errada.
    #:
    #: Nulo é resposta legítima (a frente que tem um calendário só), então este
    #: campo depende de `exclude_unset` para distinguir "não mandei" de "mandei
    #: nulo" — é por isso que ele não pode ganhar um default diferente.
    calendario: Optional[str] = None


def _normalizar_tipo_escopo(dados: dict, anterior, catalogo_repository) -> None:
    """Troca de tipo do escopo: qual item do catálogo ele é, ou "Outro" com
    nome digitado.

    Mexe nos dois campos juntos porque a invariante é dos dois: exatamente um
    preenchido, nunca os dois nem nenhum. Mandar só `escopo_id` teria que
    limpar o `nome_customizado` antigo, e vice-versa, senão o banco fica com
    os dois preenchidos mesmo que o front só quisesse trocar um lado.

    A frente não entra aqui: continua fixa no que já está gravado, a mesma
    régua do `calendario` logo acima.
    """
    if "escopo_id" not in dados and "nome_customizado" not in dados:
        return

    escopo_id_veio = "escopo_id" in dados
    nome_veio = "nome_customizado" in dados

    novo_escopo_id = dados["escopo_id"] if escopo_id_veio else anterior.escopo_id
    novo_nome = dados["nome_customizado"] if nome_veio else anterior.nome_customizado
    novo_nome = (novo_nome or "").strip() or None

    # Escolher um lado apaga o outro automaticamente quando só ELE veio na
    # request. Sem isso, mandar só `escopo_id` (trocar de item do catálogo,
    # ou sair de "Outro") batia no `nome_customizado` que sobrou do estado
    # anterior, e os dois ficavam preenchidos ao mesmo tempo.
    if escopo_id_veio and novo_escopo_id is not None and not nome_veio:
        novo_nome = None
    elif nome_veio and novo_nome is not None and not escopo_id_veio:
        novo_escopo_id = None

    tem_catalogo = novo_escopo_id is not None
    tem_customizado = bool(novo_nome)

    if tem_catalogo and tem_customizado:
        raise RegraDeNegocioError(
            "Escolha um escopo do catálogo OU digite um nome customizado, não os dois"
        )
    if not tem_catalogo and not tem_customizado:
        raise RegraDeNegocioError("Escolha um escopo do catálogo ou digite o nome de um 'Outro'")
    if tem_catalogo and not catalogo_repository.get_by_id(novo_escopo_id):
        raise RegraDeNegocioError(f"Escopo {novo_escopo_id} não encontrado no catálogo")

    dados["escopo_id"] = novo_escopo_id
    dados["nome_customizado"] = novo_nome


class UpdateEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, escopo_id: int, request: UpdateEscopoProjetoRequest):
        dados = request.dict(exclude_unset=True)
        if "dias_uteis_vendidos" in dados and dados["dias_uteis_vendidos"] is not None:
            if dados["dias_uteis_vendidos"] <= 0:
                raise RegraDeNegocioError("Os dias úteis vendidos precisam ser maiores que zero")

        # A data ANTES do update: o aviso só faz sentido dizendo de onde para
        # onde, e depois de gravar ela já se perdeu.
        anterior = self.repository.get_by_id(escopo_id)
        data_antiga = anterior.data_entrega_planejada if anterior else None

        if anterior:
            _normalizar_tipo_escopo(dados, anterior, self.catalogo_repository)

        # O calendário é validado contra a frente do escopo que ESTÁ no banco —
        # a frente não é editável por aqui, então não há como a dupla divergir.
        if "calendario" in dados and anterior:
            dados["calendario"] = validar_calendario_do_escopo(
                self.db, anterior.frente_id, dados["calendario"]
            )

        escopo = self.repository.update(escopo_id, **dados)
        if not escopo:
            return None

        # Só quando a data de entrega REALMENTE mudou — este endpoint também
        # edita nome e dias vendidos, e nenhum dos dois é notícia.
        if "data_entrega_planejada" in dados and data_antiga != escopo.data_entrega_planejada:
            projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
            if projeto:
                notificar_entrega_alterada(
                    self.db,
                    projeto,
                    data_antiga,
                    escopo.data_entrega_planejada,
                    nome_escopo=_nome_escopo(escopo, self.catalogo_repository),
                    escopo_id=escopo.id,
                )

        return {"id": escopo.id}


# ⭐ Não existe mais um "iniciar escopo" digitado à parte. A `data_inicio` do
# §5.4 nasce da reunião inicial registrada no calendário de reuniões semanais
# (`use_cases/tarefa/tarefas.py`), que é a única porta que a escreve — ter duas
# faria a contagem depender de qual delas foi usada por último.


class RegistrarEntregaEscopoRequest(BaseModel):
    data_entrega_real: date
    #: §13: obrigatória para ALTERAR uma entrega já registrada. Na primeira
    #: marcação não é pedida — marcar a entrega é o passo normal do fluxo.
    justificativa: Optional[str] = None


class RegistrarEntregaEscopoUseCase:
    """🔒 A trava do §5.5 — o coração da costura F4×F5.

    O campo que a trava lê (`banca.resultado`) nasceu na migration 5; o campo
    que ela protege (`projeto_escopo.data_entrega_real`) nasceu na 4. É por
    isso que as duas fatias são uma só.

    Desde a reformulação do cronograma há um segundo gate aqui, o do §13:
    marcar a entrega é livre, **alterar** uma que já existe é da diretoria.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.alteracao_repository = EntregaAlteracaoRepository(db)

    def execute(
        self,
        escopo_id: int,
        request: RegistrarEntregaEscopoRequest,
        eh_diretor_projetos: bool = False,
        current_user=None,
    ):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None

        if not escopo.data_inicio:
            raise RegraDeNegocioError("Este escopo ainda não foi iniciado")

        # ⚠ Entregar antes de começar é impossível, e a data entra em contas que
        # ninguém revisa: `data_entrega_cliente` do projeto é o MAIOR
        # `data_entrega_real` dos escopos, e o "tempo parado entre escopos" mede
        # a partir dela. Uma data digitada errada (2019 em vez de 2029) não
        # aparece como erro — aparece como um vão de dez anos num insight.
        #
        # Só esta borda, e de propósito: entregar DEPOIS do fim da janela é
        # legítimo (§5.5 — a apresentação ao cliente vem depois da banca), e um
        # teto no futuro seria arbitrário.
        if request.data_entrega_real < escopo.data_inicio:
            raise RegraDeNegocioError(
                f"A entrega não pode ser anterior ao início do escopo "
                f"({escopo.data_inicio:%d/%m/%Y})"
            )

        data_antiga = escopo.data_entrega_real
        self._exigir_alteracao_permitida(data_antiga, request, eh_diretor_projetos)

        # 🔒 A trava do §5.5: nada vai ao cliente sem a banca APROVAR.
        #
        # ⚠ **Só vale para a PRIMEIRA marcação.** Corrigir a data de uma entrega
        # que já aconteceu é outro assunto — é o §13, e ele já tem gate próprio
        # logo acima (`_exigir_alteracao_permitida`, que exige diretoria e
        # justificativa). Aplicar a trava aqui também devolveria 422 sobre fato
        # consumado: nem a diretoria conseguiria acertar a data de um escopo
        # entregue antes desta regra existir. Mesmo raciocínio do
        # `update_cronograma.py`, que libera o cronograma depois da entrega.
        #
        # ⭐ Três degraus, e cada mensagem diz qual falhou — "não pode entregar"
        # sem dizer por quê deixa quem marca sem saída. Marcar a banca, realizar
        # a banca, e a banca aprovar.
        #
        # O terceiro degrau só existe porque agora há como preenchê-lo: o
        # resultado sai da assinatura de diretoria + gerente da frente
        # (`use_cases/banca/aprovar_banca.py`). Enquanto o veredito era uma
        # string que ninguém digitava, exigi-lo aqui teria travado todas as
        # entregas sem caminho de saída — foi por isso que a exigência tinha
        # sido removida antes.
        if data_antiga is None:
            banca = self.banca_repository.get_by_projeto_escopo(escopo_id)
            if not banca:
                raise RegraDeNegocioError(
                    "A entrega só é liberada depois da banca do escopo acontecer — "
                    "este escopo ainda não tem banca marcada"
                )
            if not banca.realizado_em:
                raise RegraDeNegocioError(
                    "A entrega só é liberada depois da banca do escopo ser realizada"
                )
            if banca.resultado is None:
                raise RegraDeNegocioError(
                    "A banca deste escopo ainda não tem resultado — a entrega libera "
                    "quando os avaliadores votarem. Se o prazo já passou sem votos, a "
                    "diretoria pode registrar o resultado manualmente"
                )
            if banca.resultado != "aprovada":
                raise RegraDeNegocioError(
                    "A banca deste escopo não foi aprovada — é preciso marcar uma nova "
                    "banca antes de entregar ao cliente"
                )

        # ⚠ **A data NÃO muda o status.** Quem move o escopo para "Entregue" é a
        # confirmação explícita (`ConfirmarEntregaEscopoUseCase`) — do
        # coordenador do projeto ou da diretoria.
        #
        # Antes os dois andavam juntos, e um clique no calendário passava por
        # declaração de que o trabalho foi ao cliente. A data é editável, pode
        # ser antecipada, corrigida ou lançada por engano; a confirmação é uma
        # afirmação de quem responde pelo projeto.
        atualizado = self.repository.update(
            escopo_id, data_entrega_real=request.data_entrega_real
        )

        if data_antiga != atualizado.data_entrega_real:
            self.alteracao_repository.create(
                projeto_id=atualizado.projeto_id,
                projeto_escopo_id=atualizado.id,
                data_anterior=data_antiga,
                data_nova=atualizado.data_entrega_real,
                justificativa=(request.justificativa or "").strip() or "Primeira marcação",
                alterado_por=getattr(current_user, "id", None),
                # ⚠ Só na ALTERAÇÃO. Na primeira marcação ninguém autorizou
                # nada — ela não passa pelo gate do §13 —, e carimbar o diretor
                # que marcou faria o histórico afirmar que houve uma
                # autorização que nunca foi pedida.
                autorizado_por=(
                    getattr(current_user, "id", None)
                    if eh_diretor_projetos and data_antiga is not None
                    else None
                ),
            )

        # 🤖 §4: com todos os escopos entregues, o projeto passa a Período de
        # ajustes sozinho. Depois da trava, como as notificações — um status
        # avançado por uma entrega que o §5.5 barrou seria mentira.
        #
        # Import local: `avancar_status` lê escopos e bancas, e no topo seria
        # circular. Silencioso: a entrega não pode falhar porque o status não
        # avançou, e o job da madrugada pega o que escapar.
        from src.use_cases.projeto.avancar_status import AvancarStatusAutomaticoUseCase

        try:
            AvancarStatusAutomaticoUseCase(self.db).executar_para(atualizado.projeto_id)
        except Exception:  # noqa: BLE001
            # ⚠ Engolido de propósito, e só aqui: a ENTREGA é o fato: ela não
            # pode ser recusada porque o status derivado dela não pôde avançar.
            # `exception()` deixa o traceback no log — não é silêncio, é
            # não-bloqueio —, e o job da madrugada refaz a conta.
            logger.exception(
                "Entrega gravada, mas o status do projeto %s não avançou",
                atualizado.projeto_id,
            )

        # Depois da trava, nunca antes: notificar uma entrega que o §5.5 acabou
        # de barrar avisaria a diretoria de algo que não aconteceu.
        #
        # ⭐ Dois avisos diferentes para dois fatos diferentes. "O escopo foi
        # entregue" só acontece uma vez; mudar a data DEPOIS é outra notícia, e
        # é a que a diretoria precisa ver (foi ela quem autorizou). Mandar
        # `notificar_entrega` na alteração anunciava uma entrega que já tinha
        # sido anunciada, e a segunda alteração não avisava nada — a dedupe da
        # notificação engolia o repetido.
        projeto = self.projeto_repository.get_by_id(atualizado.projeto_id)
        if projeto:
            nome = _nome_escopo(atualizado, self.catalogo_repository)
            if data_antiga is None:
                notificar_entrega(self.db, projeto, escopo_id, nome)
            elif data_antiga != atualizado.data_entrega_real:
                notificar_entrega_alterada(
                    self.db,
                    projeto,
                    data_antiga,
                    atualizado.data_entrega_real,
                    nome_escopo=nome,
                    escopo_id=escopo_id,
                )

        return {
            "id": atualizado.id,
            "data_entrega_real": atualizado.data_entrega_real,
            # ⚠ Sem `status`: marcar a data não o move mais. Quem responde
            # "entregue" é `POST /escopos-projeto/{id}/confirmar-entrega`.
            "aguardando_confirmacao": atualizado.status != "entregue",
        }

    def _exigir_alteracao_permitida(
        self, data_antiga: Optional[date], request: RegistrarEntregaEscopoRequest, eh_diretor_projetos: bool
    ) -> None:
        """§13: mudar uma entrega JÁ REGISTRADA é decisão da diretoria.

        A primeira marcação passa direto — é o passo do fluxo em que o
        coordenador fecha o escopo no cronograma, e travá-la faria o time
        depender da diretoria para registrar o que já aconteceu.

        O que é gated é a MUDANÇA: a data que o cliente ouviu vira outra. Sem
        isso, um escopo entregue com atraso podia ter a data empurrada em
        silêncio e o atraso desaparecia do monitoramento.
        """
        if data_antiga is None or data_antiga == request.data_entrega_real:
            return
        if not eh_diretor_projetos:
            raise RegraDeNegocioError(
                f"Este escopo já foi entregue em {data_antiga.strftime('%d/%m/%Y')}. "
                "Mudar uma data de entrega já registrada é decisão da diretoria (§13)"
            )
        if not (request.justificativa or "").strip():
            raise RegraDeNegocioError(
                "Mudar a data de entrega exige justificativa — ela vai para o Histórico"
            )


class ClassificarAtrasoEntregaRequest(BaseModel):
    #: interno = atraso do time · externo = agenda do cliente (§7.4)
    tipo_atraso_entrega: str


class ClassificarAtrasoEntregaUseCase:
    """§7.4: a entrega ao cliente pode escorregar por agenda dele. Marcar se o
    atraso foi interno ou externo é o que evita penalizar o time pelo que não
    é dele — e por isso é decisão só da diretoria."""

    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)

    def execute(self, escopo_id: int, request: ClassificarAtrasoEntregaRequest):
        if request.tipo_atraso_entrega not in ("interno", "externo"):
            raise RegraDeNegocioError("O tipo de atraso precisa ser 'interno' ou 'externo'")
        escopo = self.repository.update(
            escopo_id, tipo_atraso_entrega=request.tipo_atraso_entrega
        )
        return {"id": escopo.id, "tipo_atraso_entrega": escopo.tipo_atraso_entrega} if escopo else None


class DeleteEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, escopo_id: int) -> bool:
        if self.banca_repository.get_by_projeto_escopo(escopo_id):
            raise RegraDeNegocioError(
                "Não é possível remover um escopo que já tem banca marcada"
            )
        # As reuniões daquele escopo não somem junto: elas ACONTECERAM, e o
        # §7.2 conta "projeto sem reunião na semana" pela ausência de linha.
        # Elas voltam a ser reuniões gerais do projeto — e, sem a FK pendurada,
        # o delete não esbarra na integridade referencial.
        reuniao_repository = ReuniaoSemanalRepository(self.db)
        for reuniao in reuniao_repository.get_by_escopo(escopo_id):
            reuniao_repository.update(reuniao.id, projeto_escopo_id=None)
        return self.repository.delete(escopo_id)


class ConfirmarEntregaEscopoRequest(BaseModel):
    """O dia da entrega, para quando ele ainda não estiver marcado.

    Opcional de propósito: quem já marcou a data no Cronograma confirma sem
    corpo nenhum.
    """

    data_entrega_real: Optional[date] = None


class ConfirmarEntregaEscopoUseCase:
    """⭐ O ato que move o escopo para **Entregue** (§5.5).

    ⚠ **Por que isto é um passo à parte da data.** Os dois já foram a mesma
    escrita: gravar `data_entrega_real` no cronograma virava o status na mesma
    linha. Só que a data é um campo de calendário — editável, corrigível,
    clicável por engano — e o status na tabela de escopos é lido como uma
    afirmação: *este trabalho foi ao cliente*. Um clique num dia passava por
    declaração.

    Agora a data continua livre (é planejamento e registro), e o status espera
    alguém dizer "sim, entregamos".

    ⭐ **Quem pode confirmar**: o **coordenador daquele projeto** ou a
    **diretoria**. Não é `pode_definir_cronograma`: marcar datas é operação de
    cronograma, confirmar a entrega é responder pelo que foi entregue. Um
    coordenador de OUTRO projeto não confirma este — a checagem é de vínculo,
    não de cargo.

    A trava do §5.5 vale aqui inteira: sem banca aprovada não há confirmação. É
    o mesmo caminho de três degraus de `RegistrarEntregaEscopoUseCase`, e é
    aqui que ele passa a morder de verdade — a data podia ser marcada antes da
    aprovação em bases antigas, mas o status não anda sem ela.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(
        self,
        escopo_id: int,
        current_user,
        eh_diretor_projetos: bool = False,
        request: Optional["ConfirmarEntregaEscopoRequest"] = None,
    ):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None

        if escopo.status == "entregue":
            raise RegraDeNegocioError("A entrega deste escopo já foi confirmada")
        if escopo.status == "cancelado":
            raise RegraDeNegocioError("Este escopo foi cancelado")

        self._exigir_quem_pode(escopo, current_user, eh_diretor_projetos)
        self._exigir_banca_aprovada(escopo_id)

        escopo = self._garantir_data(escopo, request, current_user, eh_diretor_projetos)

        atualizado = self.repository.update(
            escopo_id,
            status="entregue",
            entrega_confirmada_em=datetime.now(),
            entrega_confirmada_por=getattr(current_user, "id", None),
        )

        # 🤖 §4: com todos os escopos entregues, o projeto passa a Período de
        # ajustes. O gatilho agora é a CONFIRMAÇÃO, não a data — é ela que diz
        # que o escopo acabou.
        from src.use_cases.projeto.avancar_status import AvancarStatusAutomaticoUseCase

        try:
            AvancarStatusAutomaticoUseCase(self.db).executar_para(atualizado.projeto_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Entrega confirmada, mas o status do projeto %s não avançou",
                atualizado.projeto_id,
            )

        return {
            "id": atualizado.id,
            "status": atualizado.status,
            "entrega_confirmada_em": atualizado.entrega_confirmada_em,
        }

    def _garantir_data(self, escopo, request, current_user, eh_diretor_projetos: bool):
        """⚠ Confirma-se uma entrega que TEM data — senão o escopo apareceria
        entregue sem dizer quando.

        ⭐ Mas a data pode chegar JUNTO com a confirmação. Exigi-la marcada de
        antes obrigava a ir ao Cronograma, voltar à Visão geral e clicar de
        novo — dois gestos em duas telas para um fato só, e o botão nem
        aparecia enquanto isso. Quando ela já existe, o dia informado é
        ignorado: mudar entrega registrada é do §13, que tem porta própria.
        """
        if escopo.data_entrega_real:
            return escopo

        dia = getattr(request, "data_entrega_real", None)
        if dia is None:
            raise RegraDeNegocioError(
                "Informe o dia da entrega para confirmá-la"
            )

        # Reaproveita a marcação em vez de gravar direto: é ela que escreve o
        # Histórico do projeto e notifica a equipe. Sem isso, uma entrega
        # confirmada por aqui não deixaria rastro nenhum de quando foi marcada.
        RegistrarEntregaEscopoUseCase(self.db).execute(
            escopo.id,
            RegistrarEntregaEscopoRequest(data_entrega_real=dia),
            eh_diretor_projetos=eh_diretor_projetos,
            current_user=current_user,
        )
        return self.repository.get_by_id(escopo.id)

    def _exigir_quem_pode(self, escopo, current_user, eh_diretor_projetos: bool) -> None:
        if eh_diretor_projetos:
            return
        membros = self.membro_repository.get_by_projeto(escopo.projeto_id, apenas_atuais=True)
        usuario_id = getattr(current_user, "id", None)
        eh_coordenador = any(
            m.usuario_id == usuario_id and m.papel == "coordenador" for m in membros
        )
        if not eh_coordenador:
            raise RegraDeNegocioError(
                "Só o coordenador do projeto ou a diretoria confirmam a entrega"
            )

    def _exigir_banca_aprovada(self, escopo_id: int) -> None:
        """🔒 §5.5 — os mesmos degraus da marcação, com mensagem própria em cada.

        Repetidos aqui, e não delegados: esta é a porta que de fato muda o
        estado do escopo, e uma trava que mora só na outra porta é uma trava com
        dois caminhos.
        """
        banca = self.banca_repository.get_by_projeto_escopo(escopo_id)
        if not banca:
            raise RegraDeNegocioError(
                "Este escopo ainda não tem banca marcada — a entrega só é "
                "confirmada depois de a banca aprovar"
            )
        if not banca.realizado_em:
            raise RegraDeNegocioError("A banca deste escopo ainda não foi realizada")
        if banca.resultado is None:
            raise RegraDeNegocioError(
                "A banca deste escopo ainda não tem resultado — a confirmação "
                "libera quando os avaliadores votarem"
            )
        if banca.resultado != "aprovada":
            raise RegraDeNegocioError(
                "A banca deste escopo não foi aprovada — é preciso marcar uma "
                "nova banca antes de confirmar a entrega"
            )

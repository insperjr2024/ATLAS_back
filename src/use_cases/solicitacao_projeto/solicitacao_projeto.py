"""Declaração de interesse: o consultor pede para entrar num projeto.

O fluxo é: o consultor vê os projetos com vaga, escreve por que quer entrar,
e o COORDENADOR daquele projeto aceita ou recusa. Aceitar já inclui a pessoa
na equipe.

Quem PEDE é só quem tem posição `consultor`. Coordenação, gerência e
diretoria entram em projeto por alocação da gestão, não por autoatendimento —
para elas a tela de vagas existe apenas para responder aos pedidos dos
outros. Antes não havia trava nenhuma aqui, e um coordenador conseguia pedir
para entrar como consultor em qualquer projeto.

Quem responde é só quem tem `pode_editar_equipe` (gerência e diretoria),
desde que enxergue o projeto. Não há poder novo aqui: quem já podia montar a
equipe inteira evidentemente pode aceitar um pedido.

O COORDENADOR não decide. Até 2026-08-12 ele aceitava e recusava os pedidos
do projeto dele, e isso saiu por decisão da diretoria: entrar na equipe é
alocação, e alocação é da gestão. O que ele mantém é VISIBILIDADE — quem
pediu para entrar e quem já está no time dos projetos que coordena, sem
botão nenhum (`listar_projetos_coordenados`).

O recorte por frente do gerente vem de `pode_ver_projeto`, o mesmo do resto
do sistema — não é reimplementado aqui.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.solicitacao_projeto_model import SolicitacaoProjetoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.situacao_carga_repository import SituacaoCargaRepository, resolver
from src.repositories.usuario_repository import UsuarioRepository
from src.middlewares.authorization import (
    aplicar_recorte_visao,
    frentes_do_usuario,
    pode_ver_projeto,
    usuario_tem_permissao,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.validacao_equipe import POSICOES_ELEGIVEIS_CONSULTOR, ROTULO_POSICAO
from src.use_cases.notificacao.destinatarios import lideranca_do_projeto
from src.use_cases.notificacao.eventos import notificar_alocacao
from src.use_cases.notificacao.registrar_notificacao import registrar, registrar_varios

#: A única posição que pede para entrar em projeto. As outras são alocadas.
POSICAO_QUE_SOLICITA = "consultor"

#: Status que não aceitam gente nova: o projeto acabou ou está congelado.
STATUS_FECHADOS = {"finalizado", "pausado"}


class CriarSolicitacaoRequest(BaseModel):
    projeto_id: int
    justificativa: str


class ResponderSolicitacaoRequest(BaseModel):
    aprovar: bool
    resposta: Optional[str] = None


class AlocarDiretoRequest(BaseModel):
    projeto_id: int
    usuario_id: int


class SolicitacaoProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.situacao_repository = SituacaoCargaRepository(db)
        self._escala_cache = None

    # ------------------------------------------------------------------ #
    # Leitura                                                             #
    # ------------------------------------------------------------------ #

    def _pendentes_do_usuario(self, usuario_id: int) -> set:
        return {
            s.projeto_id
            for s in self.db.query(SolicitacaoProjetoModel)
            .filter(
                SolicitacaoProjetoModel.usuario_id == usuario_id,
                SolicitacaoProjetoModel.status == "pendente",
            )
            .all()
        }

    def _projetos_do_usuario(self, usuario_id: int) -> set:
        """Onde a pessoa está HOJE — para o "você já está neste projeto"."""
        return {
            m.projeto_id
            for m in self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .all()
        }

    def _carga(self, usuario_id: int) -> int:
        """A carga oficial do §7.3 — projeto finalizado ou arquivado não conta.

        Vem de `contar_ativos_por_usuario`, o mesmo contador que a tela de
        montar equipe usa. Contar aqui na mão daria um número diferente do que
        a diretoria vê no monitoramento, para a mesma pessoa.
        """
        return self.membro_repository.contar_ativos_por_usuario().get(usuario_id, 0)

    def _escala_consultor(self):
        """A escala de carga de consultor, buscada uma vez por requisição.

        `garantir_padrao` toca o banco (e chega a criar as faixas na primeira
        visita). Sem o cache, classificar a carga de uma lista de 40 pedidos
        faria 40 idas ao banco para ler a mesma tabela de 3 linhas.
        """
        if self._escala_cache is None:
            self._escala_cache = self.situacao_repository.garantir_padrao(POSICAO_QUE_SOLICITA)
        return self._escala_cache

    def _situacao_de_carga(self, carga: int) -> Optional[dict]:
        """Como a diretoria classifica ESTA carga hoje, na escala de consultor.

        A carga não bloqueia mais o pedido — vira aviso. Antes havia um teto
        fixo de 3 no código, que recusava o pedido de quem a própria
        configuração considerava tranquilo: a escala de consultor tinha
        "Carga alta" a partir de 7 e o código barrava em 3, sem nada na tela
        explicando a diferença.

        `None` quando a carga fica abaixo do menor mínimo da escala — a
        diretoria pode subir esse piso para deixar os menos carregados sem
        rótulo, e a tela mostra travessão.
        """
        faixa = resolver(self._escala_consultor(), carga)
        if not faixa:
            return None
        return {"nome": faixa.nome, "tom": faixa.tom, "min_projetos": faixa.min_projetos}

    def _coordena_algum(self, usuario_id: int) -> bool:
        return (
            self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.papel == "coordenador",
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .first()
            is not None
        )

    def listar_vagas(self, current_user) -> dict:
        """Os projetos que ainda cabem gente, do ponto de vista de quem olha.

        Devolve TODOS os projetos abertos, marcando cada um com o motivo de
        não poder pedir (`impedimento`), em vez de esconder. Sumir da lista
        sem explicação é o tipo de coisa que gera "por que não aparece o
        projeto X?" — e ninguém sabe responder.

        Leva também as três flags que decidem o que a página mostra:
        `pode_solicitar` (só consultor), `pode_responder` (quem monta equipe)
        e `coordena_projeto` (a visão de leitura do coordenador). Sem elas o
        front teria de reimplementar as regras — e a aba de resposta ficaria
        condicionada a "a lista veio vazia?", que é o motivo de ela nunca ter
        aparecido enquanto ninguém tinha pedido nenhum.
        """
        usuario_id = current_user.id
        pode_solicitar = current_user.posicao == POSICAO_QUE_SOLICITA
        gestao = usuario_tem_permissao(current_user, self.db, "pode_editar_equipe")

        projetos = [
            p
            for p in self.repository.get_all()
            if not p.arquivado_em and p.status not in STATUS_FECHADOS
        ]

        # Para a GESTÃO a lista é operacional — é dela que sai o projeto onde
        # se vai alocar alguém —, então respeita o §3: o gerente só enxerga as
        # frentes dele. Para o consultor a lista é um catálogo de onde pedir
        # para entrar, e aí é global de propósito: ele pode se candidatar a
        # projeto de qualquer frente.
        if gestao:
            visiveis = self._ids_visiveis(current_user)
            projetos = [p for p in projetos if p.id in visiveis]
        vinculos = self.membro_repository.get_by_projetos([p.id for p in projetos], apenas_atuais=True)

        consultores: dict = {}
        coordenadores: dict = {}
        for v in vinculos:
            if v.papel == "consultor":
                consultores.setdefault(v.projeto_id, []).append(v.usuario_id)
            else:
                coordenadores[v.projeto_id] = v.usuario_id

        # As frentes de cada projeto. É o que dá ao candidato a primeira
        # ideia do que o projeto é, antes de abrir.
        frentes_por_projeto = self._frentes_por_projeto([p.id for p in projetos])

        meus = self._projetos_do_usuario(usuario_id)
        pendentes = self._pendentes_do_usuario(usuario_id)
        minha_carga = self._carga(usuario_id)
        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}

        saida = []
        for p in projetos:
            alocados = len(consultores.get(p.id, []))
            vagas = max(0, (p.max_consultores or 0) - alocados)

            # A carga saiu daqui: ela não impede mais nada, só informa. O que
            # sobra são impedimentos de fato — o pedido seria recusado.
            if not pode_solicitar:
                impedimento = "Sua posição entra em projeto por alocação da gestão"
            elif p.id in meus:
                impedimento = "Você já está neste projeto"
            elif p.id in pendentes:
                impedimento = "Você já tem um pedido em análise aqui"
            elif vagas == 0:
                impedimento = "Sem vaga: o projeto já está com o time completo"
            else:
                impedimento = None

            saida.append(
                {
                    "id": p.id,
                    "nome": p.nome,
                    "cliente": p.cliente,
                    "descricao": p.descricao,
                    "status": p.status,
                    "frentes": frentes_por_projeto.get(p.id, []),
                    "coordenador_id": coordenadores.get(p.id),
                    "coordenador_nome": nomes.get(coordenadores.get(p.id)),
                    "consultores": [nomes.get(uid) for uid in consultores.get(p.id, [])],
                    "alocados": alocados,
                    "max_consultores": p.max_consultores,
                    "vagas": vagas,
                    "impedimento": impedimento,
                }
            )

        saida.sort(key=lambda p: (p["impedimento"] is not None, -p["vagas"], p["nome"]))
        return {
            "projetos": saida,
            "minha_carga": minha_carga,
            "situacao": self._situacao_de_carga(minha_carga),
            "pode_solicitar": pode_solicitar,
            "pode_responder": gestao,
            "coordena_projeto": self._coordena_algum(usuario_id),
            "filtra_por_frente": self._vale_filtrar_frente(current_user, gestao),
        }

    def _vale_filtrar_frente(self, current_user, gestao: bool) -> bool:
        """Se a grade da gestão deve oferecer filtro e agrupamento por frente.

        O gerente de UMA frente já recebe a lista recortada nela: o seletor
        teria uma opção só e o agrupamento, um grupo só — dois controles que
        não separam nada. Quem cuida de duas frentes, ou a diretoria, que vê
        todas, continua com os dois.

        Sai do back e não do front porque o dado que decide é o recorte do
        §3, não o que por acaso apareceu na lista: um gerente de duas frentes
        num momento em que só uma tem projeto aberto continua sendo alguém
        que compara frentes.
        """
        if not gestao:
            return False
        if current_user.posicao == "diretor" or usuario_tem_permissao(
            current_user, self.db, "pode_ver_todos_projetos"
        ):
            return True
        return len(frentes_do_usuario(current_user, self.db)) > 1

    def _pode_responder(self, projeto_id: int, current_user) -> bool:
        """Quem monta equipe e enxerga o projeto — gerência e diretoria.

        O coordenador do projeto NÃO entra: ver o topo do módulo.
        """
        return usuario_tem_permissao(
            current_user, self.db, "pode_editar_equipe"
        ) and pode_ver_projeto(projeto_id, current_user, self.db)

    def _ids_visiveis(self, current_user) -> set:
        """Os projetos que esta pessoa enxerga, numa consulta só.

        Usa `aplicar_recorte_visao`, o mesmo §3 do resto do sistema — para o
        gerente isso é "as frentes dele", o que já inclui os sinérgicos, já
        que um projeto com duas frentes casa pela interseção. Chamar
        `pode_ver_projeto` num laço daria o mesmo resultado com uma consulta
        por projeto.
        """
        query = aplicar_recorte_visao(self.db.query(ProjetoModel.id), current_user, self.db)
        return {linha[0] for linha in query.all()}

    def _frentes_por_projeto(self, projeto_ids: List[int]) -> dict:
        """Os nomes das frentes de cada projeto, numa consulta só."""
        nomes_frente = {f.id: f.nome for f in self.frente_repository.get_all()}
        saida: dict = {}
        for v in self.db.query(ProjetoFrenteModel).filter(
            ProjetoFrenteModel.projeto_id.in_(projeto_ids or [0])
        ):
            saida.setdefault(v.projeto_id, []).append(nomes_frente.get(v.frente_id))
        return {pid: sorted(n for n in nomes if n) for pid, nomes in saida.items()}

    def listar_para_decisao(self, current_user) -> List[dict]:
        """Os pedidos que ESTA pessoa pode responder — gerência e diretoria.

        O gerente fica na própria frente porque `pode_ver_projeto` já aplica
        esse recorte. Quem não monta equipe recebe lista vazia, inclusive o
        coordenador: a visão dele é `listar_projetos_coordenados`.

        Cada pedido leva as frentes do projeto porque a tela filtra por
        frente e por projeto — sem isso o front teria de cruzar com outra
        chamada só para montar o seletor.
        """
        if not usuario_tem_permissao(current_user, self.db, "pode_editar_equipe"):
            return []

        meus = list(self._ids_visiveis(current_user))
        if not meus:
            return []

        pedidos = (
            self.db.query(SolicitacaoProjetoModel)
            .filter(SolicitacaoProjetoModel.projeto_id.in_(meus))
            .order_by(SolicitacaoProjetoModel.criado_em.desc())
            .all()
        )
        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}
        projetos = {p.id: p for p in self.repository.get_all()}
        cargas = self.membro_repository.contar_ativos_por_usuario()
        frentes = self._frentes_por_projeto(meus)

        return [
            {
                "id": s.id,
                "projeto_id": s.projeto_id,
                "projeto_nome": projetos[s.projeto_id].nome if s.projeto_id in projetos else "—",
                "frentes": frentes.get(s.projeto_id, []),
                "usuario_id": s.usuario_id,
                "usuario_nome": nomes.get(s.usuario_id),
                "carga_do_solicitante": cargas.get(s.usuario_id, 0),
                # A mesma leitura do painel de alocação: o número sozinho
                # exigiria lembrar de cor onde começa "carga alta", e esse
                # limiar é configurável.
                "situacao_do_solicitante": self._situacao_de_carga(cargas.get(s.usuario_id, 0)),
                "justificativa": s.justificativa,
                "status": s.status,
                "criado_em": s.criado_em,
                "respondido_em": s.respondido_em,
                "respondido_por_nome": nomes.get(s.respondido_por),
                "resposta": s.resposta,
            }
            for s in pedidos
        ]

    def listar_projetos_coordenados(self, current_user) -> List[dict]:
        """Os projetos que a pessoa coordena, só para leitura.

        Responde às duas perguntas que o coordenador tem sobre o time dele:
        quem já está alocado, e quem pediu para entrar. Nenhuma ação sai
        daqui — a decisão é da gestão desde 2026-08-12.
        """
        coordenados = [
            m.projeto_id
            for m in self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == current_user.id,
                ProjetoMembroModel.papel == "coordenador",
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .all()
        ]
        if not coordenados:
            return []

        projetos = {p.id: p for p in self.repository.get_all() if p.id in coordenados}
        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}
        frentes = self._frentes_por_projeto(coordenados)
        cargas = self.membro_repository.contar_ativos_por_usuario()

        vinculos = self.membro_repository.get_by_projetos(coordenados, apenas_atuais=True)
        equipe: dict = {}
        for v in vinculos:
            equipe.setdefault(v.projeto_id, []).append(
                {"usuario_id": v.usuario_id, "nome": nomes.get(v.usuario_id), "papel": v.papel}
            )

        pedidos_por_projeto: dict = {}
        for s in (
            self.db.query(SolicitacaoProjetoModel)
            .filter(SolicitacaoProjetoModel.projeto_id.in_(coordenados))
            .order_by(SolicitacaoProjetoModel.criado_em.desc())
            .all()
        ):
            pedidos_por_projeto.setdefault(s.projeto_id, []).append(
                {
                    "id": s.id,
                    "usuario_nome": nomes.get(s.usuario_id),
                    "carga_do_solicitante": cargas.get(s.usuario_id, 0),
                    "justificativa": s.justificativa,
                    "status": s.status,
                    "criado_em": s.criado_em,
                    "respondido_por_nome": nomes.get(s.respondido_por),
                }
            )

        saida = []
        for projeto_id in coordenados:
            projeto = projetos.get(projeto_id)
            if not projeto:
                continue
            do_projeto = equipe.get(projeto_id, [])
            alocados = sum(1 for m in do_projeto if m["papel"] == "consultor")
            saida.append(
                {
                    "id": projeto.id,
                    "nome": projeto.nome,
                    "cliente": projeto.cliente,
                    "status": projeto.status,
                    "frentes": frentes.get(projeto_id, []),
                    "equipe": sorted(do_projeto, key=lambda m: (m["papel"] != "coordenador", m["nome"] or "")),
                    "alocados": alocados,
                    "max_consultores": projeto.max_consultores,
                    "vagas": max(0, (projeto.max_consultores or 0) - alocados),
                    "pedidos": pedidos_por_projeto.get(projeto_id, []),
                }
            )
        saida.sort(key=lambda p: p["nome"])
        return saida

    # ------------------------------------------------------------------ #
    # Escrita                                                             #
    # ------------------------------------------------------------------ #

    def criar(self, usuario_id: int, request: CriarSolicitacaoRequest) -> dict:
        if not request.justificativa.strip():
            raise RegraDeNegocioError("Escreva por que você quer entrar neste projeto.")

        # Antes da checagem do projeto: quem não pode pedir não pode pedir em
        # projeto nenhum, e "projeto não encontrado" seria a resposta errada.
        usuario = self.usuario_repository.get_by_id(usuario_id)
        if not usuario or usuario.posicao != POSICAO_QUE_SOLICITA:
            raise RegraDeNegocioError(
                "Só consultores pedem para entrar em projeto. Coordenação, gerência e "
                "diretoria são alocadas pela gestão."
            )

        projeto = self.repository.get_by_id(request.projeto_id)
        if not projeto:
            raise RegraDeNegocioError("Projeto não encontrado")
        if projeto.arquivado_em or projeto.status in STATUS_FECHADOS:
            raise RegraDeNegocioError("Este projeto não está aceitando gente nova.")

        vinculos = self.membro_repository.get_by_projeto(projeto.id, apenas_atuais=True)
        if any(v.usuario_id == usuario_id for v in vinculos):
            raise RegraDeNegocioError("Você já faz parte deste projeto.")

        alocados = sum(1 for v in vinculos if v.papel == "consultor")
        if alocados >= (projeto.max_consultores or 0):
            raise RegraDeNegocioError("Este projeto já está com o time completo.")

        if request.projeto_id in self._pendentes_do_usuario(usuario_id):
            raise RegraDeNegocioError("Você já tem um pedido em análise para este projeto.")

        # A carga NÃO barra o pedido: a escala de `situacao_carga` é
        # recomendação da diretoria, não teto. Quem está carregado pede do
        # mesmo jeito, com o aviso na tela, e quem responde vê a carga no
        # pedido (`carga_do_solicitante`) para decidir.

        solicitacao = SolicitacaoProjetoModel(
            projeto_id=request.projeto_id,
            usuario_id=usuario_id,
            justificativa=request.justificativa.strip(),
            status="pendente",
            criado_em=datetime.now(),
        )
        self.db.add(solicitacao)
        self.db.commit()
        self.db.refresh(solicitacao)

        # O aviso vai para quem DECIDE — gerência da frente e diretoria. Ia
        # para o coordenador do projeto, que desde 2026-08-12 não responde
        # mais: era mandar para o sino de quem não pode fazer nada com aquilo.
        #
        # `registrar_varios` direto, e não `notificar`: aquele helper é dos
        # eventos de banca e só sabe carregar `banca_id`.
        decisores = lideranca_do_projeto(self.db, projeto.id)
        registrar_varios(
            self.db,
            decisores,
            tipo="solicitacao_projeto",
            titulo=f"{usuario.nome} quer entrar no projeto {projeto.nome}.",
            corpo=solicitacao.justificativa,
            projeto_id=projeto.id,
            # A rota é a página de vagas. Apontava para
            # `/projetos/solicitacoes`, que não existe no roteador do front e
            # não tem catch-all: quem clicava caía numa tela em branco.
            rota="/vagas",
            chave_dedup=f"solicitacao_projeto:{solicitacao.id}",
        )

        # O coordenador continua sabendo quem quer entrar no time dele, com
        # texto que não promete ação nenhuma. Fica de fora quando já recebeu
        # como decisor (gerente ocupando a cadeira de coordenador), senão o
        # mesmo pedido chegaria duas vezes com dois textos diferentes.
        coordenador = next((v for v in vinculos if v.papel == "coordenador"), None)
        if coordenador and coordenador.usuario_id not in decisores:
            registrar(
                self.db,
                usuario_id=coordenador.usuario_id,
                tipo="solicitacao_projeto",
                titulo=(
                    f"{usuario.nome} pediu para entrar no {projeto.nome}, que você coordena. "
                    "A gestão decide."
                ),
                corpo=solicitacao.justificativa,
                projeto_id=projeto.id,
                rota="/vagas",
                chave_dedup=f"solicitacao_projeto_coordenador:{solicitacao.id}",
            )

        return {"id": solicitacao.id, "status": solicitacao.status}

    def responder(self, solicitacao_id: int, current_user, request: ResponderSolicitacaoRequest) -> dict:
        solicitacao = self.db.get(SolicitacaoProjetoModel, solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Pedido não encontrado")
        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Este pedido já foi respondido.")

        if not self._pode_responder(solicitacao.projeto_id, current_user):
            raise RegraDeNegocioError(
                "Só a gerência da frente ou a diretoria respondem a este pedido."
            )
        vinculos = self.membro_repository.get_by_projeto(solicitacao.projeto_id, apenas_atuais=True)

        if request.aprovar:
            # ⚠ Rechecar aqui, e não só na criação: entre pedir e responder,
            # a gerência pode ter preenchido o time por outro caminho.
            projeto = self.repository.get_by_id(solicitacao.projeto_id)
            alocados = sum(1 for v in vinculos if v.papel == "consultor")
            if alocados >= (projeto.max_consultores or 0):
                raise RegraDeNegocioError(
                    "O time encheu depois que o pedido foi feito. "
                    "Aumente o limite de consultores do projeto ou recuse."
                )
            if any(v.usuario_id == solicitacao.usuario_id for v in vinculos):
                raise RegraDeNegocioError("Esta pessoa já entrou no projeto por outro caminho.")

            self.membro_repository.create(
                projeto_id=solicitacao.projeto_id,
                usuario_id=solicitacao.usuario_id,
                papel="consultor",
                entrou_em=datetime.now(),
            )

        solicitacao.status = "aprovada" if request.aprovar else "recusada"
        solicitacao.respondido_por = current_user.id
        solicitacao.respondido_em = datetime.now()
        solicitacao.resposta = (request.resposta or "").strip() or None
        self.db.commit()

        projeto = self.repository.get_by_id(solicitacao.projeto_id)
        aviso = (
            f"Seu pedido para entrar no projeto {projeto.nome} foi aceito. Bem-vindo(a)!"
            if request.aprovar
            else f"Seu pedido para entrar no projeto {projeto.nome} não foi aceito."
        )
        if solicitacao.resposta:
            aviso += f" Motivo: {solicitacao.resposta}"
        registrar(
            self.db,
            usuario_id=solicitacao.usuario_id,
            tipo="solicitacao_projeto",
            titulo=aviso,
            projeto_id=solicitacao.projeto_id,
            chave_dedup=f"resposta_solicitacao_projeto:{solicitacao.id}",
        )

        return {"id": solicitacao.id, "status": solicitacao.status}

    def _projetos_ativos(self) -> dict:
        """Em quais projetos cada pessoa está hoje — TODOS, sem recorte.

        ⚠ **Abre o §3 de propósito, por decisão da diretoria (2026-08-13).**
        `contar_ativos_por_usuario` dizia que a carga atravessa frentes mas
        que vai "só o número, nunca o nome dos projetos". No painel de
        alocação isso passou a valer também para os nomes: quem aloca clica na
        carga e vê onde a pessoa está, mesmo em frente que não acompanha.

        O motivo prático: a alternativa era mostrar "e mais 1 em frente que
        você não acompanha", e um resto anônimo não ajuda a decidir — quem
        monta time precisa saber se aquele quarto projeto é pesado ou não.

        Mesma régua de carga do §7.3: finalizado ou arquivado não conta, para
        o número e a lista nunca discordarem.
        """
        linhas = (
            self.db.query(ProjetoMembroModel.usuario_id, ProjetoModel.id, ProjetoModel.nome)
            .join(ProjetoModel, ProjetoModel.id == ProjetoMembroModel.projeto_id)
            .filter(
                ProjetoMembroModel.saiu_em.is_(None),
                ProjetoModel.arquivado_em.is_(None),
                ProjetoModel.status != "finalizado",
            )
            .all()
        )

        saida: dict = {}
        for usuario_id, projeto_id, nome in linhas:
            saida.setdefault(usuario_id, []).append({"id": projeto_id, "nome": nome})
        for lista in saida.values():
            lista.sort(key=lambda p: p["nome"])
        return saida

    def listar_candidatos(self, current_user, projeto_id: int) -> List[dict]:
        """Quem a gestão pode colocar NESTE projeto, do menos carregado ao mais.

        A ordem por carga crescente é a mesma do `AlocarPessoasModal` das
        bancas: a decisão que se quer favorecer é distribuir, e ordenar por
        nome faria a pessoa varrer a lista inteira para descobrir quem está
        livre.

        Cada candidato leva a carga em número E a situação da escala da
        diretoria (`situacao_carga`). Só o número obrigaria quem aloca a
        lembrar de cor onde começa "carga alta" — e esse limiar é
        configurável, então nem sempre é o mesmo.

        As frentes vêm junto porque a tela agrupa e filtra por elas: um
        gerente montando time normalmente quer gente da própria frente, mas
        nada impede o contrário, então é filtro e não recorte.
        """
        if not self._pode_responder(projeto_id, current_user):
            raise RegraDeNegocioError(
                "Só a gerência da frente ou a diretoria alocam alguém num projeto."
            )

        ja_no_projeto = {
            v.usuario_id
            for v in self.membro_repository.get_by_projeto(projeto_id, apenas_atuais=True)
        }
        pediram = {
            s.usuario_id
            for s in self.db.query(SolicitacaoProjetoModel).filter(
                SolicitacaoProjetoModel.projeto_id == projeto_id,
                SolicitacaoProjetoModel.status == "pendente",
            )
        }

        nomes_frente = {f.id: f.nome for f in self.frente_repository.get_all()}
        frentes_por_usuario: dict = {}
        for v in self.db.query(UsuarioFrenteModel):
            frentes_por_usuario.setdefault(v.usuario_id, []).append(nomes_frente.get(v.frente_id))

        cargas = self.membro_repository.contar_ativos_por_usuario()
        projetos_por_usuario = self._projetos_ativos()

        candidatos = []
        for usuario in self.usuario_repository.get_all():
            if usuario.status != "ativo" or not usuario.ativo:
                continue
            if usuario.posicao not in POSICOES_ELEGIVEIS_CONSULTOR:
                continue
            if usuario.id in ja_no_projeto:
                continue

            carga = cargas.get(usuario.id, 0)
            candidatos.append(
                {
                    "usuario_id": usuario.id,
                    "nome": usuario.nome,
                    "posicao": usuario.posicao,
                    "frentes": sorted(n for n in frentes_por_usuario.get(usuario.id, []) if n),
                    "carga": carga,
                    "situacao": self._situacao_de_carga(carga),
                    # Todos, sem recorte de frente — ver `_projetos_ativos`.
                    "projetos": projetos_por_usuario.get(usuario.id, []),
                    "pediu_para_entrar": usuario.id in pediram,
                }
            )

        candidatos.sort(key=lambda c: (c["carga"], c["nome"] or ""))
        return candidatos

    def alocar_direto(self, current_user, request: AlocarDiretoRequest) -> dict:
        """A gestão coloca alguém no projeto sem que essa pessoa tenha pedido.

        Existe porque nem toda alocação nasce de um pedido: montar time é
        trabalho da gestão, e obrigá-la a esperar uma declaração de interesse
        para preencher uma vaga inverteria quem manda no processo. É o mesmo
        efeito de editar a equipe pela página do projeto — está aqui para não
        obrigar a sair da tela de solicitações no meio da decisão.

        As checagens são as mesmas de aprovar um pedido, e de propósito:
        os dois caminhos terminam na mesma linha de `projeto_membro`, então
        divergir aqui criaria equipe que um caminho aceita e o outro recusa.
        """
        if not self._pode_responder(request.projeto_id, current_user):
            raise RegraDeNegocioError(
                "Só a gerência da frente ou a diretoria alocam alguém num projeto."
            )

        projeto = self.repository.get_by_id(request.projeto_id)
        if not projeto:
            raise RegraDeNegocioError("Projeto não encontrado")
        if projeto.arquivado_em or projeto.status in STATUS_FECHADOS:
            raise RegraDeNegocioError("Este projeto não está aceitando gente nova.")

        usuario = self.usuario_repository.get_by_id(request.usuario_id)
        if not usuario:
            raise RegraDeNegocioError("Usuário não encontrado")
        if usuario.posicao not in POSICOES_ELEGIVEIS_CONSULTOR:
            raise RegraDeNegocioError(
                f"{usuario.nome} é {ROTULO_POSICAO.get(usuario.posicao, usuario.posicao)} "
                "e não pode entrar como consultor do projeto."
            )

        vinculos = self.membro_repository.get_by_projeto(request.projeto_id, apenas_atuais=True)
        if any(v.usuario_id == usuario.id for v in vinculos):
            raise RegraDeNegocioError(f"{usuario.nome} já faz parte deste projeto.")

        alocados = sum(1 for v in vinculos if v.papel == "consultor")
        if alocados >= (projeto.max_consultores or 0):
            raise RegraDeNegocioError(
                "O time já está completo. Aumente o limite de consultores do projeto antes."
            )

        self.membro_repository.create(
            projeto_id=projeto.id,
            usuario_id=usuario.id,
            papel="consultor",
            entrou_em=datetime.now(),
        )

        # Se a pessoa tinha pedido para entrar AQUI, o pedido morre resolvido
        # em vez de ficar pendente para sempre — quem fosse responder depois
        # esbarraria em "esta pessoa já entrou por outro caminho".
        pendente = (
            self.db.query(SolicitacaoProjetoModel)
            .filter(
                SolicitacaoProjetoModel.projeto_id == projeto.id,
                SolicitacaoProjetoModel.usuario_id == usuario.id,
                SolicitacaoProjetoModel.status == "pendente",
            )
            .first()
        )
        if pendente:
            pendente.status = "aprovada"
            pendente.respondido_por = current_user.id
            pendente.respondido_em = datetime.now()
            pendente.resposta = "Alocado diretamente pela gestão."

        self.db.commit()
        notificar_alocacao(self.db, projeto, usuario.id)
        return {"projeto_id": projeto.id, "usuario_id": usuario.id, "papel": "consultor"}

    def cancelar(self, solicitacao_id: int, usuario_id: int) -> dict:
        """O próprio solicitante desiste. Só enquanto está pendente."""
        solicitacao = self.db.get(SolicitacaoProjetoModel, solicitacao_id)
        if not solicitacao or solicitacao.usuario_id != usuario_id:
            raise RegraDeNegocioError("Pedido não encontrado")
        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Este pedido já foi respondido.")
        self.db.delete(solicitacao)
        self.db.commit()
        return {"ok": True}

    def listar_meus(self, usuario_id: int) -> List[dict]:
        pedidos = (
            self.db.query(SolicitacaoProjetoModel)
            .filter(SolicitacaoProjetoModel.usuario_id == usuario_id)
            .order_by(SolicitacaoProjetoModel.criado_em.desc())
            .all()
        )
        projetos = {p.id: p for p in self.repository.get_all()}
        return [
            {
                "id": s.id,
                "projeto_id": s.projeto_id,
                "projeto_nome": projetos[s.projeto_id].nome if s.projeto_id in projetos else "—",
                "status": s.status,
                "justificativa": s.justificativa,
                "resposta": s.resposta,
                "criado_em": s.criado_em,
                "respondido_em": s.respondido_em,
            }
            for s in pedidos
        ]

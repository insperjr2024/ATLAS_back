"""⭐ A ficha de uma banca com os NOMES já resolvidos.

Existe separado do `GetBancaUseCase` porque responde outra pergunta. Aquele
devolve a banca como o módulo de bancas precisa dela — ids crus, vagas, piso,
`equipe_ids` — e quem consome monta os nomes cruzando `/usuarios`,
`/frentes`, `/candidaturas`, `/equipes-projeto` e `/bancas-frentes` do lado do
cliente. É o que a tela `/bancas` faz, e para ela faz sentido: ela já carregou
todas essas listas para desenhar os cards.

O cronograma do projeto não carregou nenhuma delas, e não deveria: puxar cinco
listagens inteiras da empresa para escrever sete linhas de uma banca é caro e
frágil. Aqui a composição acontece onde os dados já estão.

⭐ **`membros` sai de `membros_da_banca`, não de `equipe_projeto`.** Aquela
tabela é a legada do módulo de bancas, preenchida à mão; banca marcada pelo
cronograma não escreve nela. Quem lê só ela mostra "Membros —" justamente nas
bancas nascidas do fluxo novo, que são a maioria hoje. `membros_da_banca` já
sabe olhar os dois lados (ver `utils/equipe_banca.py`).
"""

from types import SimpleNamespace

from sqlalchemy.orm import Session

from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.repositories.pergunta_repository import PerguntaRepository
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.banca.aprovar_banca import montar_situacao_aprovacao, sessao_corrente
from src.utils.banca_nota import calcular_nota_final
from src.utils.banca_status import calcular_status_banca
from src.utils.composicao_banca import (
    ComposicaoBancaChecker,
    LIDERANCA_SEM_FRENTE_POSICOES,
    eh_lideranca,
)
from src.utils.equipe_banca import membros_da_banca


class GetBancaDetalhesUseCase:
    def __init__(self, db: Session):
        #: Guardada para `_composicao`, que instancia o checker e o resolver
        #: da matriz de composição (ambos precisam de sessão).
        self.db = db
        self.repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.usuario_frente_repository = UsuarioFrenteRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.avaliacao_repository = AvaliacaoRepository(db)
        self.nota_repository = AvaliacaoNotaRepository(db)
        self.pergunta_repository = PerguntaRepository(db)

    def execute(self, banca_id: int):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None

        escopos = [
            e
            for e in (
                self.escopo_repository.get_by_id(i)
                for i in self.banca_escopo_repository.get_escopo_ids(banca_id)
            )
            if e
        ]

        # O coordenador aparece na própria linha da ficha, então sai da lista
        # de membros — repetir o mesmo nome nas duas diria menos, não mais.
        equipe = membros_da_banca(
            banca,
            self.banca_escopo_repository,
            self.escopo_repository,
            self.membro_repository,
            self.equipe_projeto_repository,
        )
        equipe.discard(banca.coordenador_id)

        # A MESMA sessão da nota final, senão os dois números do cabeçalho
        # falam de tentativas diferentes.
        numero_sessao = sessao_corrente(self.db, banca_id)
        aprovacao = montar_situacao_aprovacao(self.db, banca)

        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "data_hora": banca.data_hora,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em, cancelada_em=getattr(banca, "cancelada_em", None)),
            # Plural: uma banca pode cobrir vários escopos do projeto de uma
            # sentada (ver `BancaEscopoModel`). Vazio nas bancas legadas, que
            # não têm linha em `banca_escopo`.
            "escopos": [self._nome_do_escopo(e) for e in escopos],
            "frentes": self._nomes_das_frentes(banca_id),
            # ⭐ As mesmas frentes com id: a ficha agrupa os avaliadores por
            # frente da banca (liderança/membro de cada uma), e para isso
            # precisa casar o vínculo de cada pessoa, não só o nome.
            "frentes_da_banca": self._frentes_da_banca(banca_id),
            # ⭐ O que a combinação de frentes exige e o que a banca tem hoje
            # (mín./máx. de membro e de liderança por frente). É o que deixa a
            # ficha dizer "Membros · Business 2/3" e marcar frente lotada.
            "composicao": self._composicao(banca, banca_id),
            "coordenador": self._nome(banca.coordenador_id),
            # ⚠ O id junto do nome: a tela decide se mostra o formulário do
            # relato comparando com o usuário logado, e comparar por NOME
            # quebra em qualquer homônimo — além de esconder o formulário de
            # quem tem direito se o cadastro grafar o nome diferente.
            "coordenador_id": banca.coordenador_id,
            "membros": sorted(self._nome(i) for i in equipe),
            # ⭐ Objetos, não nomes soltos: a aba precisa saber QUEM é cada um
            # para responder "sou eu?" e "já enviou?" sem cruzar listas do
            # lado do cliente.
            "avaliadores": self._avaliadores(banca_id),
            "descricao_coordenador": banca.descricao_coordenador,
            # ⭐ Cada TENTATIVA (§9) — é o que responde "por que este escopo
            # teve duas bancas?".
            "sessoes": self._sessoes(banca_id),
            # ⭐ As notas e o feedback de quem avaliou — pedagógico, não decide
            # a banca (ver `aprovacao` abaixo).
            "avaliacoes": self._avaliacoes(banca_id),
            # ⭐ Quem aprova a banca é diretoria de projetos ou gerente da
            # frente, não os avaliadores (§5.5, §8) — ver
            # `use_cases/banca/aprovar_banca.py`.
            "aprovacao": aprovacao,
            "nota_final": self._nota_final(banca_id, numero_sessao),
            # Para a tela poder linkar de volta ao projeto — a ficha é aberta
            # de dentro dele, mas a banca pode cobrir escopo de outro lugar.
            "projeto_id": escopos[0].projeto_id if escopos else None,
        }

    def _avaliadores(self, banca_id: int) -> list:
        """Quem foi escalado, se compareceu e se já enviou a avaliação NESTA sessão.

        ⭐ O estado de cada pessoa numa linha só. Sem isto a tela não consegue
        oferecer "avaliar" a quem tem direito: ela receberia uma lista de
        nomes e não teria como saber qual deles é o usuário logado, nem se ele
        já enviou.

        A avaliação vem da sessão CORRENTE: numa 2ª banca, a avaliação que a
        pessoa deu na primeira não a impede de avaliar de novo — é outra
        tentativa.
        """
        numero = sessao_corrente(self.db, banca_id)

        # Rascunho entra aqui de propósito, ao contrário de `_avaliacoes`: a
        # tela precisa reaproveitar o rascunho da própria pessoa em vez de
        # criar um segundo — dois rascunhos do mesmo avaliador viram duas
        # linhas duplicadas.
        por_avaliador = {
            a.avaliador_id: a
            for a in self.avaliacao_repository.get_by_banca(banca_id, sessao=numero)
        }

        usuarios_por_id = self._usuarios_por_id()
        linhas = []
        for c in self.candidatura_repository.get_by_banca(banca_id):
            minha = por_avaliador.get(c.usuario_id)
            usuario = usuarios_por_id.get(c.usuario_id)
            posicao = usuario.posicao if usuario else "consultor"
            linhas.append(
                {
                    "usuario_id": c.usuario_id,
                    "nome": self._nome(c.usuario_id),
                    # Marcado ao registrar a realização: quem de fato esteve lá.
                    "presente": bool(c.confirmado),
                    # ⭐ Para a ficha agrupar por (liderança/membro) x frente.
                    # `eh_lideranca` é a categoria grosseira da EXIBIÇÃO (todo
                    # coordenador conta); a contagem em `composicao` é mais
                    # fina. `frente_ids` são os vínculos da pessoa, que a tela
                    # cruza com `frentes_da_banca`.
                    "posicao": posicao,
                    "eh_lideranca": eh_lideranca(posicao),
                    # Coordenador de vendas puro — só para o "· vendas" no
                    # nome. Quem decide o BLOCO ("outras frentes") é o campo
                    # de baixo, mais largo.
                    "coordenador_vendas": bool(
                        usuario and getattr(usuario, "coordenador_vendas", False)
                    ),
                    # ⭐ Liderança SEM frente (2026-09-04): coordenador de
                    # vendas OU diretoria (qualquer uma — projetos, pessoas,
                    # geral). Nenhum dos dois fecha o piso de liderança de
                    # frente nenhuma (ver `composicao_banca`); a ficha os joga
                    # no bloco "outras frentes" mesmo vinculados a uma frente
                    # da banca.
                    "lideranca_sem_frente": bool(
                        usuario
                        and (
                            getattr(usuario, "coordenador_vendas", False)
                            or posicao in LIDERANCA_SEM_FRENTE_POSICOES
                        )
                    ),
                    "frente_ids": self._frentes_do_usuario(c.usuario_id),
                    "avaliacao_id": minha.id if minha else None,
                    "ja_enviou": bool(minha and minha.status == "submetida"),
                    "comentario_feedback": minha.comentario_feedback if minha else None,
                }
            )
        return sorted(linhas, key=lambda l: l["nome"])

    def _sessoes(self, banca_id: int) -> list:
        """As tentativas, da primeira à atual."""
        return [
            {
                "id": s.id,
                "numero": s.numero,
                "data_hora": s.data_hora,
                "realizado_em": s.realizado_em,
                "resultado": s.resultado,
                "encerrada_em": s.encerrada_em,
            }
            for s in self.sessao_repository.get_by_banca(banca_id)
        ]

    def _avaliacoes(self, banca_id: int) -> list:
        """Uma linha por avaliação SUBMETIDA: quem, de qual sessão, notas e texto.

        ⚠ Rascunho fica de fora de propósito. É o formulário aberto e não
        enviado — mostrá-lo exporia notas que a pessoa ainda não decidiu
        tornar públicas.
        """
        # As notas por critério, agrupadas pela avaliação que as recebeu. Uma
        # consulta só para a banca inteira — buscar por avaliação seria um N+1
        # numa banca com cinco avaliadores e dez critérios.
        notas_por_avaliacao: dict = {}
        for n in self.nota_repository.get_by_banca(banca_id):
            notas_por_avaliacao.setdefault(n.avaliacao_id, []).append(n)
        perguntas = {p.id: p for p in self.pergunta_repository.get_all()}

        def detalhar_notas(avaliacao_id: int) -> list:
            linhas = []
            for n in notas_por_avaliacao.get(avaliacao_id, []):
                pergunta = perguntas.get(n.pergunta_id)
                linhas.append(
                    {
                        "pergunta": pergunta.texto if pergunta else f"critério {n.pergunta_id}",
                        "ordem": pergunta.ordem if pergunta else 0,
                        # Uma das duas: critério de nota traz `nota`, pergunta
                        # dissertativa traz `resposta_texto`.
                        "nota": float(n.nota) if n.nota is not None else None,
                        "resposta_texto": n.resposta_texto,
                    }
                )
            return sorted(linhas, key=lambda l: l["ordem"])

        return [
            {
                "id": a.id,
                "avaliador": self._nome(a.avaliador_id),
                "avaliador_id": a.avaliador_id,
                "sessao": getattr(a, "sessao", 1) or 1,
                "comentario_feedback": a.comentario_feedback,
                "submetida_em": a.submetida_em,
                # ⭐ O que a pessoa respondeu, critério a critério.
                "notas": detalhar_notas(a.id),
            }
            for a in sorted(
                (
                    a
                    for a in self.avaliacao_repository.get_by_banca(banca_id)
                    if a.status == "submetida"
                ),
                key=lambda a: (getattr(a, "sessao", 1) or 1, a.id),
            )
        ]

    def _nota_final(self, banca_id: int, sessao: int):
        """A média das notas por critério — outra dimensão que a aprovação.

        A nota diz quão bem o trabalho foi feito; a aprovação responde se ele
        pode ir ao cliente. Dá para ir bem na nota e reprovar por um ponto
        isolado.

        ⚠ **Só as notas DESTA tentativa.** Somar as duas misturava a banca que
        reprovou com a que aprovou e produzia uma média que não descreve
        nenhuma das duas — um escopo refeito e aprovado com 4,5 aparecia com
        3,4 por causa das notas que motivaram a reprovação.
        """
        avaliacoes_da_sessao = {
            a.id
            for a in self.avaliacao_repository.get_by_banca(banca_id, sessao=sessao)
        }
        notas = [
            n
            for n in self.nota_repository.get_by_banca(banca_id)
            if n.avaliacao_id in avaliacoes_da_sessao
        ]
        nota = calcular_nota_final(notas)
        return float(nota) if nota is not None else None

    def _usuarios_por_id(self) -> dict:
        """A tabela inteira, uma vez por ficha (2026-09-04 — a query que
        faltava pro `/bancas/{id}/detalhes` de 12 avaliadores parar de levar
        ~17s).

        ⚠ `_nome`, `_avaliadores` e `_avaliacoes` juntos chamavam isto uma vez
        POR REFERÊNCIA a um usuário — coordenador, cada membro, cada
        avaliador, cada nome de avaliação — sem cache nenhum: 20+ queries
        redondas pro banco remoto onde uma só bastava. `ListBancasDoProjetoUseCase`
        reaproveita a MESMA instância desta classe pra todas as bancas do
        projeto, então o cache também vale entre bancas — melhor ainda.
        """
        cache = getattr(self, "_cache_usuarios", None)
        if cache is None:
            cache = {u.id: u for u in self.usuario_repository.get_all()}
            self._cache_usuarios = cache
        return cache

    def _frentes_por_usuario(self) -> dict:
        """usuario_id → [frente_id, ...], a tabela de vínculos inteira numa
        query só — `_frentes_do_usuario` chamava `get_by_usuario` um por
        avaliador (mesmo motivo de `_usuarios_por_id` acima)."""
        cache = getattr(self, "_cache_frentes_por_usuario", None)
        if cache is None:
            cache = {}
            for v in self.usuario_frente_repository.get_all():
                cache.setdefault(v.usuario_id, []).append(v.frente_id)
            self._cache_frentes_por_usuario = cache
        return cache

    def _nome(self, usuario_id) -> str:
        if not usuario_id:
            return "—"
        usuario = self._usuarios_por_id().get(usuario_id)
        return usuario.nome if usuario else "—"

    def _nome_do_escopo(self, escopo) -> str:
        """O nome digitado quando é um "Outro", senão o do catálogo."""
        if escopo.nome_customizado:
            return escopo.nome_customizado
        do_catalogo = (
            self.catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
        )
        return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"

    def _nomes_das_frentes(self, banca_id: int) -> list:
        return sorted(f["nome"] for f in self._frentes_da_banca(banca_id))

    def _frentes_da_banca(self, banca_id: int) -> list:
        # Memoizado por banca_id: `execute()` chama isto direto (campo
        # `frentes_da_banca`) E via `_nomes_das_frentes` E via `_composicao` —
        # três vezes a mesma consulta, sem isto.
        cache = getattr(self, "_cache_frentes_da_banca", None)
        if cache is None:
            cache = {}
            self._cache_frentes_da_banca = cache
        if banca_id not in cache:
            frentes = []
            for vinculo in self.banca_frente_repository.get_by_banca(banca_id):
                frente = self.frente_repository.get_by_id(vinculo.frente_id)
                if frente:
                    frentes.append({"id": frente.id, "nome": frente.nome})
            cache[banca_id] = sorted(frentes, key=lambda f: f["nome"])
        return cache[banca_id]

    def _frentes_do_usuario(self, usuario_id: int) -> list:
        return sorted(self._frentes_por_usuario().get(usuario_id, []))

    def _composicao(self, banca, banca_id: int) -> list:
        """Mín./máx. de membro e liderança por frente da combinação, ao lado do
        que a banca tem — a mesma conta de `GET /bancas`, reaproveitada.
        """
        from src.use_cases.banca.get_banca import composicao_da_banca
        from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase

        frentes = [
            SimpleNamespace(id=f["id"], nome=f["nome"])
            for f in self._frentes_da_banca(banca_id)
        ]
        candidatos = [
            c.usuario_id for c in self.candidatura_repository.get_by_banca(banca_id)
        ]
        return composicao_da_banca(
            banca,
            frentes,
            candidatos,
            ComposicaoBancaChecker(self.db),
            ResolverComposicaoUseCase(self.db),
        )


class ListBancasDoProjetoUseCase:
    """⭐ Todas as bancas de um projeto, com a ficha completa de cada uma.

    É o que alimenta a aba **Banca** do projeto. Existe como rota própria, e
    não como N chamadas a `/bancas/{id}/detalhes`, por dois motivos:

    1. Um projeto sinérgico tem uma banca por escopo (às vezes uma para dois);
       a tela precisa das duas juntas para ordenar e comparar.
    2. Quem abre a aba não sabe os ids das bancas — teria de buscar os escopos
       primeiro só para descobrir o que pedir.

    Reusa `GetBancaDetalhesUseCase` inteiro: a ficha é a mesma, e ter duas
    versões dela seria garantir que uma ficasse para trás.
    """

    def __init__(self, db: Session):
        self.db = db
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.ficha = GetBancaDetalhesUseCase(db)

    def execute(self, projeto_id: int) -> list:
        escopos = self.escopo_repository.get_by_projeto(projeto_id)
        # Uma banca pode cobrir mais de um escopo: sem o dedup, ela apareceria
        # duas vezes na aba, com a mesma ficha.
        vistas: dict = {}
        for escopo in sorted(escopos, key=lambda e: (e.ordem, e.id)):
            banca = self.banca_repository.get_by_projeto_escopo(escopo.id)
            if banca and banca.id not in vistas:
                vistas[banca.id] = self.ficha.execute(banca.id)
        return [f for f in vistas.values() if f]

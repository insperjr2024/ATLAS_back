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

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
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
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.apuracao_banca import apurar, eleitorado, votos_por_avaliador
from src.utils.banca_nota import calcular_nota_final
from src.utils.banca_status import calcular_status_banca
from src.utils.equipe_banca import membros_da_banca


class GetBancaDetalhesUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.vendedor_repository = ProjetoVendedorRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.usuario_repository = UsuarioRepository(db)
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
            self.vendedor_repository,
        )
        equipe.discard(banca.coordenador_id)

        # Calculada antes: a nota final precisa da MESMA sessão que a apuração,
        # senão os dois números do cabeçalho falam de tentativas diferentes.
        apuracao = self._apuracao(banca, banca_id)

        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "data_hora": banca.data_hora,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            # Plural: uma banca pode cobrir vários escopos do projeto de uma
            # sentada (ver `BancaEscopoModel`). Vazio nas bancas legadas, que
            # não têm linha em `banca_escopo`.
            "escopos": [self._nome_do_escopo(e) for e in escopos],
            "frentes": self._nomes_das_frentes(banca_id),
            "coordenador": self._nome(banca.coordenador_id),
            # ⚠ O id junto do nome: a tela decide se mostra o formulário do
            # relato comparando com o usuário logado, e comparar por NOME
            # quebra em qualquer homônimo — além de esconder o formulário de
            # quem tem direito se o cadastro grafar o nome diferente.
            "coordenador_id": banca.coordenador_id,
            "membros": sorted(self._nome(i) for i in equipe),
            # ⭐ Objetos, não nomes soltos: a aba precisa saber QUEM é cada um
            # para responder "sou eu?" e "já votei?" sem cruzar listas do lado
            # do cliente. É o que permite votar de dentro do projeto.
            "avaliadores": self._avaliadores(banca_id),
            "descricao_coordenador": banca.descricao_coordenador,
            # ⭐ Cada TENTATIVA (§9) — é o que responde "por que este escopo
            # teve duas bancas?".
            "sessoes": self._sessoes(banca_id),
            # ⭐ Quem votou o quê, e o que cada um escreveu. O §8 diz que o
            # resultado sai da MAIORIA dos presentes; sem mostrar os votos, o
            # veredito é um oráculo.
            "avaliacoes": self._avaliacoes(banca_id),
            "apuracao": apuracao,
            "nota_final": self._nota_final(banca_id, apuracao["sessao"]),
            # Para a tela poder linkar de volta ao projeto — a ficha é aberta
            # de dentro dele, mas a banca pode cobrir escopo de outro lugar.
            "projeto_id": escopos[0].projeto_id if escopos else None,
        }

    def _avaliadores(self, banca_id: int) -> list:
        """Quem foi escalado, se compareceu e o que já votou NESTA sessão.

        ⭐ O estado de cada pessoa numa linha só. Sem isto a tela não consegue
        oferecer "dar meu voto" a quem tem direito: ela receberia uma lista de
        nomes e não teria como saber qual deles é o usuário logado, nem se ele
        já votou.

        A avaliação vem da sessão CORRENTE: numa 2ª banca, o voto que a pessoa
        deu na primeira não a impede de votar de novo — é outra tentativa.
        """
        corrente = self.sessao_repository.get_corrente(banca_id)
        if corrente is None:
            sessoes = self.sessao_repository.get_by_banca(banca_id)
            corrente = sessoes[-1] if sessoes else None
        numero = corrente.numero if corrente else 1

        # Rascunho entra aqui de propósito, ao contrário de `_avaliacoes`: a
        # tela precisa reaproveitar o rascunho da própria pessoa em vez de
        # criar um segundo — dois rascunhos do mesmo avaliador viram duas
        # linhas que a apuração teria de deduplicar.
        por_avaliador = {
            a.avaliador_id: a
            for a in self.avaliacao_repository.get_by_banca(banca_id, sessao=numero)
        }

        linhas = []
        for c in self.candidatura_repository.get_by_banca(banca_id):
            minha = por_avaliador.get(c.usuario_id)
            linhas.append(
                {
                    "usuario_id": c.usuario_id,
                    "nome": self._nome(c.usuario_id),
                    # Marcado ao registrar a realização: quem de fato esteve lá.
                    "presente": bool(c.confirmado),
                    "avaliacao_id": minha.id if minha else None,
                    "ja_votou": bool(minha and minha.status == "submetida"),
                    "voto_aprovacao": minha.voto_aprovacao if minha else None,
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
        """Uma linha por avaliação SUBMETIDA: quem, de qual sessão, voto e texto.

        ⚠ Rascunho fica de fora de propósito. É o formulário aberto e não
        enviado — mostrá-lo exporia uma opinião que a pessoa ainda não decidiu
        tornar pública, e ele não conta na apuração.
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
                "voto_aprovacao": a.voto_aprovacao,
                "comentario_feedback": a.comentario_feedback,
                "submetida_em": a.submetida_em,
                # ⭐ O que a pessoa respondeu, critério a critério. É o que a aba
                # abre ao clicar no nome dela: sem isto, o voto aparece sem a
                # avaliação que o justifica.
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

    def _apuracao(self, banca, banca_id: int) -> dict:
        """A conta dos votos da sessão CORRENTE, como a tela precisa mostrá-la.

        Não decide nada — quem grava o veredito é `apurar_banca`, no ato do
        voto e no job diário. Aqui é leitura: "3 de 4 votaram, 2 a favor".
        """
        # A sessão corrente; na falta dela (todas encerradas), a ÚLTIMA.
        #
        # ⚠ Cair para `1` mostrava a conta da PRIMEIRA tentativa numa banca já
        # decidida na segunda — a tela exibiria os votos que reprovaram ao lado
        # do veredito "aprovada".
        corrente = self.sessao_repository.get_corrente(banca_id)
        if corrente is None:
            sessoes = self.sessao_repository.get_by_banca(banca_id)
            corrente = sessoes[-1] if sessoes else None
        numero = corrente.numero if corrente else 1
        candidaturas = self.candidatura_repository.get_by_banca(banca_id)
        escalados = {c.usuario_id for c in candidaturas}
        submetidas = [
            a
            for a in self.avaliacao_repository.get_by_banca(banca_id, sessao=numero)
            if a.status == "submetida"
            and a.voto_aprovacao is not None
            and (not escalados or a.avaliador_id in escalados)
        ]
        votantes = list(votos_por_avaliador(submetidas).values())
        # ⚠ O prazo REAL, não "já tem veredito".
        #
        # `motivo` é o que a tela usa para escolher a mensagem, e os dois casos
        # pedem ações opostas: "aguardando" manda esperar o último voto,
        # "sem_votos" manda a diretoria registrar o resultado à mão. Uma banca
        # com prazo vencido e zero voto aparecia como "aguardando" — a tela
        # pedia paciência num beco que só a diretoria destrava.
        prazo_vencido = bool(
            banca.resultado is not None
            or (
                banca.realizado_em
                and datetime.now() > banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
            )
        )
        conta = apurar(
            [a.voto_aprovacao for a in votantes],
            esperados=eleitorado(candidaturas, [a.avaliador_id for a in votantes]),
            prazo_vencido=prazo_vencido,
        )
        return {
            "sessao": numero,
            "aprovacoes": conta.aprovacoes,
            "reprovacoes": conta.reprovacoes,
            "esperados": conta.esperados,
            "motivo": conta.motivo,
        }

    def _nota_final(self, banca_id: int, sessao: int):
        """A média das notas por critério — outra dimensão que o VOTO.

        A nota diz quão bem o trabalho foi feito; o voto responde se ele pode
        ir ao cliente. Dá para ir bem na nota e reprovar por um ponto isolado.

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

    def _nome(self, usuario_id) -> str:
        if not usuario_id:
            return "—"
        usuario = self.usuario_repository.get_by_id(usuario_id)
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
        nomes = []
        for vinculo in self.banca_frente_repository.get_by_banca(banca_id):
            frente = self.frente_repository.get_by_id(vinculo.frente_id)
            if frente:
                nomes.append(frente.nome)
        return sorted(nomes)


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

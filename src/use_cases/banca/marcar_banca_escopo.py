"""Marcar a banca de um escopo — pelo cronograma ou pela tela de Bancas.

⚠ **Não existe sincronização aqui, e é de propósito.** O §8 fala em "os dois
lados conversam e ficam sincronizados (uma data só)" — a resposta certa a isso
NÃO é uma rotina de sync entre duas tabelas, é haver uma linha só. Marcar a
banca pelo cronograma escreve em `banca`, exatamente a mesma linha que
`/bancas` lê. Mudou de um lado, o outro vê no próximo load. Não é
sincronização: é a mesma linha lida duas vezes.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_remarcacao_repository import BancaRemarcacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_remarcacao_banca_repository import ProjetoRemarcacaoBancaRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.use_cases.notificacao.eventos import notificar_banca_remarcada
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.composicao_banca import ComposicaoBancaChecker
from src.utils.contagem_dias import derivar_janelas_pausa
from src.utils.piso_banca import calcular_piso_banca
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.janela_escopo import (
    FOLGA_LIVRE_REMARCACAO_DIAS_UTEIS,
    calcular_janela,
    dentro_da_janela,
    dias_uteis_ate_a_banca,
)
from src.utils.notificar import notificar


class MarcarBancaEscopoRequest(BaseModel):
    data_hora: datetime
    #: §9: remarcação nunca é silenciosa — justificativa sempre obrigatória,
    #: mesmo quando remarcar é livre. Obrigatória também na PRIMEIRA marcação,
    #: quando a data escolhida cai fora da janela do escopo (§13).
    justificativa: Optional[str] = None
    #: ⭐ O conjunto COMPLETO de escopos que esta banca cobre, escolhido por
    #: quem marca. O escopo da URL entra sempre, mesmo que não venha na lista.
    #: `None` = não mexer nos vínculos atuais (é o que as chamadas antigas
    #: fazem: marcam a banca do escopo da URL e pronto).
    escopo_ids: Optional[List[int]] = None


class MarcarBancaEscopoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.remarcacao_repository = ProjetoRemarcacaoBancaRepository(db)
        self.banca_remarcacao_repository = BancaRemarcacaoRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(
        self,
        escopo_id: int,
        request: MarcarBancaEscopoRequest,
        eh_diretor: bool = False,
        current_user=None,
        registrado_por: Optional[int] = None,
    ):
        escopo = self.escopo_repository.get_by_id(escopo_id)
        if not escopo:
            return None

        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        existente = self.repository.get_by_projeto_escopo(escopo_id)
        escopos_cobertos = self._resolver_escopos(escopo, request, existente)

        # Precisa ser decidido ANTES dos gates: a 2ª banca (a que sucede uma
        # que já aconteceu) segue regras diferentes das do adiamento.
        eh_segunda_banca = bool(existente and existente.realizado_em is not None)

        self._checar_choque(
            request.data_hora,
            ignorar_banca_id=existente.id if existente else None,
            projeto_escopo_id=escopo_id,
        )
        # ⭐ §9: o ÚNICO bloqueio duro do cronograma. Pintar além da janela
        # avisa (§15); marcar banca fora dela não passa sem a diretoria.
        self._exigir_janela(escopos_cobertos, request, eh_diretor, eh_segunda_banca)

        if existente:
            data_anterior = existente.data_hora
            # ⭐ Dois caminhos MUITO diferentes chegam aqui, e a régua que os
            # separa é `realizado_em`:
            #
            # - a banca ainda não aconteceu → é ADIAMENTO, com os gates do §13;
            # - a banca já aconteceu → é a 2ª BANCA do escopo, e os gates do
            #   adiamento não fazem sentido nela (ver `_exigir_segunda_permitida`).
            if data_anterior is not None and data_anterior != request.data_hora:
                if eh_segunda_banca:
                    # ⚠ **Apurar ANTES de julgar.** `_exigir_segunda_permitida`
                    # lê `existente.resultado` para recusar a 2ª banca de uma
                    # banca APROVADA — mas a apuração da sessão que está sendo
                    # descartada só acontecia depois, dentro de
                    # `_sincronizar_sessao`. A guarda nunca via a aprovação que
                    # ela existe para barrar.
                    #
                    # O estrago era exatamente o que ela previne: a sessão era
                    # arquivada como "aprovada", a 2ª banca nascia assim mesmo e
                    # `_campos_da_remarcacao` zerava `banca.resultado` — a
                    # coluna que a trava da entrega lê (§5.5). O escopo ficava
                    # aprovado no histórico e travado na tela, e o próprio
                    # histórico dizia "Segunda banca — a anterior foi reprovada"
                    # ao lado de "Resultado: aprovada".
                    existente = self._apurar_sessao_em_curso(existente)
                    self._exigir_segunda_permitida(existente)
                else:
                    # §9: remarcação nunca é silenciosa — justificativa SEMPRE,
                    # mesmo quando é livre. O que o §13 dispensa é a diretoria,
                    # não o registro.
                    self._exigir_remarcacao_permitida(existente, request, eh_diretor)

            # ⚠ ANTES do update: `_campos_da_remarcacao` zera `realizado_em` e
            # `resultado`, e é justamente isso que a sessão precisa arquivar.
            # Invertida a ordem, a sessão guardaria campos já limpos e a
            # reprovação se perderia de novo.
            #
            # ⚠ E SÓ quando a data muda. `_campos_da_remarcacao` faz early-return
            # se a data é a mesma — a banca continua realizada. Sincronizar
            # assim mesmo abriria uma sessão 2 fantasma numa banca que não foi
            # remarcada, e os votos carimbados com `sessao=1` passariam a
            # apontar para uma sessão encerrada: a apuração leria a sessão nova,
            # vazia, e nunca fecharia.
            if data_anterior != request.data_hora:
                self._sincronizar_sessao(existente, request)

            banca = self.repository.update(
                existente.id, **self._campos_da_remarcacao(existente, request)
            )
            # Depois do update e só se a data realmente mudou: salvar a mesma
            # data (por causa de outra edição na mesma request) não é remarcação.
            if data_anterior != banca.data_hora:
                if data_anterior is not None:
                    self.banca_remarcacao_repository.create(
                        banca_id=banca.id,
                        data_anterior=data_anterior,
                        data_nova=banca.data_hora,
                        justificativa=(request.justificativa or "").strip(),
                        remarcado_por=getattr(current_user, "id", None) or banca.coordenador_id,
                        autorizado_por=getattr(current_user, "id", None) if eh_diretor else None,
                    )
                notificar_banca_remarcada(
                    self.db, projeto, banca.id, self._nome(escopo), data_anterior, banca.data_hora
                )
                # §5.6: a justificativa exigida acima finalmente vai pra algum
                # lugar — sem isso, ela era validada e jogada fora.
                self.remarcacao_repository.create(
                    projeto_id=projeto.id,
                    banca_id=banca.id,
                    projeto_escopo_id=escopo.id,
                    data_anterior=data_anterior,
                    data_nova=banca.data_hora,
                    # ⚠ Era `request.justificativa.strip()` cru, e quebrava com
                    # `None` desde que a 2ª banca passou a dispensar o texto.
                    # O fallback não é enfeite: diz por que a linha existe sem
                    # justificativa, em vez de gravar vazio e deixar quem lê o
                    # Histórico achar que alguém esqueceu de preencher.
                    justificativa=(
                        (request.justificativa or "").strip()
                        or "Segunda banca — a anterior foi reprovada"
                    ),
                    registrado_por=registrado_por,
                )
        else:
            coordenador = next(
                (
                    m
                    for m in self.membro_repository.get_by_projeto(escopo.projeto_id, apenas_atuais=True)
                    if m.papel == "coordenador"
                ),
                None,
            )
            if not coordenador:
                raise RegraDeNegocioError("O projeto precisa ter um coordenador para marcar a banca")

            banca = self.repository.create(
                # `nome_projeto` e `escopo_id` continuam gravados por
                # compatibilidade com o módulo legado, mas quem manda é o
                # vínculo em `banca_escopo`.
                nome_projeto=projeto.nome,
                escopo_id=escopo.escopo_id,
                coordenador_id=coordenador.usuario_id,
                data_hora=request.data_hora,
            )
            # Toda banca nasce com a sessão nº 1. Sem ela, `get_corrente`
            # devolveria `None` numa banca perfeitamente normal e a realização
            # não teria onde se registrar.
            self.sessao_repository.create(
                banca_id=banca.id, numero=1, data_hora=banca.data_hora
            )

        self.banca_escopo_repository.definir(banca.id, [e.id for e in escopos_cobertos])
        self._garantir_frentes(banca.id, [e.frente_id for e in escopos_cobertos])

        return {
            "id": banca.id,
            "projeto_escopo_ids": [e.id for e in escopos_cobertos],
            "frente_ids": sorted({e.frente_id for e in escopos_cobertos}),
            "data_hora": banca.data_hora,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
        }

    def _campos_da_remarcacao(self, existente, request: MarcarBancaEscopoRequest) -> dict:
        """O que muda na linha da banca ao remarcá-la.

        ⭐ **É uma banca por escopo, sempre a mesma linha** — inclusive quando a
        banca foi reprovada e precisa acontecer de novo (§9). Por isso, marcar
        uma data NOVA para uma banca que já aconteceu tem de limpar
        `realizado_em` e `resultado`: eles descrevem a sessão anterior, não a
        que acabou de ser marcada.

        Sem isso, a banca remarcada continuava `realizada` para
        `calcular_status_banca` (que testa `realizado_em` antes da data) e
        seguia com `entrega_liberada: true` — o escopo podia ser entregue ao
        cliente com a nova banca ainda por acontecer.

        ⚠ **Limpar aqui já foi APAGAR.** Antes de `banca_sessao` existir, o
        veredito da sessão anterior sumia do banco: sobrava a data antiga em
        `banca_remarcacao` e nada dizendo que a banca havia sido REPROVADA.
        Agora `_abrir_proxima_sessao` arquiva a sessão antes que estes campos
        sejam zerados — quem chama precisa fazer as duas coisas, nesta ordem.
        """
        campos = {"data_hora": request.data_hora}
        if existente.data_hora == request.data_hora:
            return campos
        if existente.realizado_em is not None:
            campos["realizado_em"] = None
            campos["resultado"] = None
        return campos

    def _apurar_sessao_em_curso(self, banca):
        """Fecha a conta dos votos ANTES de decidir o destino da sessão (§8).

        ⭐ Roda no exato ponto em que a 2ª banca vai ser julgada, e é essa
        ordem que importa. A sessão que está prestes a ser descartada pode ter
        votos que nunca viraram veredito — 2 de 3 votaram e o terceiro sumiu.
        Duas coisas dependem de apurá-los agora:

        1. **Não perder os votos.** Arquivada a sessão, eles ficam presos ao
           número antigo, e o job diário — que varre `banca.realizado_em`,
           zerado na remarcação — nunca mais os alcança.
        2. **Deixar a guarda enxergar a aprovação.** `_exigir_segunda_permitida`
           recusa a 2ª banca de uma banca APROVADA. Se a apuração só rodasse
           depois dela, uma banca que a urna acabou de aprovar ganharia uma 2ª
           banca e perderia o veredito que libera a entrega — o mesmo estrago
           que a guarda existe para impedir, por uma janela de ordenação.

        `prazo_vencido=True` porque a sessão acaba AQUI, não daqui a dois dias:
        quem não votou até a remarcação não vai mais votar naquela banca. Sem
        voto nenhum continua sem veredito, como sempre.

        Devolve a banca RECARREGADA — `apurar_banca` grava direto no banco, e
        quem chama precisa enxergar o resultado que acabou de nascer.
        """
        # Import local: `submeter_avaliacao` importa `registrar_resultado_na_sessao`
        # deste módulo, e no topo isto seria circular.
        from src.use_cases.avaliacao.submeter_avaliacao import apurar_banca

        apurar_banca(self.db, banca, prazo_vencido=True)
        return self.repository.get_by_id(banca.id) or banca

    def _sincronizar_sessao(self, banca, request: MarcarBancaEscopoRequest) -> None:
        """⭐ Adiar ≠ segunda banca — e é aqui que a diferença é decidida.

        Duas coisas muito diferentes chegam nesta mesma rota:

        - **Adiar** uma banca que ainda não aconteceu: é a MESMA tentativa em
          outro dia. A sessão corrente só muda de data; quem registra o "de →
          para" é `banca_remarcacao`, como sempre foi.
        - **Marcar de novo** uma banca que já aconteceu (na prática, que foi
          REPROVADA — a aprovada não precisa de outra): a sessão anterior
          fecha guardando `realizado_em` e `resultado`, e nasce a sessão
          seguinte. É esta que a tela chama de "2ª banca do escopo".

        A régua é `realizado_em`, não `resultado`: uma banca realizada e ainda
        sem veredito apurado também merece sessão nova se for remarcada —
        aconteceu, e o que vem é outra sessão.
        """
        corrente = self.sessao_repository.get_corrente(banca.id)

        if corrente is None:
            # Banca anterior ao `banca_sessao` que escapou do backfill, ou uma
            # cuja última sessão já foi encerrada com veredito. Abre a próxima.
            self.sessao_repository.create(
                banca_id=banca.id,
                numero=self.sessao_repository.proximo_numero(banca.id),
                data_hora=request.data_hora,
            )
            return

        if corrente.realizado_em is None:
            self.sessao_repository.update(corrente.id, data_hora=request.data_hora)
            return

        # A apuração da sessão que está sendo descartada já rodou em
        # `_apurar_sessao_em_curso`, ANTES da guarda que decide se esta 2ª banca
        # pode existir. Aqui só resta arquivar.
        self.sessao_repository.update(corrente.id, encerrada_em=datetime.now())
        self.sessao_repository.create(
            banca_id=banca.id,
            numero=self.sessao_repository.proximo_numero(banca.id),
            data_hora=request.data_hora,
        )

    def _resolver_escopos(self, escopo, request: MarcarBancaEscopoRequest, existente):
        """Quais escopos esta banca vai cobrir — e se pode cobri-los.

        Uma banca pode juntar vários escopos do MESMO projeto (inclusive de
        frentes diferentes). O que ela não pode é roubar escopo que já tem
        banca própria: como o escopo continua tendo no máximo uma, juntá-lo
        aqui apagaria em silêncio a data que já estava marcada nele.
        """
        if request.escopo_ids is None:
            atuais = (
                self.banca_escopo_repository.get_escopo_ids(existente.id) if existente else []
            )
            pedidos = set(atuais) | {escopo.id}
        else:
            pedidos = set(request.escopo_ids) | {escopo.id}

        escopos = []
        for pedido_id in sorted(pedidos):
            alvo = escopo if pedido_id == escopo.id else self.escopo_repository.get_by_id(pedido_id)
            if not alvo:
                raise RegraDeNegocioError(f"Escopo {pedido_id} não encontrado")
            if alvo.projeto_id != escopo.projeto_id:
                raise RegraDeNegocioError(
                    "Uma banca só pode cobrir escopos do mesmo projeto"
                )
            dono = self.banca_escopo_repository.get_banca_id(alvo.id)
            if dono is not None and (existente is None or dono != existente.id):
                raise RegraDeNegocioError(
                    f"O escopo '{self._nome(alvo)}' já tem banca marcada — "
                    "desmarque a dele antes de juntar os dois"
                )
            escopos.append(alvo)
        return escopos

    def _nome(self, escopo) -> str:
        if escopo.nome_customizado:
            return escopo.nome_customizado
        do_catalogo = self.catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
        return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"

    def _garantir_frentes(self, banca_id: int, frente_ids: List[int]) -> None:
        """⭐ A banca é das frentes **dos escopos que ela cobre**, não de todas
        as frentes do projeto.

        Uma banca só de Análise Mercadológica é banca de Business; se a mesma
        banca também cobrir Revisão Contratual, ela passa a ser de Business +
        Direito e a composição do §8 cobra o piso das duas. É a consequência
        esperada de juntar os escopos — quem junta está dizendo que uma banca
        só avalia os dois trabalhos.

        Roda também na remarcação, de propósito: banca criada por fora deste
        fluxo (o módulo legado, um seed) chega aqui sem vínculo nenhum, e
        marcar a data é a oportunidade de acertar isso. Idempotente.

        Só adiciona: frente escalada à mão por outro caminho não é removida
        daqui, porque pode já ter gente inscrita por ela.
        """
        atuais = {bf.frente_id for bf in self.banca_frente_repository.get_by_banca(banca_id)}
        for frente_id in sorted(set(frente_ids) - atuais):
            self.banca_frente_repository.create(banca_id=banca_id, frente_id=frente_id)

    def _janela_do_escopo(self, escopo):
        dias_nao_letivos = [d.data for d in self.dia_nao_letivo_repository.get_all()]
        # A janela precisa enxergar as pausas do projeto — senão a banca de um
        # projeto que ficou ⏸ Pausado é barrada por uma data que já não é o fim
        # da janela dele.
        janelas_pausa = derivar_janelas_pausa(
            self.historico_repository.get_by_projeto(escopo.projeto_id)
        )
        return calcular_janela(
            escopo.data_inicio,
            escopo.dias_uteis_vendidos,
            escopo.dias_uteis_ajustados,
            dias_nao_letivos,
            janelas_pausa=janelas_pausa,
        )

    def _exigir_janela(
        self,
        escopos_cobertos,
        request: MarcarBancaEscopoRequest,
        eh_diretor: bool,
        eh_segunda_banca: bool = False,
    ) -> None:
        """§9: a banca só cabe em dia dentro da janela do escopo.

        ⚠ **De TODOS os escopos que ela cobre.** Uma banca que avalia dois
        escopos de uma sentada precisa caber nos dois — estar fora da janela de
        um deles é exatamente o atraso que o §10 vai cobrar daquele escopo, e
        deixar passar em silêncio esconderia isso.

        Fora da janela não é proibido: é decisão da diretoria (§13), e os dias
        entre o fim da janela e a data nova viram atraso sozinhos — não há o
        que gravar, `dias_de_atraso` deriva.

        ⭐ **A 2ª banca continua precisando de diretoria, mas não de texto.**
        Ela quase sempre cai fora da janela — é da natureza de uma reprovação
        empurrar o escopo para além do vendido —, e isentá-la do gate apagaria
        do monitoramento exatamente o atraso que a reprovação causou. O que ela
        dispensa é a JUSTIFICATIVA digitada: o motivo é a reprovação, que já
        está gravada na sessão anterior. Exigir que se escreva de novo o que o
        sistema acabou de registrar é pedir carimbo.
        """
        for alvo in escopos_cobertos:
            janela = self._janela_do_escopo(alvo)

            # §20.4: sem reunião inicial não há janela, e sem janela não há
            # banca. É a ordem do §6 (reunião → etapas → banca), e o inverso da
            # trava antiga, que exigia a banca ANTES da reunião inicial.
            if not janela.aberta:
                raise RegraDeNegocioError(
                    f"O escopo '{self._nome(alvo)}' ainda não teve reunião inicial — "
                    "marque-a antes, é ela que abre a janela em que a banca cabe"
                )

            if dentro_da_janela(request.data_hora, janela):
                continue

            if not eh_diretor:
                raise RegraDeNegocioError(
                    f"Esta data está fora da janela de '{self._nome(alvo)}', que vai de "
                    f"{janela.data_inicio.strftime('%d/%m/%Y')} a "
                    f"{janela.fim.strftime('%d/%m/%Y')} "
                    f"({janela.dias_vendidos} vendidos + {janela.dias_ajustados} ajustados). "
                    "Marcar fora dela é decisão da diretoria, e os dias além da janela "
                    "entram como atraso do projeto (§13)"
                )
            # §13: fora da janela é "autorização **+ justificativa**". Vale
            # também na primeira marcação — sem isso, o Histórico registraria
            # um atraso que ninguém explicou. A 2ª banca é a exceção: o texto
            # dela já existe, é a reprovação da sessão anterior.
            if eh_segunda_banca:
                continue
            if not (request.justificativa or "").strip():
                raise RegraDeNegocioError(
                    f"Marcar a banca fora da janela de '{self._nome(alvo)}' exige "
                    "justificativa — os dias além dela entram como atraso"
                )

    def _exigir_remarcacao_permitida(
        self, existente, request: MarcarBancaEscopoRequest, eh_diretor: bool
    ) -> None:
        """Os dois gates de remarcação do §13 — só para ADIAMENTO.

        Remarcar dentro da janela e com folga é **livre** para quem edita o
        projeto — era decisão da diretoria para tudo, e isso fazia da exceção
        uma rotina. O que continua exigindo diretoria é remarcar em cima da
        hora: a banca dos próximos 5 dias úteis já tem avaliadores escalados
        que reservaram a agenda.

        A justificativa é sempre obrigatória, com ou sem gate: §9 diz que
        remarcação nunca é silenciosa, e é ela que vai para o Histórico.

        ⚠ **Não chame isto para uma 2ª banca.** Ver `_exigir_segunda_permitida`:
        os dois gates daqui pressupõem uma banca que ainda VAI acontecer, e
        aplicá-los a uma que já aconteceu barra o caso legítimo.
        """
        if not (request.justificativa or "").strip():
            raise RegraDeNegocioError("Remarcar uma banca exige justificativa")

        dias_nao_letivos = [d.data for d in self.dia_nao_letivo_repository.get_all()]
        folga = dias_uteis_ate_a_banca(existente.data_hora, dias_nao_letivos)

        if folga is not None and folga <= FOLGA_LIVRE_REMARCACAO_DIAS_UTEIS and not eh_diretor:
            raise RegraDeNegocioError(
                f"Esta banca acontece em {folga} "
                f"{'dia útil' if folga == 1 else 'dias úteis'} e os avaliadores já estão "
                "escalados. Remarcar em cima da hora é decisão da diretoria (§13)"
            )

    def _exigir_segunda_permitida(self, existente) -> None:
        """§9: marcar OUTRA banca para um escopo cuja banca já aconteceu.

        ⭐ **O gate de "em cima da hora" NÃO se aplica aqui, e isso é
        aritmética, não opinião.** `dias_uteis_ate_a_banca` devolve `0` para
        data no passado, e `0 <= FOLGA_LIVRE_REMARCACAO_DIAS_UTEIS` é sempre
        verdadeiro — passar uma 2ª banca por `_exigir_remarcacao_permitida`
        exigiria diretoria em **todas** elas. O gate existe para proteger a
        agenda de avaliadores já escalados; numa banca que já aconteceu não há
        agenda a proteger, eles compareceram.

        ⚠ **Banca APROVADA não ganha segunda.** Antes isto passava e o
        `_campos_da_remarcacao` apagava a aprovação em silêncio — o escopo
        perdia o veredito que liberava a entrega, sem registro em lugar nenhum.
        Se a data da banca aprovada estiver errada, o caminho é corrigir o
        registro, não marcar outra.

        A justificativa fica OPCIONAL: o motivo da 2ª banca é a reprovação, que
        já está registrada na sessão anterior. Cobrar um texto aqui seria pedir
        que se escrevesse de novo o que o sistema acabou de gravar.
        """
        if existente.resultado == "aprovada":
            raise RegraDeNegocioError(
                "Esta banca foi APROVADA — não há segunda banca a marcar. "
                "Se a data está errada, corrija o registro da banca."
            )

    def _checar_choque(
        self,
        data_hora: datetime,
        ignorar_banca_id: Optional[int],
        projeto_escopo_id: Optional[int] = None,
    ) -> None:
        """§8, delegado para `excecao_choque.checar_choque`.

        A regra saiu daqui para virar função de módulo quando se descobriu que
        `POST /bancas` e `PATCH /bancas/{id}` gravavam `data_hora` sem passá-la.
        Este wrapper fica porque os testes e a leitura do fluxo apontam para
        ele, mas quem decide é um lugar só.
        """
        from src.use_cases.banca.excecao_choque import checar_choque

        checar_choque(
            self.db,
            data_hora,
            banca_repository=self.repository,
            ignorar_banca_id=ignorar_banca_id,
            projeto_escopo_id=projeto_escopo_id,
        )


class RegistrarRealizacaoRequest(BaseModel):
    realizado_em: Optional[datetime] = None
    #: Quem de fato compareceu — confirma as candidaturas listadas.
    presentes: Optional[list[int]] = None
    #: Registrar mesmo com menos gente que o mínimo. Só a diretoria (§8: a
    #: exceção às regras de composição é liberada por ela).
    forcar: bool = False


class RegistrarRealizacaoBancaUseCase:
    """⭐ Marcar que a banca ACONTECEU (§8).

    É esta escrita que separa "a data passou" de "a banca aconteceu" — e sem
    ela, a partir da F5, a banca fica `atrasada` para sempre. Passou a ser
    passo obrigatório da rotina.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        from src.repositories.candidatura_repository import CandidaturaRepository
        from src.repositories.frente_repository import FrenteRepository

        self.candidatura_repository = CandidaturaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.composicao_checker = ComposicaoBancaChecker(db)

    def execute(
        self,
        banca_id: int,
        request: RegistrarRealizacaoRequest,
        eh_diretor: bool = False,
    ):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None
        if not banca.data_hora:
            raise RegraDeNegocioError("Uma banca sem data não pode ser marcada como realizada")

        self._exigir_composicao(banca, request, eh_diretor)

        realizado_em = request.realizado_em or banca.data_hora
        banca = self.repository.update(banca_id, realizado_em=realizado_em)

        # A sessão corrente é a que ACONTECEU. Sem espelhar aqui, a próxima
        # remarcação arquivaria uma sessão sem data de realização e o histórico
        # de tentativas ficaria mudo sobre quando cada uma foi.
        corrente = self.sessao_repository.get_corrente(banca_id)
        if corrente:
            self.sessao_repository.update(
                corrente.id, realizado_em=realizado_em, data_hora=banca.data_hora
            )

        candidaturas = self.candidatura_repository.get_by_banca(banca_id)
        if request.presentes is not None:
            presentes = set(request.presentes)
            for candidatura in candidaturas:
                self.candidatura_repository.update(
                    candidatura.id, confirmado=candidatura.usuario_id in presentes
                )
            avisar = presentes
        else:
            # Sem lista de presença, avisa todo mundo que era candidato — não
            # deixar de notificar por falta de dado é melhor que silenciar.
            avisar = {c.usuario_id for c in candidaturas}

        self._notificar_prazo_avaliacao(banca, avisar)
        self._notificar_descricao_coordenador(banca)

        return {
            "id": banca.id,
            "realizado_em": banca.realizado_em,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
        }

    def _exigir_composicao(self, banca, request, eh_diretor: bool) -> None:
        """A banca não fecha com menos gente que o combinado, nem faltando a
        distribuição certa entre frentes e a liderança de cada uma (§8).

        📐 O piso TOTAL é a SOMA do `piso_banca` das frentes vinculadas (§8:
        Business 3 · Tech 2 · Eng. de Processos 2 · Direito 1) — vem de
        `calcular_piso_banca`, o mesmo caminho do push automático. Mas total
        não basta: uma banca Business+Tech (piso 3+2=5) não pode fechar com 5
        de Business e ZERO de Tech, então `ComposicaoBancaChecker` confere o
        piso POR frente e a liderança (gerente da frente, ou diretor) de cada
        uma, excluindo a equipe do próprio projeto da contagem. Só depois de
        cada frente cumprida é que o resto das vagas pode ser de qualquer uma.

        `piso_minimo_override` (a diretoria já afrouxou esta banca específica)
        relaxa TUDO — total, por frente e liderança — não só o total.

        ⚠ NÃO é `configuracao.vagas_por_banca`: aquilo é o TETO de quantos
        cabem na banca (`create_candidatura` recusa em "banca lotada"), e usar
        o teto como piso reprovaria quase toda banca — 5 alocados exigidos
        onde o §8 pede 3.

        A saída é `forcar`, e só para a diretoria — é ela que libera exceção às
        regras de composição no §8. Sem essa porta, uma banca que aconteceu com
        4 pessoas ficaria "atrasada" para sempre, e o §7.4 mede atraso
        exatamente por isso: a nota de rodapé viraria dado errado no
        monitoramento.
        """
        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        frentes = [
            f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos) if f
        ]
        minimo = calcular_piso_banca(banca, frentes)
        candidaturas = self.candidatura_repository.get_by_banca(banca.id)
        alocados = len(candidaturas)

        problemas = []
        if alocados < minimo:
            problemas.append(f"{alocados} de {minimo} pessoas alocadas")

        if banca.piso_minimo_override is None and frentes:
            configuracao = self.configuracao_repository.get()
            lideranca_minima = configuracao.lideranca_minima_por_frente if configuracao else 1
            candidato_ids = {c.usuario_id for c in candidaturas}
            status = self.composicao_checker.verificar(banca, frentes, candidato_ids, lideranca_minima)
            for deficit in status.deficits:
                if deficit.piso_faltando:
                    problemas.append(f"faltam {deficit.piso_faltando} de {deficit.frente_nome}")
                if deficit.lideranca_faltando:
                    problemas.append(f"falta liderança de {deficit.frente_nome}")

        if not problemas:
            return

        if not request.forcar:
            raise RegraDeNegocioError(
                "Composição incompleta (" + "; ".join(problemas) + "). "
                "Só a diretoria pode registrá-la assim mesmo."
            )
        if not eh_diretor:
            raise RegraDeNegocioError(
                "Apenas o Diretor de Projetos pode registrar uma banca abaixo do mínimo"
            )

    def _notificar_prazo_avaliacao(self, banca, usuario_ids) -> None:
        prazo = banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
        mensagem = (
            f"A banca de {banca.nome_projeto} foi realizada. Você tem até "
            f"{prazo:%d/%m/%Y} para enviar sua avaliação."
        )
        for usuario_id in usuario_ids:
            notificar(
                self.db, usuario_id, mensagem, banca_id=banca.id, tipo="avaliacao_pendente"
            )

    def _notificar_descricao_coordenador(self, banca) -> None:
        """O coordenador não avalia a própria banca — este é o aviso dele,
        separado do prazo de avaliação acima, que é só pros candidatos."""
        notificar(
            self.db,
            banca.coordenador_id,
            f"A banca de {banca.nome_projeto} foi realizada. Registre a sua descrição do resultado.",
            banca_id=banca.id,
            tipo="descricao_coordenador_pendente",
        )


class RegistrarResultadoRequest(BaseModel):
    resultado: str  # "aprovada" | "nao_aprovada"


class RegistrarResultadoBancaUseCase:
    """🔒 O resultado é o que libera ou trava a entrega ao cliente (§8).

    ⚠ **Isto é o OVERRIDE da diretoria, não o caminho normal.** O veredito sai
    do voto de quem assistiu (`utils/apuracao_banca.py`) — esta rota existe
    para o caso que a apuração não resolve: banca realizada em que ninguém
    votou, e que ficaria travando a entrega para sempre.

    Por isso o router a restringe a `require_diretor`: sobrescrever a maioria
    não é ação de rotina de quem conduz o cronograma.
    """

    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)

    def execute(self, banca_id: int, request: RegistrarResultadoRequest):
        if request.resultado not in ("aprovada", "nao_aprovada"):
            raise RegraDeNegocioError("O resultado precisa ser 'aprovada' ou 'nao_aprovada'")

        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None
        # Não há resultado de banca que não aconteceu.
        if not banca.realizado_em:
            raise RegraDeNegocioError(
                "Registre primeiro que a banca foi realizada, depois o resultado"
            )

        banca = self.repository.update(banca_id, resultado=request.resultado)
        registrar_resultado_na_sessao(self.sessao_repository, banca)
        return {"id": banca.id, "resultado": banca.resultado}


def registrar_resultado_na_sessao(sessao_repository, banca) -> None:
    """Copia o veredito para a sessão corrente e a ENCERRA.

    Função solta porque tem dois chamadores por natureza diferentes: o override
    da diretoria acima e a apuração automática por voto. Duplicar isso nos dois
    seria duas versões de "o que significa fechar uma sessão".

    ⭐ Encerrar aqui é o que faz a próxima marcação abrir a sessão seguinte em
    vez de sobrescrever esta — é a fronteira entre "adiar" e "2ª banca".
    """
    corrente = sessao_repository.get_corrente(banca.id)
    if not corrente:
        return
    sessao_repository.update(
        corrente.id,
        realizado_em=banca.realizado_em,
        resultado=banca.resultado,
        encerrada_em=datetime.now(),
    )


class LiberarExcecaoChoqueRequest(BaseModel):
    nota: str


class LiberarExcecaoChoqueUseCase:
    """§8: a exceção de choque de horário só é liberada pela diretoria."""

    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: LiberarExcecaoChoqueRequest, liberado_por: int):
        if not (request.nota or "").strip():
            raise RegraDeNegocioError("A exceção de choque exige uma justificativa")
        banca = self.repository.update(
            banca_id, excecao_choque_por=liberado_por, excecao_choque_nota=request.nota.strip()
        )
        return {"id": banca.id, "excecao_choque_por": banca.excecao_choque_por} if banca else None

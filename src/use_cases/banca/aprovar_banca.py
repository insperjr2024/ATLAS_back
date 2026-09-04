"""⭐ Quem aprova a banca é diretoria de projetos OU gerente de qualquer
frente dela (§5.5, §8) — não mais a maioria dos avaliadores.

⭐ **Qualquer um decide sozinho.** Mudança de direção do próprio usuário
(2026-09-03): a primeira versão exigia diretoria E gerente concordando; agora
o primeiro que decidir já fecha o resultado, sem esperar os demais. Diretoria
e o gerente de cada frente têm o mesmo peso.

Duas pontas:

- `RegistrarAprovacaoBancaUseCase`: o botão único de "Aprovar"/"Reprovar". O
  papel de quem está agindo (diretoria ou gerente de qual frente) é resolvido
  aqui dentro a partir do `current_user`, não escolhido pela tela — é o que
  impede alguém de assinar por um papel que não é seu.
- `ListarBancasEsperandoAprovacaoUseCase`: a fila "Esperando aprovação" da aba
  Bancas — bancas realizadas sem veredito, escopadas por quem pode decidir.

`montar_situacao_aprovacao` é a leitura comum às duas rotas acima e à ficha da
banca (`get_banca_detalhes.py`) e à fila de Monitoramento
(`monitoramento/aprovacoes.py`) — um só lugar resolve os nomes de quem já
decidiu (banca fechada) ou de quem PODE decidir (banca ainda em aberto).
"""

from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.middlewares.authorization import eh_diretoria_de_projetos, frentes_do_usuario
from src.repositories.banca_aprovacao_repository import BancaAprovacaoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.banca.marcar_banca_escopo import registrar_resultado_na_sessao
from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo
from src.utils.apuracao_banca import apurar_aprovacao
from src.utils.exceptions import RegraDeNegocioError


def _frentes_da_banca(db: Session, banca_id: int) -> List[int]:
    """As frentes desta banca (`banca_frente`) — não do projeto inteiro: um
    projeto sinérgico pode ter uma banca por frente."""
    return sorted({bf.frente_id for bf in BancaFrenteRepository(db).get_by_banca(banca_id)})


def _gerentes_da_frente(db: Session, frente_id: int) -> List:
    """Os gerentes ATIVOS vinculados a esta frente especificamente — pode ser
    mais de um, e qualquer um deles pode aprovar por ela (ver `execute`)."""
    usuario_frente_repository = UsuarioFrenteRepository(db)
    usuario_repository = UsuarioRepository(db)
    vinculos = usuario_frente_repository.get_by_frente(frente_id)
    usuarios = [usuario_repository.get_by_id(v.usuario_id) for v in vinculos]
    return [u for u in usuarios if u and u.posicao == "gerente" and u.ativo]


def _possiveis_gerentes(db: Session) -> List:
    """Fallback para quando a frente ainda não tem gerente vinculado: todo
    gerente ativo do sistema — quem lê a fila sabe a quem pedir para cadastrar
    o vínculo."""
    return [u for u in UsuarioRepository(db).get_por_posicao("gerente") if u.ativo]


def projeto_da_banca(db: Session, banca_id: int) -> Optional[int]:
    """`projeto_id` da banca, via `banca_escopo` → `projeto_escopo`.

    `None` para banca legada (sem vínculo de escopo) — não há projeto a partir
    do qual cobrar gerente nenhum, e só a diretoria decide essas.
    """
    escopo_ids = BancaEscopoRepository(db).get_escopo_ids(banca_id)
    projeto_escopo_repository = ProjetoEscopoRepository(db)
    for escopo_id in escopo_ids:
        escopo = projeto_escopo_repository.get_by_id(escopo_id)
        if escopo:
            return escopo.projeto_id
    return None


def sessao_corrente(db: Session, banca_id: int) -> int:
    """O número da tentativa (§9) em curso — mesmo cálculo de
    `get_banca_detalhes.py`: a sessão corrente ou, na falta dela (todas
    encerradas), a última."""
    sessao_repository = BancaSessaoRepository(db)
    corrente = sessao_repository.get_corrente(banca_id)
    if corrente is None:
        sessoes = sessao_repository.get_by_banca(banca_id)
        corrente = sessoes[-1] if sessoes else None
    return corrente.numero if corrente else 1


def montar_situacao_aprovacao(db: Session, banca) -> dict:
    """Quem decidiu (banca fechada) ou quem PODE decidir (banca em aberto),
    NA SESSÃO CORRENTE, pronto para a tela.

    ⚠ Filtrado por sessão pela mesma razão de `avaliacao.sessao`: uma
    assinatura dada antes de uma remarcação (2ª banca) não pode contar como
    válida para a tentativa nova, que ninguém revisou de novo.

    ⭐ **Qualquer um decide sozinho** (§5.5, §8): assim que alguém aprova ou
    reprova, `banca.resultado` fecha e nenhuma outra decisão é aceita — então,
    na prática, uma banca ainda "esperando aprovação" nunca tem nenhuma linha
    de `banca_aprovacao` registrada. `possiveis_gerentes` existe para esse
    caso: mostra quem PODERIA aprovar por aquela frente, para a tela dizer
    "diretoria ou o gerente de Tech (Fulano)" em vez de deixar a pessoa sem
    saber a quem procurar.
    """
    numero = sessao_corrente(db, banca.id)
    frentes_da_banca = _frentes_da_banca(db, banca.id)

    linhas = BancaAprovacaoRepository(db).get_by_banca(banca.id, sessao=numero)
    diretoria_linha = next((l for l in linhas if l.papel == "diretoria"), None)
    gerente_linhas = {l.frente_id: l for l in linhas if l.papel == "gerente"}

    usuario_repository = UsuarioRepository(db)
    frente_repository = FrenteRepository(db)

    def nome_usuario(usuario_id):
        u = usuario_repository.get_by_id(usuario_id) if usuario_id else None
        return u.nome if u else None

    aprovacao_gerente = []
    for frente_id in frentes_da_banca:
        frente = frente_repository.get_by_id(frente_id)
        linha = gerente_linhas.get(frente_id)
        gerentes_vinculados = _gerentes_da_frente(db, frente_id)
        aprovacao_gerente.append(
            {
                "frente_id": frente_id,
                "frente_nome": frente.nome if frente else f"frente {frente_id}",
                "aprovado": linha.aprovado if linha else None,
                "usuario_nome": nome_usuario(linha.usuario_id) if linha else None,
                "em": linha.criado_em if linha else None,
                "nota": linha.nota if linha else None,
                # ⭐ Quem PODE aprovar por esta frente — a lista real de
                # gerentes vinculados, ou o fallback de gerentes do sistema
                # quando ninguém está vinculado ainda.
                "possiveis_gerentes": [
                    u.nome for u in (gerentes_vinculados or _possiveis_gerentes(db))
                ],
            }
        )
    aprovacao_gerente.sort(key=lambda x: x["frente_nome"])

    return {
        "resultado": banca.resultado,
        "aprovacao_diretoria": (
            {
                "aprovado": diretoria_linha.aprovado,
                "usuario_nome": nome_usuario(diretoria_linha.usuario_id),
                "em": diretoria_linha.criado_em,
                "nota": diretoria_linha.nota,
            }
            if diretoria_linha
            else None
        ),
        "aprovacao_gerente": aprovacao_gerente,
    }


class RegistrarAprovacaoBancaRequest(BaseModel):
    aprovado: bool
    nota: Optional[str] = None


class RegistrarAprovacaoBancaUseCase:
    """O botão único de decisão — resolve sozinho se quem chamou é a
    diretoria ou o gerente de qual frente, e fecha o resultado na hora: não
    espera nenhuma outra parte responder."""

    def __init__(self, db: Session):
        self.db = db
        self.banca_repository = BancaRepository(db)
        self.aprovacao_repository = BancaAprovacaoRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)

    def execute(self, banca_id: int, request: RegistrarAprovacaoBancaRequest, current_user):
        banca = self.banca_repository.get_by_id(banca_id)
        if not banca:
            return None
        if not banca.realizado_em:
            raise RegraDeNegocioError(
                "Registre primeiro que a banca foi realizada, depois a aprovação"
            )
        # 🔒 Resultado fechado é definitivo — o primeiro a decidir vale, e
        # ninguém decide por cima depois.
        if banca.resultado is not None:
            raise RegraDeNegocioError("Esta banca já tem resultado registrado")

        frentes_da_banca = _frentes_da_banca(self.db, banca_id)
        numero = sessao_corrente(self.db, banca_id)

        if eh_diretoria_de_projetos(current_user):
            self.aprovacao_repository.registrar(
                banca_id, "diretoria", None, numero, current_user.id, request.aprovado, request.nota
            )
        elif getattr(current_user, "posicao", None) == "gerente":
            minhas = set(frentes_do_usuario(current_user, self.db))
            aplicaveis = minhas & set(frentes_da_banca)
            if not aplicaveis:
                raise RegraDeNegocioError(
                    "Você não é gerente de nenhuma frente desta banca"
                )
            # ⚠ Um gerente pode responder por mais de uma frente (projeto
            # sinérgico com a mesma pessoa nas duas) — registra em todas, mas
            # a decisão já fecha o resultado sozinha, sem esperar as outras.
            for frente_id in aplicaveis:
                self.aprovacao_repository.registrar(
                    banca_id, "gerente", frente_id, numero, current_user.id, request.aprovado, request.nota
                )
        else:
            raise RegraDeNegocioError(
                "Só diretoria de projetos ou gerente da frente decidem a aprovação desta banca"
            )

        # ⭐ Qualquer um decide sozinho — a decisão de quem acabou de agir já
        # fecha o resultado, sem combinar com outras assinaturas.
        banca = self.banca_repository.update(
            banca_id, resultado=apurar_aprovacao(request.aprovado)
        )
        registrar_resultado_na_sessao(self.sessao_repository, banca)

        return {"banca_id": banca_id, **montar_situacao_aprovacao(self.db, banca)}


class ListarBancasEsperandoAprovacaoUseCase:
    """A fila "Esperando aprovação" da aba Bancas — diretoria vê tudo, gerente
    só as bancas com frente dele."""

    def __init__(self, db: Session):
        self.db = db
        self.banca_repository = BancaRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)

    def execute(self, current_user) -> List[dict]:
        eh_diretoria = eh_diretoria_de_projetos(current_user)
        minhas_frentes = (
            set(frentes_do_usuario(current_user, self.db))
            if getattr(current_user, "posicao", None) == "gerente"
            else set()
        )
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}

        linhas = []
        for banca in self.banca_repository.get_realizadas_sem_resultado():
            escopo_ids = self.banca_escopo_repository.get_escopo_ids(banca.id)
            escopos = [e for e in (self.escopo_repository.get_by_id(i) for i in escopo_ids) if e]
            projeto_id = escopos[0].projeto_id if escopos else None

            if not eh_diretoria:
                if projeto_id is None:
                    continue  # banca legada: só a diretoria decide essas
                if not (set(_frentes_da_banca(self.db, banca.id)) & minhas_frentes):
                    continue

            projeto = self.projeto_repository.get_by_id(projeto_id) if projeto_id else None
            linhas.append(
                {
                    "banca_id": banca.id,
                    "projeto_id": projeto_id,
                    "projeto_nome": projeto.nome if projeto else banca.nome_projeto,
                    "escopos": [nome_do_escopo(e, catalogo) for e in escopos],
                    "realizado_em": banca.realizado_em,
                    **montar_situacao_aprovacao(self.db, banca),
                }
            )
        # A mais antiga primeiro: é a que está esperando há mais tempo.
        return sorted(linhas, key=lambda x: x["realizado_em"])

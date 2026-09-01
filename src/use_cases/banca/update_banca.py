from typing import List, Optional
from datetime import datetime
from sqlalchemy import delete
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.models.projeto_remarcacao_banca_model import ProjetoRemarcacaoBancaModel
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.escopos_da_banca import resolver_escopos
from src.use_cases.banca.excecao_choque import checar_choque
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import normalizar_utc
from src.utils.notificar import notificar


class UpdateBancaRequest(BaseModel):
    nome_projeto: Optional[str] = None
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None
    #: Só a diretoria altera — ver `require_diretor_projetos` no use case.
    piso_minimo_override: Optional[int] = None
    #: ⭐ Os escopos vendidos que esta banca cobre (2026-09-01). A lista
    #: SUBSTITUI a atual: o que não vier é removido, o que vier de novo é
    #: acrescentado. `None` = não mexer, que é o que toda edição que só troca
    #: nome ou coordenador manda.
    #:
    #: ⚠ Não confundir com `escopo_id`, que é o escopo do CATÁLOGO e é só um
    #: rótulo da banca legada.
    projeto_escopo_ids: Optional[List[int]] = None


class UpdateBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)

    def execute(self, banca_id: int, request: UpdateBancaRequest, eh_diretor_projetos: bool = False):
        data = request.dict(exclude_unset=True)

        if "piso_minimo_override" in data and not eh_diretor_projetos:
            raise RegraDeNegocioError("Só a diretoria pode alterar o piso mínimo de uma banca")

        existente = self.repository.get_by_id(banca_id)
        if not existente:
            return None

        escopo_ids = self.banca_escopo_repository.get_escopo_ids(banca_id)

        # ⚠ ANTES de qualquer comparação: o front manda `toISOString()`, que
        # chega como datetime COM fuso, e a coluna devolve SEM. Comparados
        # crus, os dois nunca são iguais — as duas guardas abaixo disparavam em
        # toda edição, mesmo quando a data não tinha sido tocada, e o botão
        # Editar da tela de Bancas não salvava nada, de campo nenhum.
        if "data_hora" in data:
            data["data_hora"] = normalizar_utc(data["data_hora"])
        data_mudou = "data_hora" in data and data["data_hora"] != existente.data_hora

        # 🔒 §5.6: remarcar a banca de um escopo nunca é silenciosa — exige
        # diretoria e justificativa. Esta rota é a genérica do módulo legado
        # e não tem como cumprir isso, então ela para aqui e manda usar o
        # cronograma, que impõe a regra.
        if escopo_ids and data_mudou:
            raise RegraDeNegocioError(
                "Para mudar a data desta banca, use o cronograma do projeto: "
                "remarcar exige justificativa e autorização da diretoria. "
                "Os outros campos podem ser editados por aqui."
            )

        # 🔒 §8 também aqui: a banca LEGADA (sem escopo) escapa do bloco acima e
        # tinha caminho livre para ser movida para cima de outra banca. A regra
        # do choque vale para toda porta que grava `data_hora`.
        if data_mudou:
            checar_choque(
                self.db,
                data["data_hora"],
                banca_repository=self.repository,
                ignorar_banca_id=banca_id,
                projeto_escopo_id=escopo_ids[0] if escopo_ids else None,
            )

        # Os escopos saem de `data` antes do update: eles não são coluna de
        # `banca`, moram em `banca_escopo`.
        escopos_pedidos = data.pop("projeto_escopo_ids", None)
        if escopos_pedidos is not None:
            escopo_ids = self._trocar_escopos(existente, escopo_ids, escopos_pedidos)

        banca = self.repository.update(banca_id, **data)
        if not banca:
            return None

        # ⭐ Quem foi escalado tem de saber que a banca mudou — a agenda dele
        # mexeu sem que ele pedisse. Antes, editar era silencioso: a pessoa
        # aparecia no dia e no horário antigos.
        notificar_alocados(
            self.db,
            banca,
            f"A banca de {banca.nome_projeto} foi editada. Confira os dados em Bancas.",
        )
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            "projeto_escopo_ids": escopo_ids,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            "piso_minimo_override": banca.piso_minimo_override,
        }


    def _trocar_escopos(self, banca, atuais, pedidos) -> list:
        """⭐ Troca os escopos que a banca cobre — a lista SUBSTITUI a antiga.

        A validação (mesmo projeto, escopo sem outra banca) mora em
        `utils/escopos_da_banca`, compartilhada com a marcação pelo cronograma.

        ⚠ **Uma banca com escopos não pode ficar sem nenhum.** Ela existe para
        avaliar um trabalho; esvaziá-la a deixaria órfã, invisível no
        cronograma de todos os escopos e sem nada que a apague. Para desfazer,
        o caminho é excluir a banca.

        ⚠ **As frentes são RECALCULADAS a partir dos escopos.** A banca é das
        frentes do trabalho que ela avalia (§8), e é isso que decide o piso
        que a composição vai cobrar. Sem remover a frente do escopo que saiu,
        a banca continuaria exigindo gente de uma frente que ela não avalia
        mais — e ficaria impossível de fechar.
        """
        if atuais and not pedidos:
            raise RegraDeNegocioError(
                "Uma banca precisa cobrir ao menos um escopo. Para desfazê-la, "
                "exclua a banca."
            )
        if not pedidos:
            return atuais

        # O projeto é o dos escopos que a banca já cobre; sendo legada (sem
        # nenhum), passa a ser o do primeiro escopo pedido.
        if atuais:
            referencia = self.escopo_repository.get_by_id(atuais[0])
        else:
            referencia = self.escopo_repository.get_by_id(sorted(pedidos)[0])
        if not referencia:
            raise RegraDeNegocioError("Escopo não encontrado")

        escopos = resolver_escopos(
            pedidos,
            projeto_id=referencia.projeto_id,
            banca_id=banca.id,
            escopo_repository=self.escopo_repository,
            catalogo_repository=self.catalogo_repository,
            banca_escopo_repository=self.banca_escopo_repository,
        )
        self.banca_escopo_repository.definir(banca.id, [e.id for e in escopos])
        self._recalcular_frentes(banca.id, {e.frente_id for e in escopos})
        return [e.id for e in escopos]

    def _recalcular_frentes(self, banca_id: int, frente_ids: set) -> None:
        """As frentes da banca passam a ser exatamente as dos escopos dela.

        Diferente de `marcar_banca_escopo._garantir_frentes`, que só ADICIONA:
        lá o gesto é marcar a data e tirar uma frente seria efeito colateral;
        aqui o gesto é justamente dizer quais escopos a banca cobre.

        Quem já se inscreveu não é desinscrito: `candidatura` é por banca, não
        por frente. O que muda é o piso que a composição cobra.
        """
        atuais = {v.frente_id: v for v in self.banca_frente_repository.get_by_banca(banca_id)}
        for frente_id in frente_ids - set(atuais):
            self.banca_frente_repository.create(banca_id=banca_id, frente_id=frente_id)
        for frente_id in set(atuais) - frente_ids:
            self.banca_frente_repository.delete(atuais[frente_id].id)


class DeleteBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int) -> bool:
        # ⚠ Avisar ANTES de apagar: depois do delete não há mais como saber
        # quem estava escalado — a candidatura vai junto.
        banca = self.repository.get_by_id(banca_id)
        if banca:
            notificar_alocados(
                self.db,
                banca,
                f"A banca de {banca.nome_projeto} foi cancelada e não acontecerá mais.",
            )
        # ⚠ `projeto_remarcacao_banca.banca_id` não cascateia (mesmo motivo
        # documentado em `delete_projeto.py`): uma banca já remarcada alguma
        # vez travava aqui com IntegrityError, e o 503 na tela não dizia por
        # quê. As outras tabelas filhas (banca_escopo, candidatura,
        # avaliacao+nota, banca_frente) já cascateiam sozinhas.
        self.db.execute(
            delete(ProjetoRemarcacaoBancaModel).where(ProjetoRemarcacaoBancaModel.banca_id == banca_id)
        )
        return self.repository.delete(banca_id)


def notificar_alocados(db: Session, banca, mensagem: str) -> None:
    """Avisa quem está escalado nesta banca.

    ⭐ Editar e excluir mexem na agenda de quem foi escalado sem que ele tenha
    pedido — o §8 trata escalação como compromisso, e compromisso que muda em
    silêncio é falta anunciada. A remarcação pelo cronograma já avisava
    (`notificar_banca_remarcada`); estas duas portas não avisavam ninguém.
    """
    from src.repositories.candidatura_repository import CandidaturaRepository

    for candidatura in CandidaturaRepository(db).get_by_banca(banca.id):
        notificar(
            db,
            candidatura.usuario_id,
            mensagem,
            banca_id=banca.id,
            tipo="banca_aviso",
        )
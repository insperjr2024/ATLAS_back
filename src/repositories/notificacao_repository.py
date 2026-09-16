from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from src.models.notificacao_model import NotificacaoModel
from src.repositories.base_repository import BaseRepository

#: 🔄 Só estes dois tipos de CONDIÇÃO chegam a tentar e-mail
#: (`rodar_lembrete_condicoes`, em `app.py`) — os demais (`kickoff_pendente`,
#: `banca_nao_marcada`, `projeto_sem_reuniao`) só nascem quando a PESSOA
#: dispensa (`marcar_condicao_lida`), sem `enfileirar` nenhum: `email_enviado_
#: em` nulo neles é o estado normal para sempre, não uma falha a repescar.
_TIPOS_DE_CONDICAO_COM_EMAIL = ("tarefa_vencida", "banca_hoje")


class NotificacaoRepository(BaseRepository[NotificacaoModel]):
    model = NotificacaoModel

    def get_eventos(self, usuario_id: int) -> List[NotificacaoModel]:
        """Os 📌 eventos do usuário, mais recentes primeiro.

        Só `origem="evento"`: linhas de `condicao` não são notificações, são
        marcações de leitura — servir uma delas mostraria "kickoff pendente"
        de um projeto cujo kickoff já foi marcado.
        """
        return (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.usuario_id == usuario_id,
                NotificacaoModel.origem == "evento",
            )
            .order_by(NotificacaoModel.criado_em.desc(), NotificacaoModel.id.desc())
            .all()
        )

    def get_leituras_de_condicao(self, usuario_id: int) -> Dict[str, datetime]:
        """`chave_dedup → lida_em` das condições que o usuário já dispensou.

        É o único uso das linhas `origem="condicao"`: a condição em si é
        recalculada a cada leitura, e este mapa só diz quais delas param de
        contar no sino.
        """
        linhas = (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.usuario_id == usuario_id,
                NotificacaoModel.origem == "condicao",
            )
            .all()
        )
        return {linha.chave_dedup: linha.lida_em for linha in linhas}

    def get_by_usuario(self, usuario_id: int) -> List[NotificacaoModel]:
        """Tudo do usuário, sem filtrar origem.

        Sobrevivente da versão de bancas desta tabela. Continua aqui porque é
        uma pergunta legítima ("o que existe para esta pessoa?"), mas o sino
        NÃO deve usá-la: servir uma linha `origem="condicao"` mostraria
        "kickoff pendente" de um projeto cujo kickoff já foi marcado. Quem
        monta a central é `ListarNotificacoesUseCase`.
        """
        return (
            self.db.query(NotificacaoModel)
            .filter(NotificacaoModel.usuario_id == usuario_id)
            .all()
        )

    def get_por_chave(self, usuario_id: int, chave_dedup: str) -> Optional[NotificacaoModel]:
        return (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.usuario_id == usuario_id,
                NotificacaoModel.chave_dedup == chave_dedup,
            )
            .first()
        )

    def get_pendentes_de_email(self, desde: datetime) -> List[NotificacaoModel]:
        """Eventos recentes cujo e-mail nunca saiu — nem tentativa registrada
        no Resend, nem carimbo aqui (ver `reenviar_pendentes.py`).

        ⚠ **`email_enviado_em` nulo não é sempre falha.** Duas situações
        legítimas se parecem exatamente com uma falha e por isso ficam de
        fora daqui:

        1. **`tipo="troca_banca"` do broadcast pro pool elegível**
           (`create_solicitacao_troca._notificar_elegiveis`) passa
           `enviar_email=False` de propósito — é aviso de massa, mandar
           e-mail a cada pedido de troca lotaria a caixa de quem não tem nada
           a ver com aquela banca. Só ESTE tipo tem chamada com a flag
           desligada hoje, mas outras chamadas do MESMO tipo (convite direto
           de troca) querem e-mail — sem uma coluna própria pra guardar a
           intenção, a única distinção segura é excluir o tipo inteiro:
           perde-se a repescagem de um convite direto que falhe de verdade,
           channel que já é opcional (`TIPOS_NOTIFICACAO_OPCIONAIS`).
        2. **Linha de `origem="condicao"`** nasce ao a PESSOA dispensar um
           alerta (`marcar_condicao_lida`) — não é notificação, é marcação de
           leitura, e nunca tenta e-mail. Só `tarefa_vencida`/`banca_hoje`
           fogem disso: `rodar_lembrete_condicoes` os cria com e-mail junto.
        """
        return (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.email_enviado_em.is_(None),
                NotificacaoModel.criado_em >= desde,
                NotificacaoModel.tipo != "troca_banca",
                or_(
                    NotificacaoModel.origem == "evento",
                    NotificacaoModel.tipo.in_(_TIPOS_DE_CONDICAO_COM_EMAIL),
                ),
            )
            .all()
        )

    def criar_se_nao_existe(self, **kwargs) -> Optional[NotificacaoModel]:
        """Insere o evento; devolve `None` se aquele usuário já o tem.

        A checagem prévia resolve o caso comum e o `IntegrityError` resolve a
        corrida: sem ele, dois cliques simultâneos em "salvar equipe" passariam
        os dois pelo `get_por_chave` antes de qualquer um gravar, e o segundo
        estouraria a rota inteira em vez de virar um no-op.
        """
        existente = self.get_por_chave(kwargs["usuario_id"], kwargs["chave_dedup"])
        if existente:
            return None
        try:
            return self.create(**kwargs)
        except IntegrityError:
            self.db.rollback()
            return None

    def marcar_lida(self, notificacao_id: int, usuario_id: int, agora: datetime):
        """Só o dono marca a própria notificação — o `usuario_id` no filtro é
        a autorização, não um detalhe da consulta."""
        linha = (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.id == notificacao_id,
                NotificacaoModel.usuario_id == usuario_id,
            )
            .first()
        )
        if not linha:
            return None
        if linha.lida_em is None:
            linha.lida_em = agora
            self.db.commit()
            self.db.refresh(linha)
        return linha

    def marcar_condicao_lida(
        self,
        usuario_id: int,
        chave_dedup: str,
        tipo: str,
        titulo: str,
        projeto_id: Optional[int],
        agora: datetime,
    ) -> NotificacaoModel:
        """Dispensa uma 🔄 condição, criando a linha se ela ainda não existir.

        Ao contrário do evento, aqui a linha nasce **no clique**, não quando o
        problema apareceu: até alguém dispensar, a condição não tem por que
        ocupar espaço no banco.
        """
        existente = self.get_por_chave(usuario_id, chave_dedup)
        if existente:
            if existente.lida_em is None:
                existente.lida_em = agora
                self.db.commit()
                self.db.refresh(existente)
            return existente
        try:
            return self.create(
                usuario_id=usuario_id,
                tipo=tipo,
                origem="condicao",
                titulo=titulo,
                projeto_id=projeto_id,
                chave_dedup=chave_dedup,
                lida_em=agora,
            )
        except IntegrityError:
            # Corrida com outra aba do mesmo usuário: a outra ganhou e a linha
            # já está marcada como lida, que é exatamente o que se queria.
            self.db.rollback()
            return self.get_por_chave(usuario_id, chave_dedup)

    def marcar_eventos_lidos(self, usuario_id: int, agora: datetime) -> int:
        atualizadas = (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.usuario_id == usuario_id,
                NotificacaoModel.origem == "evento",
                NotificacaoModel.lida_em.is_(None),
            )
            .update({NotificacaoModel.lida_em: agora}, synchronize_session=False)
        )
        self.db.commit()
        return atualizadas

    def get_evento_do_usuario(
        self, notificacao_id: int, usuario_id: int
    ) -> Optional[NotificacaoModel]:
        """Só `origem="evento"`: uma linha de `condicao` não é a notificação,
        é a marcação de leitura dela, apagá-la faz o alerta voltar a contar
        no sino mesmo com o problema continuando resolvido."""
        return (
            self.db.query(NotificacaoModel)
            .filter(
                NotificacaoModel.id == notificacao_id,
                NotificacaoModel.usuario_id == usuario_id,
                NotificacaoModel.origem == "evento",
            )
            .first()
        )

    def excluir(self, linha: NotificacaoModel) -> None:
        self.db.delete(linha)
        self.db.commit()

    def limpar_eventos_lidos(self, usuario_id: int) -> int:
        linhas = self.db.query(NotificacaoModel).filter(
            NotificacaoModel.usuario_id == usuario_id,
            NotificacaoModel.origem == "evento",
            NotificacaoModel.lida_em.isnot(None),
        )
        total = linhas.count()
        linhas.delete(synchronize_session=False)
        self.db.commit()
        return total

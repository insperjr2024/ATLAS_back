"""Lembretes de local da banca, na contagem regressiva (2026-09-10, a pedido).

Banca SEM local registrado — a cobrança vai abrindo o público:

    ~24h antes ..... COORDENADORES do projeto
    ~12h antes ..... TODOS do projeto
    ~2h antes ...... TODOS do projeto

E a ~1h antes (com ou sem local), um aviso pra TODOS QUE VÃO ASSISTIR (os
avaliadores escalados, menos o time do projeto), com o local — ou, se ainda
não tiver, "NÃO INFORMADO — vejam com os coordenadores".

Dedup por `chave`: cada aviso sai uma vez só, mesmo o job rodando de 5 em 5
min. Rodado pelo agendador (`src/app.py::rodar_lembrete_local_banca`).
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.use_cases.banca.local_e_entrega import (
    coordenadores_do_projeto_da_banca,
    pessoas_do_projeto_da_banca,
)
from src.utils.fuso import agora_utc, para_hora_local
from src.utils.notificar import notificar


class LembreteLocalBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.banca_repo = BancaRepository(db)
        self.cand_repo = CandidaturaRepository(db)

    def execute(self) -> int:
        agora = agora_utc()
        avisos = 0
        for banca in self.banca_repo.get_all():
            if (
                not banca.data_hora
                or banca.realizado_em
                or getattr(banca, "cancelada_em", None)
            ):
                continue
            faltando = banca.data_hora - agora
            if faltando <= timedelta(0):
                continue
            avisos += self._avisar_uma(banca, faltando)
        return avisos

    def _avisar_uma(self, banca, faltando: timedelta) -> int:
        avisos = 0
        nome = banca.nome_projeto
        tem_local = bool((getattr(banca, "local", None) or "").strip())

        if not tem_local:
            destino, msg, chave = self._cobranca_de_local(banca, faltando, nome)
            if msg:
                for uid in destino:
                    notificar(self.db, uid, msg, banca_id=banca.id, chave=chave)
                    avisos += 1

        if faltando <= timedelta(hours=1):
            avisos += self._avisar_quem_vai_assistir(banca, nome)

        return avisos

    def _cobranca_de_local(self, banca, faltando: timedelta, nome: str):
        """(destinatários, mensagem, chave) do lembrete da vez — ou
        (vazio, None, None) fora das janelas."""
        if timedelta(hours=12) < faltando <= timedelta(hours=24):
            return (
                coordenadores_do_projeto_da_banca(self.db, banca),
                f"A banca de {nome} é amanhã e ainda não tem local no Atlas. "
                "Registrem onde vai ser na aba Bancas do projeto.",
                f"local_falta_24h:banca={banca.id}",
            )
        if timedelta(hours=2) < faltando <= timedelta(hours=12):
            return (
                pessoas_do_projeto_da_banca(self.db, banca),
                f"A banca de {nome} é em algumas horas e ainda não tem local no "
                "Atlas. Registrem onde vai ser na aba Bancas do projeto.",
                f"local_falta_12h:banca={banca.id}",
            )
        if timedelta(hours=1) < faltando <= timedelta(hours=2):
            return (
                pessoas_do_projeto_da_banca(self.db, banca),
                f"A banca de {nome} é em cerca de 2h e SEGUE sem local no Atlas. "
                "Registrem agora — o campo tranca 1h antes da banca.",
                f"local_falta_2h:banca={banca.id}",
            )
        return set(), None, None

    def _avisar_quem_vai_assistir(self, banca, nome: str) -> int:
        quando = para_hora_local(banca.data_hora).strftime("%d/%m às %H:%M")
        onde = (getattr(banca, "local", None) or "").strip()
        if onde:
            corpo = f"A banca de {nome} está chegando: {quando}, em {onde}."
        else:
            corpo = (
                f"A banca de {nome} está chegando: {quando}. Local: NÃO INFORMADO "
                "— vejam com os coordenadores do projeto."
            )
        # Quem vai ASSISTIR = candidatos escalados, menos quem é do projeto (o
        # time do projeto recebeu a cobrança acima, não este aviso).
        time_projeto = pessoas_do_projeto_da_banca(self.db, banca)
        escalados = {
            c.usuario_id for c in self.cand_repo.get_by_banca(banca.id)
        } - time_projeto
        for uid in escalados:
            notificar(
                self.db, uid, corpo,
                banca_id=banca.id,
                chave=f"local_avaliadores:banca={banca.id}",
            )
        return len(escalados)

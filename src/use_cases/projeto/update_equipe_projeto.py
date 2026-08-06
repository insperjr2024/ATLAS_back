from datetime import date
from typing import List

from pydantic import BaseModel

from sqlalchemy.orm import Session

from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.eventos import notificar_alocacao
from src.utils.exceptions import RegraDeNegocioError
from src.utils.validacao_equipe import validar_equipe


class MembroEquipeRequest(BaseModel):
    usuario_id: int
    papel: str


class UpdateEquipeProjetoRequest(BaseModel):
    equipe: List[MembroEquipeRequest]


class UpdateEquipeProjetoUseCase:
    """Editar a equipe é sempre editável (§6.4) — trocar alguém preenche
    `saiu_em` da linha antiga e cria outra nova; nunca sobrescreve (§10: o
    histórico de quem participou não pode ser reescrito)."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoMembroRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, projeto_id: int, request: UpdateEquipeProjetoRequest):
        projeto = self.projeto_repository.get_by_id(projeto_id)
        if not projeto:
            return None

        validar_equipe(request.equipe, self.usuario_repository)

        atuais = self.repository.get_by_projeto(projeto_id, apenas_atuais=True)
        ids_novos = {m.usuario_id for m in request.equipe}
        hoje = date.today()

        # Quem saiu: fecha a linha (não apaga — §10).
        for atual in atuais:
            if atual.usuario_id not in ids_novos:
                self.repository.update(atual.id, saiu_em=hoje)

        # Quem entrou ou trocou de papel: fecha a linha antiga (se houver
        # mudança de papel) e abre uma nova.
        ids_atuais_por_papel = {m.usuario_id: m.papel for m in atuais}
        for membro in request.equipe:
            papel_atual = ids_atuais_por_papel.get(membro.usuario_id)
            if papel_atual is None:
                self.repository.create(
                    projeto_id=projeto_id,
                    usuario_id=membro.usuario_id,
                    papel=membro.papel,
                    entrou_em=hoje,
                )
                notificar_alocacao(self.db, projeto, membro.usuario_id)
            elif papel_atual != membro.papel:
                linha_atual = next(a for a in atuais if a.usuario_id == membro.usuario_id)
                self.repository.update(linha_atual.id, saiu_em=hoje)
                self.repository.create(
                    projeto_id=projeto_id,
                    usuario_id=membro.usuario_id,
                    papel=membro.papel,
                    entrou_em=hoje,
                )

        return {
            "equipe": [
                {"usuario_id": m.usuario_id, "papel": m.papel}
                for m in self.repository.get_by_projeto(projeto_id, apenas_atuais=True)
            ]
        }

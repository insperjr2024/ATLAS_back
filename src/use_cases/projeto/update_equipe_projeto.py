from datetime import date
from typing import List, Optional

from pydantic import BaseModel

from sqlalchemy.orm import Session

from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
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
    #: ⭐ Quem VENDEU o projeto. Zero ou mais, e não faz parte da equipe — vem
    #: junto porque é a mesma tela e a mesma permissão (`pode_editar_equipe`),
    #: não porque seja time.
    #:
    #: `None` (o padrão) significa "não mexa nos vendedores", diferente de `[]`,
    #: que significa "apague todos". Sem essa distinção, qualquer tela que
    #: salvasse só a equipe apagaria os vendedores em silêncio.
    vendedor_ids: Optional[List[int]] = None


class UpdateEquipeProjetoUseCase:
    """Editar a equipe é sempre editável (§6.4) — trocar alguém preenche
    `saiu_em` da linha antiga e cria outra nova; nunca sobrescreve (§10: o
    histórico de quem participou não pode ser reescrito)."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoMembroRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.vendedor_repository = ProjetoVendedorRepository(db)

    def execute(
        self,
        projeto_id: int,
        request: UpdateEquipeProjetoRequest,
        registrado_por: Optional[int] = None,
    ):
        projeto = self.projeto_repository.get_by_id(projeto_id)
        if not projeto:
            return None

        validar_equipe(request.equipe, self.usuario_repository, projeto.max_consultores)

        if request.vendedor_ids is not None:
            self._definir_vendedores(projeto_id, request.vendedor_ids, registrado_por)

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

    def _definir_vendedores(self, projeto_id: int, usuario_ids, registrado_por):
        """Valida e grava a lista de vendedores.

        Duas regras, as duas sobre existir de verdade: a pessoa precisa existir
        e estar ativa. Um id solto viraria uma linha órfã que a ficha do projeto
        mostraria como nome em branco.
        """
        vistos = set()
        for usuario_id in usuario_ids:
            if usuario_id in vistos:
                raise RegraDeNegocioError("A mesma pessoa aparece duas vezes como vendedora")
            vistos.add(usuario_id)
            usuario = self.usuario_repository.get_by_id(usuario_id)
            if not usuario:
                raise RegraDeNegocioError("Vendedor(a) não encontrado(a)")
            if usuario.status != "ativo":
                raise RegraDeNegocioError(
                    f"{usuario.nome} não está ativo(a) e não pode ser marcado(a) como vendedor(a)"
                )
        self.vendedor_repository.definir(projeto_id, list(vistos), registrado_por)

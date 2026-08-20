"""A passagem de bastão da diretoria (§10).

A virada de gestão acontece todo ano, e antes disso ela dependia de duas
edições soltas na tela de Membros — promover a pessoa nova e rebaixar a
antiga. Entre uma e outra a plataforma podia ficar com dois diretores ou com
nenhum, e nada garantia que o histórico registrasse a troca.

Aqui é um passo só, com a garantia que importa: nunca sobra zero na diretoria
que está sendo passada.

⭐ **`posicao` é escolhida por quem chama** desde a divisão em três cargos
(2026-08-20). Antes a rota só sabia passar `diretor`, que era o cargo único.
Agora cada diretoria troca de mão pelo mesmo caminho, com a mesma garantia —
e a virada anual, em que as três costumam trocar juntas, são três chamadas
independentes em vez de uma edição solta por pessoa na tela de Membros.
"""

from typing import Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.usuario_posicao_historico_model import UsuarioPosicaoHistoricoModel
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError

#: Só para a mensagem de erro. O rótulo bonito da tela mora no front; aqui é o
#: mínimo para a recusa dizer de qual diretoria ela está falando.
ROTULO = {
    "diretor_projetos": "a diretoria de projetos",
    "diretor_pessoas": "a diretoria de gestão de pessoas",
    "diretor": "a diretoria",
}


class TransferirDiretoriaRequest(BaseModel):
    novo_diretor_id: int
    diretor_atual_id: int
    #: Qual diretoria está sendo passada. Sem padrão de propósito: adivinhar
    #: aqui seria passar o cargo errado em silêncio, e a operação não tem
    #: desfazer — ela desativa a pessoa que sai.
    posicao: Literal["diretor_projetos", "diretor_pessoas", "diretor"]


class TransferirDiretoriaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UsuarioRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def _registrar(self, usuario_id: int, posicao: str, alterado_por: Optional[int]):
        semestre = self.semestre_repository.get_ativo()
        self.db.add(
            UsuarioPosicaoHistoricoModel(
                usuario_id=usuario_id,
                posicao=posicao,
                semestre_id=semestre.id if semestre else None,
                alterado_por=alterado_por,
            )
        )

    def execute(self, request: TransferirDiretoriaRequest, alterado_por: Optional[int] = None):
        if request.novo_diretor_id == request.diretor_atual_id:
            raise RegraDeNegocioError("Escolha uma pessoa diferente para receber a diretoria")

        novo = self.repository.get_by_id(request.novo_diretor_id)
        if not novo:
            raise RegraDeNegocioError("Usuário que receberia a diretoria não encontrado")
        if novo.status != "ativo":
            raise RegraDeNegocioError(
                f"{novo.nome} não está ativo na plataforma e não pode assumir a diretoria"
            )

        atual = self.repository.get_by_id(request.diretor_atual_id)
        if not atual:
            raise RegraDeNegocioError("Diretor(a) atual não encontrado")
        if atual.posicao != request.posicao:
            raise RegraDeNegocioError(
                f"{atual.nome} não ocupa {ROTULO[request.posicao]} hoje"
            )

        # A pessoa que entra vira diretora ANTES de a que sai ser desligada,
        # para nenhum instante da transação existir sem diretoria.
        self.repository.update(novo.id, posicao=request.posicao)
        self._registrar(novo.id, request.posicao, alterado_por)

        # Quem sai vira ex-membro: é exatamente o caso de "fim de gestão" do
        # §10 — perde o acesso, mantém o histórico. A `posicao` continua
        # "diretor" porque é a verdade do que a pessoa FOI, e reescrevê-la
        # faria o arquivo mentir. Quem manda no acesso é o `ativo`, que o
        # `get_current_user` checa a cada request — o token dela para de
        # valer na hora.
        self.repository.update(atual.id, status="ex_membro", ativo=False)

        self.db.commit()

        return {
            "novo_diretor": {"id": novo.id, "nome": novo.nome},
            "diretor_anterior": {"id": atual.id, "nome": atual.nome, "status": "ex_membro"},
        }

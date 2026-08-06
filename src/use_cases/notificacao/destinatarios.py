"""Quem recebe cada 📌 evento.

As 🔄 condições resolvem isso sozinhas — quem enxerga o projeto vem de
`aplicar_recorte_visao` e o papel vem de `projeto_membro`. Os eventos não:
"o escopo 2 do Beta foi entregue" precisa saber, no momento do registro, quem
é a diretoria e quem é o gerente **daquela frente**.

O recorte do §3 vale igual aqui: gerente enxerga a própria frente, então
notificar todos os gerentes vazaria projeto de frente alheia no sino deles.
"""

from typing import List

from sqlalchemy.orm import Session

from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository


def lideranca_do_projeto(db: Session, projeto_id: int) -> List[int]:
    """Diretoria + o(s) gerente(s) das frentes do projeto, só quem está ativo.

    Projeto sinérgico tem duas frentes e portanto dois gerentes — os dois
    recebem, que é o mesmo critério do monitoramento (§7.5).
    """
    usuario_repository = UsuarioRepository(db)
    frentes_do_projeto = {
        f.frente_id for f in ProjetoFrenteRepository(db).get_by_projeto(projeto_id)
    }

    destinatarios = [u.id for u in usuario_repository.get_por_posicao("diretor") if u.ativo]

    vinculo_repository = UsuarioFrenteRepository(db)
    for gerente in usuario_repository.get_por_posicao("gerente"):
        if not gerente.ativo:
            continue
        frentes = {v.frente_id for v in vinculo_repository.get_by_usuario(gerente.id)}
        if frentes & frentes_do_projeto:
            destinatarios.append(gerente.id)

    # Diretor que também é gerente de frente entraria duas vezes.
    return list(dict.fromkeys(destinatarios))

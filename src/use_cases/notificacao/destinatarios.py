"""Quem recebe cada 📌 evento — o §3 aplicado à notificação.

As 🔄 condições resolvem a visibilidade sozinhas: os projetos entram por
`aplicar_recorte_visao`, que já É o §3. Os eventos não têm essa sorte — "o
escopo 2 do Beta foi entregue" precisa saber, no momento do registro, quem
enxerga o Beta.

**Este módulo é a tradução do §3 para eventos, e é o único lugar onde ela
mora.** As três regras do briefing viram três funções:

    Coordenador e consultor → só onde estão alocados ....... `equipe_do_projeto`
    Gerente → só a própria frente (inclui sinérgicos) ...... `lideranca_do_projeto`
    Diretor → todas as frentes ............................. `lideranca_do_projeto`

Quem for adicionar um evento novo compõe a partir daqui em vez de montar a
lista de destinatários à mão — foi para isso que estas funções existem.

⚠ **Uma exceção legítima, e só uma:** notificação de BANCA vai também para
quem se inscreveu nela, que por definição (§8) NÃO é da equipe do projeto.
Não é furo no §3: o alerta fala da banca e aponta para `/bancas/{id}`, nunca
para a página do projeto. Ver `inscritos_na_banca`.
"""

from typing import List

from sqlalchemy.orm import Session

from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository


def equipe_do_projeto(db: Session, projeto_id: int) -> List[int]:
    """Coordenador e consultores alocados HOJE.

    §3: "coordenador e consultor enxergam apenas os projetos em que estão
    alocados". `saiu_em` preenchido = saiu da equipe e para de receber — o
    histórico continua no banco, mas a notificação não segue quem saiu.
    """
    return [
        m.usuario_id
        for m in ProjetoMembroRepository(db).get_by_projeto(projeto_id, apenas_atuais=True)
    ]


def lideranca_do_projeto(db: Session, projeto_id: int) -> List[int]:
    """Diretoria + o(s) gerente(s) das frentes do projeto, só quem está ativo.

    §3: o diretor enxerga todas as frentes; o gerente, só a dele. Projeto
    sinérgico tem duas frentes e portanto dois gerentes — os dois recebem,
    mesmo critério do §7.5.

    Notificar TODOS os gerentes seria vazar projeto de frente alheia no sino
    de quem não pode nem abrir a página dele.
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


def todos_do_projeto(db: Session, projeto_id: int) -> List[int]:
    """Equipe + liderança — exatamente o conjunto que o §3 deixa ver o projeto.

    É o destinatário certo para o que muda o PLANO do projeto (data de banca,
    data de entrega): a equipe porque executa, a liderança porque acompanha.
    """
    return list(dict.fromkeys(equipe_do_projeto(db, projeto_id) + lideranca_do_projeto(db, projeto_id)))


def inscritos_na_banca(db: Session, banca_id: int) -> List[int]:
    """Quem se inscreveu na banca — a exceção documentada no topo do módulo.

    Uma banca remarcada precisa avisar quem reservou a agenda para ela, e
    essas pessoas são de fora do projeto por exigência do §8 ("a equipe do
    próprio projeto não pode se inscrever na sua banca"). O alerta fala da
    banca e leva para `/bancas/{id}` — nada do projeto vaza.
    """
    return [c.usuario_id for c in CandidaturaRepository(db).get_by_banca(banca_id)]

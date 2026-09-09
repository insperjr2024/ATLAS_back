"""O ponto de partida do editor de formulário de avaliação de banca.

⚠ Diferente de `GetFormularioAtivoUseCase`: aquele é estrito (nenhum ativo =
`None` = a tela de avaliação fica fechada, de propósito). ESTE nunca deixa o
editor abrir em branco quando existe conteúdo salvo em alguma versão.

O bug que motivou (2026-09-09): "Publicar nova versão" cria uma versão nova
com EXATAMENTE o que o editor mandou e desativa a anterior — sem merge. Se
alguém publica uma lista curta (ou vazia), a versão boa some da tela. Da
próxima vez o editor abria a versão ativa vazia, e republicar só empilhava
outra vazia. Semeando pelo conteúdo mais recente que EXISTE, o editor volta a
mostrar as perguntas de sempre mesmo que a versão ativa esteja zerada — quem
republicar preserva o que havia, em vez de apagar.
"""

from sqlalchemy.orm import Session

from src.repositories.formulario_repository import FormularioRepository
from src.repositories.pergunta_repository import PerguntaRepository


class GetFormularioParaEditarUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)
        self.pergunta_repository = PerguntaRepository(db)

    def _serializar(self, formulario):
        perguntas = self.pergunta_repository.get_by_formulario(formulario.id)
        return {
            "id": formulario.id,
            "semestre_id": formulario.semestre_id,
            "perguntas": [
                {
                    "id": p.id,
                    "texto": p.texto,
                    "ordem": p.ordem,
                    "tipo_resposta": p.tipo_resposta,
                    "escopo_id": p.escopo_id,
                }
                for p in perguntas
            ],
        }

    def execute(self):
        formularios = sorted(self.repository.get_all(), key=lambda f: f.id, reverse=True)
        if not formularios:
            return None

        ativo = next((f for f in formularios if f.ativo), None)

        # Preferência: a versão ativa se tiver conteúdo; senão a versão mais
        # recente (maior id) que tenha; senão a ativa mesmo que vazia; senão
        # a mais recente de todas.
        ordem_de_busca = ([ativo] if ativo else []) + [f for f in formularios if f is not ativo]
        for f in ordem_de_busca:
            if self.pergunta_repository.get_by_formulario(f.id):
                return self._serializar(f)

        return self._serializar(ativo or formularios[0])

"""⭐ A ficha de uma banca com os NOMES já resolvidos.

Existe separado do `GetBancaUseCase` porque responde outra pergunta. Aquele
devolve a banca como o módulo de bancas precisa dela — ids crus, vagas, piso,
`equipe_ids` — e quem consome monta os nomes cruzando `/usuarios`,
`/frentes`, `/candidaturas`, `/equipes-projeto` e `/bancas-frentes` do lado do
cliente. É o que a tela `/bancas` faz, e para ela faz sentido: ela já carregou
todas essas listas para desenhar os cards.

O cronograma do projeto não carregou nenhuma delas, e não deveria: puxar cinco
listagens inteiras da empresa para escrever sete linhas de uma banca é caro e
frágil. Aqui a composição acontece onde os dados já estão.

⭐ **`membros` sai de `membros_da_banca`, não de `equipe_projeto`.** Aquela
tabela é a legada do módulo de bancas, preenchida à mão; banca marcada pelo
cronograma não escreve nela. Quem lê só ela mostra "Membros —" justamente nas
bancas nascidas do fluxo novo, que são a maioria hoje. `membros_da_banca` já
sabe olhar os dois lados (ver `utils/equipe_banca.py`).
"""

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.equipe_banca import membros_da_banca


class GetBancaDetalhesUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, banca_id: int):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None

        escopos = [
            e
            for e in (
                self.escopo_repository.get_by_id(i)
                for i in self.banca_escopo_repository.get_escopo_ids(banca_id)
            )
            if e
        ]

        # O coordenador aparece na própria linha da ficha, então sai da lista
        # de membros — repetir o mesmo nome nas duas diria menos, não mais.
        equipe = membros_da_banca(
            banca,
            self.banca_escopo_repository,
            self.escopo_repository,
            self.membro_repository,
            self.equipe_projeto_repository,
        )
        equipe.discard(banca.coordenador_id)

        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "data_hora": banca.data_hora,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            # Plural: uma banca pode cobrir vários escopos do projeto de uma
            # sentada (ver `BancaEscopoModel`). Vazio nas bancas legadas, que
            # não têm linha em `banca_escopo`.
            "escopos": [self._nome_do_escopo(e) for e in escopos],
            "frentes": self._nomes_das_frentes(banca_id),
            "coordenador": self._nome(banca.coordenador_id),
            "membros": sorted(self._nome(i) for i in equipe),
            "avaliadores": sorted(
                self._nome(c.usuario_id)
                for c in self.candidatura_repository.get_by_banca(banca_id)
            ),
            "descricao_coordenador": banca.descricao_coordenador,
            # Para a tela poder linkar de volta ao projeto — a ficha é aberta
            # de dentro dele, mas a banca pode cobrir escopo de outro lugar.
            "projeto_id": escopos[0].projeto_id if escopos else None,
        }

    def _nome(self, usuario_id) -> str:
        if not usuario_id:
            return "—"
        usuario = self.usuario_repository.get_by_id(usuario_id)
        return usuario.nome if usuario else "—"

    def _nome_do_escopo(self, escopo) -> str:
        """O nome digitado quando é um "Outro", senão o do catálogo."""
        if escopo.nome_customizado:
            return escopo.nome_customizado
        do_catalogo = (
            self.catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
        )
        return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"

    def _nomes_das_frentes(self, banca_id: int) -> list:
        nomes = []
        for vinculo in self.banca_frente_repository.get_by_banca(banca_id):
            frente = self.frente_repository.get_by_id(vinculo.frente_id)
            if frente:
                nomes.append(frente.nome)
        return sorted(nomes)

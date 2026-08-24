from typing import List

from src.models.frente_model import FrenteModel
from src.repositories.base_repository import BaseRepository


class FrenteRepository(BaseRepository[FrenteModel]):
    model = FrenteModel

    def get_all(self) -> List[FrenteModel]:
        """Sempre por `id`, que é a ordem em que as frentes foram criadas.

        ⚠ O `get_all` herdado não ordena, e o Postgres devolve na ordem física
        da tabela. Isso não é estável: qualquer `UPDATE` reescreve a linha e a
        joga para o fim. Foi o que aconteceu quando a Tech ganhou
        `calendario_padrao` — ela sumiu do segundo lugar e apareceu depois de
        Direito na tela de Calendários base, sem que nada de propósito tivesse
        mudado.

        A ordem por `id` é a que as telas assumem desde sempre (Business, Tech,
        Processos, Direito) e a única que não depende de quem escreveu por
        último.
        """
        return self.db.query(FrenteModel).order_by(FrenteModel.id).all()

    def get_ativas(self) -> List[FrenteModel]:
        return [f for f in self.get_all() if f.ativa]

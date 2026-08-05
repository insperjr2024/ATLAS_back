from typing import List, Optional

from src.models.desempenho_mentoria_model import DesempenhoMentoriaModel
from src.repositories.base_repository import BaseRepository


class DesempenhoMentoriaRepository(BaseRepository[DesempenhoMentoriaModel]):
    model = DesempenhoMentoriaModel

    def get_mentor_de(self, mentorado_id: int) -> Optional[DesempenhoMentoriaModel]:
        return self.first_by(mentorado_id=mentorado_id)

    def get_mentorados_de(self, mentor_id: int) -> List[DesempenhoMentoriaModel]:
        return self.filter_by(mentor_id=mentor_id)

"""🤖 O status do projeto anda sozinho quando o FATO já aconteceu (§4).

⚠ **O problema que isto resolve.** Só uma das seis transições do ciclo era
automática (Ambientação → Em andamento, por data). Todas as outras esperavam
alguém abrir o projeto e trocar no seletor — e ninguém trocava. Na base de
teste, 5 de 29 projetos tinham banca REALIZADA e continuavam em "Em andamento";
dois deles já tinham escopo entregue ao cliente. O status virava uma etiqueta
que dizia o passado.

⭐ **Só automatiza o que tem gatilho INEQUÍVOCO no sistema.** Duas transições:

- **Em andamento → Validação em bancas**, quando a primeira banca do projeto é
  registrada como realizada. A banca acontecendo *é* a validação começando.
- **Validação em bancas (ou Envio de TEP) → Período de ajustes**, quando todos
  os escopos foram entregues ao cliente. Não há mais o que validar.

⚠ **`Envio de TEP` fica de fora de propósito.** É um documento que sai da
plataforma; nada aqui sabe se ele foi enviado. Inventar um gatilho ali faria o
sistema afirmar algo que não observou. Quem passa por ele passa à mão — e a
segunda regra aceita `envio_tep` como origem, então o projeto que foi por lá
continua avançando sozinho depois.

⚠ **`Finalizado` também fica de fora.** Encerrar um projeto é uma decisão da
diretoria, não uma consequência da última entrega: pode haver pendência
administrativa depois dela.

## Como isto convive com a mudança manual

O seletor continua valendo para tudo, nos dois sentidos. Três garantias fazem o
robô não brigar com a pessoa:

1. **Só avança UMA casa, e só a partir da origem exata.** Um projeto que alguém
   já levou adiante não é puxado de volta nem empurrado de novo.
2. **Nunca retrocede.** Nenhum fato faz o status voltar.
3. **Um retrocesso manual é respeitado.** Se a última mudança foi uma pessoa
   puxando o projeto para trás, o robô não desfaz na passada seguinte — foi uma
   decisão, não um atraso de registro. Sem isto, quem corrigisse um status
   veria a correção sumir na madrugada.

⏸ Projeto pausado não é tocado: pausar é parar o relógio, e virar o status de
quem está parado desfaria a decisão de quem pausou.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.status_projeto import STATUS_ORDEM

logger = logging.getLogger(__name__)


class AvancarStatusAutomaticoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(self) -> List[int]:
        """Varre o portfólio. Devolve os ids que avançaram — vazio é o normal."""
        avancados = []
        for projeto in self.repository.get_all():
            if self._avancar(projeto):
                avancados.append(projeto.id)
        return avancados

    def executar_para(self, projeto_id: int) -> bool:
        """A mesma regra para UM projeto.

        Chamada logo depois dos atos que são gatilho (registrar a realização de
        uma banca, marcar a entrega de um escopo), para o status virar na hora
        em vez de esperar a passada da madrugada — que é quando a pessoa está
        olhando a tela e esperando ver o efeito.
        """
        projeto = self.repository.get_by_id(projeto_id)
        return bool(projeto and self._avancar(projeto))

    # ------------------------------------------------------------------ regra

    def _avancar(self, projeto: ProjetoModel) -> bool:
        if projeto.status == "pausado":
            return False
        if self._houve_retrocesso_manual(projeto.id):
            return False

        destino = self._destino(projeto)
        if destino is None or destino == projeto.status:
            return False

        # ⚠ Guarda-corpo: nunca para trás, mesmo que uma regra futura erre a
        # conta. O status é lido pelo monitoramento e pelos filtros — retroceder
        # sozinho seria pior que ficar parado.
        if STATUS_ORDEM.index(destino) <= STATUS_ORDEM.index(projeto.status):
            return False

        anterior = projeto.status
        self.repository.update(projeto.id, status=destino)
        self.historico_repository.create(
            projeto_id=projeto.id,
            status_anterior=anterior,
            status_novo=destino,
            # 🤖 Sem autor: a convenção do sistema para "mudou sozinho". A tela
            # do Histórico lê o nulo e escreve "pelo sistema".
            alterado_por=None,
        )
        logger.info(
            "Status avançado automaticamente: projeto %s (%s) %s → %s",
            projeto.id,
            projeto.nome,
            anterior,
            destino,
        )
        return True

    def _destino(self, projeto: ProjetoModel) -> Optional[str]:
        """Para onde os FATOS dizem que este projeto deveria ter ido."""
        escopos = self.escopo_repository.get_by_projeto(projeto.id)
        if not escopos:
            return None

        # ⚠ Escopo cancelado não conta para "tudo entregue": exigir entrega de
        # algo que foi cancelado travaria o avanço para sempre.
        vivos = [e for e in escopos if e.status != "cancelado"]
        if not vivos:
            return None

        if projeto.status in ("validacao_bancas", "envio_tep"):
            if all(e.data_entrega_real for e in vivos):
                return "periodo_ajustes"
            return None

        if projeto.status == "em_andamento":
            if any(self._banca_realizada(e.id) for e in vivos):
                return "validacao_bancas"
            return None

        return None

    def _banca_realizada(self, escopo_id: int) -> bool:
        banca = self.banca_repository.get_by_projeto_escopo(escopo_id)
        return bool(banca and banca.realizado_em)

    def _houve_retrocesso_manual(self, projeto_id: int) -> bool:
        """A última mudança foi uma PESSOA puxando o projeto para trás?

        ⭐ É o que faz o automático não brigar com quem corrige. Alguém que
        devolve um projeto de "Período de ajustes" para "Em andamento" está
        dizendo que ele voltou ao trabalho; avançá-lo de novo na madrugada
        apagaria essa decisão e a pessoa veria o status "consertar-se" sozinho
        toda noite.

        Só o ÚLTIMO movimento conta: uma nova mudança manual para frente, ou uma
        virada do próprio sistema, devolve o projeto ao fluxo automático.
        """
        linhas = self.historico_repository.get_by_projeto(projeto_id)
        if not linhas:
            return False

        ultima = max(linhas, key=lambda l: (l.alterado_em, l.id))
        # Sem autor = foi o sistema; então não há decisão humana a respeitar.
        if ultima.alterado_por is None:
            return False
        if ultima.status_anterior not in STATUS_ORDEM or ultima.status_novo not in STATUS_ORDEM:
            return False
        return STATUS_ORDEM.index(ultima.status_novo) < STATUS_ORDEM.index(ultima.status_anterior)

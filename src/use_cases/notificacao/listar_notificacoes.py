"""A central de notificações do §6.6 — o que cada perfil vê no sino.

Três coisas se encontram aqui, e a ordem importa:

1. **📌 eventos** — linhas já gravadas (`alocado_em_projeto`, `entrega_registrada`,
   `escalacao_banca`). Vêm do banco como estão.
2. **🔄 condições individuais** — recalculadas por `condicoes_alerta` e
   filtradas pelo papel da pessoa NO projeto (§5.2/§5.3/§6.4).
3. **▣ agregados da liderança** — as mesmas condições, somadas numa linha por
   tipo, para diretor e gerente.

**Por que o agregado existe.** O diretor enxerga todos os projetos. Uma linha
por tarefa vencida da consultoria inteira transforma o sino em lixo eletrônico
na primeira semana — e um sino ignorado não notifica ninguém. Ele recebe
"11 tarefas vencidas" apontando para o monitoramento, que já mostra o detalhe.

**A regra de desempate:** o individual sempre ganha do agregado. Uma tarefa
vencida que é da própria pessoa chega como item próprio e **sai** da conta do
agregado — senão ela veria a mesma tarefa duas vezes.
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.repositories.notificacao_repository import NotificacaoRepository
from src.use_cases.monitoramento.monitoramento import _BaseMonitoramento, _agrupar
from src.utils.condicoes_alerta import (
    AGREGAVEIS_PARA_LIDERANCA,
    detectar_condicoes,
    para_papel,
)
from src.utils.tarefa_status import janela_semana

#: Quem vê projeto que não é seu — e por isso recebe agregado em vez de item a
#: item. Mesma fronteira de `aplicar_recorte_visao`.
POSICOES_LIDERANCA = ("diretor", "gerente")

#: O texto de cada agregado. Sem isto o front teria que montar a frase a partir
#: do `tipo`, e o e-mail da fase 2 montaria outra.
ROTULO_AGREGADO = {
    "kickoff_pendente": ("{n} projeto sem kickoff", "{n} projetos sem kickoff"),
    "tarefa_vencida": ("{n} tarefa vencida", "{n} tarefas vencidas"),
    "banca_nao_marcada": ("{n} escopo sem banca marcada", "{n} escopos sem banca marcada"),
    "projeto_sem_reuniao": (
        "{n} projeto sem reunião esta semana",
        "{n} projetos sem reunião esta semana",
    ),
}


class ListarNotificacoesUseCase(_BaseMonitoramento):
    """Herda o CARREGAMENTO do monitoramento, não as regras dele.

    `_projetos_visiveis`, `_contexto` e `_encerra_por_coluna` fazem exatamente
    as consultas que o sino precisa, com o mesmo recorte de visão. Copiá-las
    para cá seria criar a segunda régua que `condicoes_alerta` existe para
    evitar — as duas telas ficariam livres para divergir no dia em que alguém
    mexesse só de um lado.
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self.notificacao_repository = NotificacaoRepository(db)

    def execute(self, current_user, referencia: Optional[date] = None) -> dict:
        hoje = referencia or date.today()
        itens = self._condicoes_do_usuario(current_user, hoje)
        itens.extend(self._eventos(current_user))

        # Não lidas primeiro; dentro de cada grupo, o buraco maior na frente.
        itens.sort(key=lambda i: (i["lida"], i["dias"] is None, -(i["dias"] or 0)))
        return {
            "nao_lidas": sum(1 for i in itens if not i["lida"]),
            "itens": itens,
        }

    # ── 📌 eventos ───────────────────────────────────────────────────────
    def _eventos(self, current_user) -> List[dict]:
        return [
            {
                "id": linha.id,
                "chave": linha.chave_dedup,
                "tipo": linha.tipo,
                "origem": "evento",
                "titulo": linha.titulo,
                "corpo": linha.corpo,
                "projeto_id": linha.projeto_id,
                "rota": (linha.payload or {}).get("rota"),
                "dias": None,
                "total": None,
                "lida": linha.lida_em is not None,
                "criado_em": linha.criado_em,
            }
            for linha in self.notificacao_repository.get_eventos(current_user.id)
        ]

    # ── 🔄 condições + ▣ agregados ───────────────────────────────────────
    def _condicoes_do_usuario(self, current_user, hoje: date) -> List[dict]:
        projetos = self._projetos_visiveis(current_user, frente_id=None)
        if not projetos:
            return []

        ctx = self._contexto(projetos)
        inicio, fim = janela_semana(hoje)
        reunioes = self.reuniao_repository.get_by_projetos_e_janela(ctx["ids"], inicio, fim)

        condicoes = detectar_condicoes(
            projetos,
            escopos_por_projeto=ctx["escopos_por_projeto"],
            bancas_por_escopo=ctx["bancas_por_escopo"],
            nomes_escopo=ctx["nomes_escopo"],
            tarefas_por_projeto=_agrupar(
                self.tarefa_repository.get_by_projetos(ctx["ids"]), "projeto_id"
            ),
            encerra_por_coluna=self._encerra_por_coluna(),
            projetos_com_reuniao={r.projeto_id for r in reunioes},
            # Para `ambientacao_sem_banca`. Ela não chega ao sino hoje — não
            # está em `PAPEIS_DESTINATARIOS` nem em `AGREGAVEIS_PARA_LIDERANCA`,
            # e o filtro a descarta. O calendário vai junto assim mesmo: no dia
            # em que alguém decidir que a coordenação recebe esta cobrança pelo
            # sino, basta a linha em `PAPEIS_DESTINATARIOS` — sem isto aqui, a
            # condição chegaria lá calculada por uma régua diferente da do
            # monitoramento, que é exatamente o que este módulo existe para
            # evitar.
            dias_nao_letivos=self._calendario_global(),
            hoje=hoje,
        )

        return self.montar(
            condicoes,
            papeis=self._papeis_no_projeto(current_user.id),
            usuario_id=current_user.id,
            posicao=current_user.posicao,
            leituras=self.notificacao_repository.get_leituras_de_condicao(current_user.id),
            hoje=hoje,
        )

    def montar(self, condicoes, *, papeis, usuario_id, posicao, leituras, hoje) -> List[dict]:
        """A mescla individual × agregado, sem tocar em banco.

        Separada do `execute` de propósito: é a regra que decide o que cada
        perfil vê, e é a única parte disto que precisa de teste unitário —
        o resto é carregamento.
        """
        individuais = self._individuais(condicoes, papeis, usuario_id)
        itens = [self._item(c, leituras) for c in individuais]

        if posicao in POSICOES_LIDERANCA:
            # O individual ganha do agregado: o que já foi entregue item a item
            # sai da conta, senão a mesma tarefa apareceria duas vezes.
            ja_entregues = {c.chave_dedup for c in individuais}
            restantes = [c for c in condicoes if c.chave_dedup not in ja_entregues]
            itens.extend(self._agregados(restantes, leituras, hoje))

        return itens

    def _papeis_no_projeto(self, usuario_id: int) -> Dict[int, str]:
        """`projeto_id → papel`, só onde a pessoa está alocada HOJE.

        Diretor e gerente também aparecem aqui quando estão numa equipe — e
        nesse caso recebem o projeto item a item, como qualquer membro.
        """
        return {
            m.projeto_id: m.papel
            for m in self.membro_repository.get_atuais_por_usuario(usuario_id)
        }

    def _individuais(self, condicoes, papeis: Dict[int, str], usuario_id: int) -> list:
        resultado = []
        for projeto_id, papel in papeis.items():
            do_projeto = [c for c in condicoes if c.projeto_id == projeto_id]
            resultado.extend(para_papel(do_projeto, papel, usuario_id))
        return resultado

    def _agregados(self, condicoes, leituras: Dict[str, datetime], hoje: date) -> List[dict]:
        por_tipo: Dict[str, int] = {}
        for condicao in condicoes:
            if condicao.tipo in AGREGAVEIS_PARA_LIDERANCA:
                por_tipo[condicao.tipo] = por_tipo.get(condicao.tipo, 0) + 1

        itens = []
        for tipo, total in por_tipo.items():
            singular, plural = ROTULO_AGREGADO[tipo]
            # A data entra na chave: dispensar "11 tarefas vencidas" hoje não
            # pode silenciar as 20 de amanhã. O resumo da liderança é sempre
            # o estado de HOJE.
            chave = f"agregado:{tipo}:{hoje.isoformat()}"
            itens.append(
                {
                    "id": None,
                    "chave": chave,
                    "tipo": tipo,
                    "origem": "condicao",
                    "titulo": (singular if total == 1 else plural).format(n=total),
                    "corpo": None,
                    "projeto_id": None,
                    # O detalhe já existe e é melhor do que qualquer lista que
                    # o sino conseguisse mostrar.
                    "rota": "/monitoramento",
                    "dias": None,
                    "total": total,
                    "lida": leituras.get(chave) is not None,
                    "criado_em": None,
                }
            )
        return itens

    def _item(self, condicao, leituras: Dict[str, datetime]) -> dict:
        return {
            "id": None,
            "chave": condicao.chave_dedup,
            "tipo": condicao.tipo,
            "origem": "condicao",
            "titulo": condicao.titulo,
            "corpo": None,
            "projeto_id": condicao.projeto_id,
            "rota": condicao.rota,
            "dias": condicao.dias,
            "total": None,
            # Condição não tem linha no banco até alguém dispensá-la: a
            # ausência de chave em `leituras` É o "não lida".
            "lida": leituras.get(condicao.chave_dedup) is not None,
            "criado_em": None,
        }

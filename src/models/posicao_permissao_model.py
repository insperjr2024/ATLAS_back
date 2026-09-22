from sqlalchemy import Boolean, Column, Integer, String
from src.database.database import Base


class PosicaoPermissaoModel(Base):
    """As permissões da plataforma, uma caixa por ação — POR POSIÇÃO.

    Substitui `cargo` (removido em 2026-08-07): eram duas dimensões de
    permissão convivendo (posição decidia o recorte de visão, cargo decidia
    o resto), e a distinção não sobreviveu ao uso real — cargo só criava
    combinação estranha (ex.: "Admin" que não amplia visão de projeto
    nenhuma) sem servir pra delegar de verdade.

    Desde 2026-09-16 este É o catálogo de cargos: a diretoria cria e apaga
    linha por `POST`/`DELETE /posicoes-permissoes` (ver `create_posicao_permissao.py`,
    `delete_posicao_permissao.py`), igual `frente`/`escopo`. Os 6 cargos que a
    plataforma sempre teve (`e_padrao=True`) continuam INTOCÁVEIS por essa
    rota — apagar um deles quebraria as dezenas de regras hardcoded a eles por
    nome em `middlewares/authorization.py` e afins, que um cargo novo
    deliberadamente NÃO herda (ver a migration `a9cae5c30c6d`).

    Eram as mesmas 13 caixas que `cargo` tinha: as 9 da tabela do §3 do
    briefing, as 3 extensões (Avaliação de Desempenho, formulários dela,
    Configurações) e `pode_ver_todos_projetos` (2026-08-07) — a única que muda
    QUAIS projetos aparecem; as outras só ligam/desligam funcionalidade.

    Da 15ª à 21ª (2026-09-02) vieram do mesmo levantamento: áreas de leitura
    pura ou de administração que continuavam presas a POSIÇÃO enquanto suas
    vizinhas de tela já eram caixa — o histórico do portfólio, os dois boards
    macro do Monitoramento, as colunas do kanban e a fila de Aprovações. As
    duas últimas partem `pode_administrar_configuracoes` em três: catálogo
    (que fica com o nome antigo), a tabela de permissões e os calendários
    base, que tinham riscos muito diferentes debaixo de uma caixa só.

    A 14ª é `pode_ver_dashboard_bancas` (2026-09-01): o Dashboard Bancas
    nasceu travado em `diretor_projetos` por uma matriz do FRONT
    (`utils/permissoes.ts`), fora desta tabela — quem quisesse delegar a
    leitura das notas tinha de promover a pessoa a diretora de projetos
    inteira. Virou caixa pelo mesmo motivo das outras três extensões.
    """

    __tablename__ = "posicao_permissao"

    id = Column(Integer, primary_key=True, index=True)
    #: O valor interno (slug), referenciado por `usuario.posicao`. Gerado a
    #: partir de `nome` na criação — ver `create_posicao_permissao.py`.
    posicao = Column(String(50), nullable=False, unique=True)
    #: O rótulo mostrado na tela. Os 6 cargos padrão nasceram sem este campo
    #: (o rótulo vivia hardcoded no front, `ROTULO_POSICAO`); a migration
    #: `a9cae5c30c6d` fez o backfill deles.
    nome = Column(String(100), nullable=False)
    #: Os 6 cargos que a plataforma sempre teve. `False` para todo cargo
    #: criado pela tela — só eles podem ser apagados por `DELETE`.
    e_padrao = Column(Boolean, default=False, nullable=False, server_default="0")

    # 1. Criar projeto e alocar equipe
    pode_criar_projeto = Column(Boolean, default=False, nullable=False)
    # 2. Editar a equipe de um projeto
    pode_editar_equipe = Column(Boolean, default=False, nullable=False)
    # 3. Gerir membros (posição e status)
    pode_gerir_membros = Column(Boolean, default=False, nullable=False)
    # 4. Marcar kickoff e data de entrega
    pode_marcar_kickoff = Column(Boolean, default=False, nullable=False)
    # 5. Definir cronograma por escopo (etapas, banca)
    pode_definir_cronograma = Column(Boolean, default=False, nullable=False)
    # 7. Criar tarefa
    pode_criar_tarefa = Column(Boolean, default=False, nullable=False)
    # 8. Mover e editar tarefa
    pode_mover_editar_tarefa = Column(Boolean, default=False, nullable=False)
    # 9. Ver os próprios projetos
    pode_ver_proprios_projetos = Column(Boolean, default=False, nullable=False)
    # 10. Monitoramento e alocação
    pode_ver_monitoramento = Column(Boolean, default=False, nullable=False)

    # Extensões além das 10 do §3.
    pode_administrar_desempenho = Column(Boolean, default=False, nullable=False)
    pode_editar_formularios_desempenho = Column(Boolean, default=False, nullable=False)
    pode_administrar_configuracoes = Column(Boolean, default=False, nullable=False)
    #: O Dashboard Bancas (`/avaliacoes`): as notas por pergunta, o histórico
    #: de bancas e a edição dos formulários de banca. Não confundir com
    #: `pode_editar_formularios_desempenho`, que é o formulário da Avaliação
    #: de Desempenho — outra área, outro formulário.
    pode_ver_dashboard_bancas = Column(Boolean, default=False, nullable=False)

    #: A aba Histórico do Monitoramento (portfólio encerrado). Leitura pura,
    #: e era a única aba de lá presa em `require_gestao` — nasce ligada para
    #: diretoria de projetos e gerente, que é quem a via.
    pode_ver_historico_projetos = Column(Boolean, default=False, nullable=False)
    #: O board macro de tarefas (todos os projetos juntos). Leitura pura,
    #: presa em `require_diretor_projetos` enquanto o resto do Monitoramento
    #: já era caixa.
    pode_ver_tarefas_gerais = Column(Boolean, default=False, nullable=False)
    #: O board macro de cronogramas. Mesma história do de tarefas.
    pode_ver_cronogramas_gerais = Column(Boolean, default=False, nullable=False)
    #: Criar, renomear, reordenar e apagar coluna do kanban do projeto.
    #: Desenhar o fluxo é trabalho de administração — criar e mover tarefa já
    #: eram caixa (`pode_criar_tarefa`, `pode_mover_editar_tarefa`), e só o
    #: redesenho da coluna seguia preso à posição.
    pode_configurar_colunas = Column(Boolean, default=False, nullable=False)
    #: Responder a fila de Aprovações: pedido de dias de ajuste, exceção de
    #: choque de horário e banca fora da janela.
    #:
    #: ⚠ NÃO cobre as seis linhas da fila. "Atrasos sem justificativa" é
    #: escrito por `require_lideranca` (quem conduz o projeto sabe o porquê) e
    #: "solicitações de entrada" são respondidas por quem coordena o projeto —
    #: as duas aparecem na fila como cobrança, não como decisão da diretoria.
    #: Ver `use_cases/monitoramento/aprovacoes.py`.
    pode_aprovar_pedidos = Column(Boolean, default=False, nullable=False)

    #: ⭐ Editar ESTA tabela — as caixas de todas as posições, inclusive a
    #: própria. Saiu de `pode_administrar_configuracoes` porque é de outra
    #: ordem de risco: as outras duas fatias daquela caixa mexem em catálogo e
    #: calendário; esta decide quem pode o quê na plataforma inteira.
    pode_administrar_permissoes = Column(Boolean, default=False, nullable=False)
    #: Calendários base: dias não letivos do semestre, importação do PDF e
    #: nome dos calendários. Também saiu de `pode_administrar_configuracoes` —
    #: é a área que mais se delega e a que menos estraga se sair errada.
    pode_gerir_calendarios_base = Column(Boolean, default=False, nullable=False)

    # A única que muda QUAIS projetos aparecem (ver docstring da classe).
    pode_ver_todos_projetos = Column(Boolean, default=False, nullable=False)

    #: ⭐ 2026-09-16, a pedido — substitui `usuario.coordenador_vendas` e
    #: `usuario.bdr`, que eram dois booleanos soltos, hardcoded a "posição é
    #: literalmente coordenador" e "literalmente consultor", sem nenhuma
    #: ligação com o resto do sistema de permissões: criar um cargo novo não
    #: tinha como herdar esse comportamento nem exibir que o tinha.
    #:
    #: Quem TEM esta caixa (na posição base ou no `cargo_extra`, ver
    #: `usuario_model.py`) aparece na lista "quem vendeu o projeto".
    pode_responsavel_por_vendas = Column(Boolean, default=False, nullable=False)
    #: Continua contando como liderança (vai à banca, soma no total), mas
    #: NÃO cobre `min_lideranca`/`min_membros` da FRENTE em que está
    #: cadastrado — o antigo `eh_lideranca_sem_frente(usuario.coordenador_
    #: vendas)`, agora por permissão em vez de nome de posição fixo.
    pode_coordenar_vendas = Column(Boolean, default=False, nullable=False)

    #: ⭐ 2026-09-16 — as seis caixas da integração com a Contratos
    #: (`documento_contratual`). "Criar documento"/"enviar ao cliente" não
    #: viram caixa nova: reaproveitam `pode_criar_projeto` e `pode_
    #: responsavel_por_vendas`, que já existem e significam a mesma coisa.
    #:
    #: Gerar o rascunho (.docx → PDF) e exportar o link de aprovação.
    pode_gerar_documento_juridico = Column(Boolean, default=False, nullable=False)
    #: Editar o texto do rascunho e regerar depois de confirmado — a partir
    #: daqui a palavra sobre o documento passa a ser de quem tem esta caixa,
    #: não mais de quem preencheu.
    pode_editar_documento_juridico = Column(Boolean, default=False, nullable=False)
    #: Fechar o ciclo: marcar como assinado (fora da plataforma) e arquivar.
    pode_marcar_documento_assinado = Column(Boolean, default=False, nullable=False)
    #: Ver o Repositório — todo documento final assinado, de todo projeto,
    #: organizado por gestão.
    pode_ver_repositorio_contratos = Column(Boolean, default=False, nullable=False)
    #: ⭐ 2026-09-21 — a aba "Contratos" (painel cross-projeto de documentos
    #: EM ANDAMENTO, não arquivados — diferente do Repositório acima). O
    #: "ajuste" pedido: dá acesso à aba pra alguém fora da régua padrão
    #: (diretoria/Jurídico/vendedor/coordenador do projeto), como um
    #: consultor alocado dentro do Jurídico.
    pode_ver_painel_contratos = Column(Boolean, default=False, nullable=False)
    #: Cadastrar documento já assinado fora do fluxo normal (gestão anterior,
    #: por exemplo) — só guarda o arquivo e arquiva direto na gestão informada.
    pode_importar_documento_antigo = Column(Boolean, default=False, nullable=False)
    #: Abrir o TEP dentro de um projeto que já tem Contrato de Prestação —
    #: quem acompanha a ENTREGA, não a venda.
    pode_solicitar_tep = Column(Boolean, default=False, nullable=False)
    #: ⭐ 2026-09-21 — a pedido: quem assina PELA Insper Jr era só diretoria
    #: de projetos, hardcoded (`eh_diretoria_de_projetos`). Vira delegável.
    pode_editar_identidade_institucional = Column(Boolean, default=False, nullable=False)
    #: Acessar a aba Contratos (vê TODOS os documentos, igual `pode_ver_
    #: painel_contratos`) e elaborar (abrir, preencher, confirmar, gerar) os
    #: documentos jurídicos dos projetos em que a PRÓPRIA pessoa consta como
    #: vendedora — não qualquer projeto. `+ Novo Contrato` também só oferece,
    #: pra quem só tem esta caixa, os projetos em que ela vendeu (mesma régua
    #: de `aplicar_recorte_visao`, que já mostra pro vendedor os projetos que
    #: vendeu).
    pode_elaborar_contratos_proprios = Column(Boolean, default=False, nullable=False)
    #: Mesma coisa, sem o recorte por vendedor — abre e elabora o documento
    #: jurídico de QUALQUER projeto, igual diretoria/Jurídico.
    pode_elaborar_qualquer_contrato = Column(Boolean, default=False, nullable=False)

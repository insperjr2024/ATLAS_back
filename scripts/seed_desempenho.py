"""Seed dos 4 formulários de Avaliação de Desempenho (periodico/finalizacao x
consultor/coordenador), com o conteúdo validado pela diretoria no protótipo.

Rodar:  .venv/bin/python -m scripts.seed_desempenho
É idempotente — rodar de novo não duplica nada (checa por tipo+papel antes de
criar). `finalizacao` nasce como cópia idêntica de `periodico`, editável
depois via /avaliacao-desempenho/painel/formularios.
"""

from src.database.database import SessionLocal
from src.models.desempenho_criterio_model import DesempenhoCriterioModel
from src.models.desempenho_formulario_model import DesempenhoFormularioModel
from src.models.desempenho_formulario_secao_model import DesempenhoFormularioSecaoModel

TEXTOS = {
    "consultor": {
        "nota_geral_titulo": "Avaliação geral como consultor",
        "nota_geral_descricao": (
            "Considerando sua atuação e comportamento ao longo das interações e "
            "atividades realizadas, como você avalia o desempenho geral deste consultor?"
        ),
        "comentarios_titulo": "Comentários, feedbacks e exemplos",
        "comentarios_descricao": (
            "Compartilhe feedbacks sobre este consultor, destacando pontos fortes e "
            "pontos de melhoria. Sempre que possível, inclua exemplos de situações ou "
            "comportamentos que justifiquem sua avaliação. (Escrevam no mínimo 1 ponto "
            "forte e 1 ponto de melhoria)"
        ),
        "comentarios_aviso": (
            "Este campo é fundamental para dar contexto às notas atribuídas e "
            "contribuir para o desenvolvimento dos membros. Pedimos que todos "
            "preencham com atenção."
        ),
    },
    "coordenador": {
        "nota_geral_titulo": "Avaliação geral como coordenador",
        "nota_geral_descricao": (
            "Considerando sua atuação e comportamento ao longo das interações e "
            "atividades realizadas, como você avalia o desempenho geral deste coordenador?"
        ),
        "comentarios_titulo": "Comentários, feedbacks e exemplos",
        "comentarios_descricao": (
            "Compartilhe feedbacks sobre este coordenador, destacando pontos fortes e "
            "pontos de melhoria. Sempre que possível, inclua exemplos de situações ou "
            "comportamentos que justifiquem sua avaliação. (Escrevam no mínimo 1 ponto "
            "forte e 1 ponto de melhoria)"
        ),
        "comentarios_aviso": (
            "Este campo é fundamental para dar contexto às notas atribuídas e "
            "contribuir para o desenvolvimento dos membros. Pedimos que todos "
            "preencham com atenção."
        ),
    },
}

# (título da seção, descrição opcional, [(label, descrição), ...])
SECOES_CONSULTOR = [
    (
        "Execução das entregas",
        "Avalia se o consultor entrega bem e cumpre o que foi combinado.",
        [
            (
                "Responsabilidade e execução",
                "Cumpre prazos, assume responsabilidade pelas tarefas e executa o "
                "que foi acordado no projeto.",
            ),
            (
                "Qualidade das entregas",
                "Produz materiais claros, bem estruturados e organizados, "
                "demonstrando atenção aos detalhes nas entregas.",
            ),
        ],
    ),
    (
        "Capacidade analítica e técnica",
        "Avalia como o consultor pensa e aplica conhecimento no projeto.",
        [
            (
                "Conhecimento técnico",
                "Demonstra domínio dos conceitos e ferramentas utilizados nos "
                "escopos da Insper Jr., aplicando corretamente conhecimentos "
                "técnicos ao longo do projeto.",
            ),
            (
                "Análise crítica e raciocínio",
                "Consegue interpretar informações, questionar hipóteses e "
                "contribuir com reflexões relevantes para o desenvolvimento das "
                "soluções do projeto.",
            ),
        ],
    ),
    (
        "Interação e postura profissional",
        None,
        [
            (
                "Proatividade e iniciativa",
                "Toma iniciativa, busca soluções para problemas e se disponibiliza "
                "para contribuir além das tarefas mínimas atribuídas.",
            ),
            (
                "Comunicação",
                "Se comunica de forma clara e objetiva com o time e, quando "
                "aplicável, com o cliente, contribuindo para o alinhamento do "
                "projeto.",
            ),
            (
                "Colaboração e trabalho em equipe",
                "Trabalha de forma construtiva com os demais membros do time, "
                "respeita diferentes pontos de vista e demonstra abertura para "
                "ouvir ideias de outros.",
            ),
        ],
    ),
]

SECOES_COORDENADOR = [
    (
        "Liderança e direcionamento do time",
        None,
        [
            (
                "Liderança e direcionamento do time",
                "Capacidade de orientar o time, estimular discussões produtivas e "
                "direcionar o desenvolvimento das soluções do projeto, incentivando "
                "pensamento crítico e inconformismo construtivo na busca por "
                "melhores resultados.",
            )
        ],
    ),
    (
        "Gestão e organização do time",
        None,
        [
            (
                "Gestão e organização do time",
                "Organiza o trabalho do time, conduz reuniões semanais, distribui "
                "tarefas de forma adequada e acompanha de perto o andamento das "
                "atividades.",
            )
        ],
    ),
    (
        "Qualidade e validação das soluções",
        None,
        [
            (
                "Qualidade e validação das soluções",
                "Capacidade de validar análises e ideias do time, garantindo "
                "consistência, coerência e qualidade nas entregas do projeto.",
            )
        ],
    ),
    (
        "Domínio técnico",
        None,
        [
            (
                "Domínio técnico",
                "Demonstra domínio dos conceitos e ferramentas utilizados nos "
                "escopos da Insper Jr., sendo referência técnica para o time "
                "quando necessário.",
            )
        ],
    ),
    (
        "Comunicação e alinhamento",
        None,
        [
            (
                "Comunicação e alinhamento",
                "Se comunica de forma clara e estruturada com o time, cliente e "
                "diretoria, garantindo alinhamento sobre o andamento do projeto.",
            )
        ],
    ),
]

SECOES_POR_PAPEL = {"consultor": SECOES_CONSULTOR, "coordenador": SECOES_COORDENADOR}

# finalizacao nasce como cópia idêntica de periodico (editável depois, à parte)
COMBINACOES = [
    ("periodico", "consultor"),
    ("periodico", "coordenador"),
    ("finalizacao", "consultor"),
    ("finalizacao", "coordenador"),
]


def executar():
    db = SessionLocal()
    criados = 0
    try:
        for tipo, papel in COMBINACOES:
            existente = db.query(DesempenhoFormularioModel).filter_by(tipo=tipo, papel=papel).first()
            if existente:
                continue

            textos = TEXTOS[papel]
            formulario = DesempenhoFormularioModel(tipo=tipo, papel=papel, **textos)
            db.add(formulario)
            db.flush()

            for ordem_secao, (titulo, descricao, criterios) in enumerate(SECOES_POR_PAPEL[papel]):
                secao = DesempenhoFormularioSecaoModel(
                    formulario_id=formulario.id, titulo=titulo, descricao=descricao, ordem=ordem_secao
                )
                db.add(secao)
                db.flush()

                for ordem_criterio, (label, desc_criterio) in enumerate(criterios):
                    db.add(
                        DesempenhoCriterioModel(
                            secao_id=secao.id,
                            label=label,
                            descricao=desc_criterio,
                            tipo_resposta="nota",
                            ordem=ordem_criterio,
                        )
                    )

            criados += 1

        db.commit()
        print(f"Seed de desempenho aplicado: {criados} formulário(s) novo(s) (de {len(COMBINACOES)} esperados).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    executar()

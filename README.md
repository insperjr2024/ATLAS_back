# BANCAS_back

API do projeto BANCAS da Insper Jr, construída com FastAPI, SQLAlchemy e Alembic sobre MySQL.

## Stack

- **Python** >= 3.14
- **FastAPI** — framework web
- **Uvicorn** — servidor ASGI
- **SQLAlchemy 2** — ORM
- **Alembic** — migrations
- **PyMySQL** — driver MySQL
- **pydantic-settings** — configuração via variáveis de ambiente

## Estrutura

```
src/
├── app.py           # instância do FastAPI e rotas raiz
├── config/          # Settings (lê o .env)
├── database/        # engine, SessionLocal, Base e get_db
├── entities/        # schemas Pydantic (entrada/saída da API)
├── models/          # models SQLAlchemy (tabelas)
├── repositories/    # acesso ao banco
├── use_cases/       # regras de negócio
├── middlewares/     # middlewares da aplicação
└── utils/           # utilitários
alembic/             # configuração e versões das migrations
```

As pastas de domínio (`entities`, `models`, `repositories`, `use_cases`, `middlewares`, `utils`) ainda estão vazias — a estrutura está pronta para receber as features.

## Setup

Requer Python 3.14 ou superior. Confira sua versão com `python3 --version`.

```bash
# 1. Criar o ambiente virtual
python3 -m venv .venv

# 2. Ativar o ambiente virtual
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Criar o .env a partir do exemplo
cp .env.example .env
```

> Com o ambiente ativado, o terminal mostra `(.venv)` no início da linha. Todos os comandos abaixo assumem o ambiente ativado — se abrir um terminal novo, rode o passo 2 de novo.

Depois edite o `.env` com os dados do seu banco local:

```env
DATABASE_URL=mysql+pymysql://usuario:senha@localhost:3306/bancas_db
SECRET_KEY=sua_chave_secreta_aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

> O banco `bancas_db` precisa existir no MySQL antes de rodar as migrations.

### Instalando um pacote novo

```bash
pip install nome-do-pacote
pip freeze > requirements.txt
```

Adicione também a dependência na lista `dependencies` do `pyproject.toml`, para manter os dois arquivos em sincronia.

## Migrations

```bash
# Aplicar todas as migrations pendentes
alembic upgrade head

# Gerar uma nova migration a partir dos models
alembic revision --autogenerate -m "descricao da mudanca"

# Voltar uma migration
alembic downgrade -1
```

A URL do banco vem do `.env` (via `src/config/config.py`), não do `alembic.ini`. Models novos precisam ser importados em `src/models/__init__.py` para que o `--autogenerate` os enxergue.

## Rodando a API

```bash
uvicorn src.app:app --reload
```

A API sobe em `http://localhost:8000`.

- Documentação interativa (Swagger): http://localhost:8000/docs
- Documentação alternativa (ReDoc): http://localhost:8000/redoc

## Rotas atuais

| Método | Rota         | Descrição                          |
| ------ | ------------ | ---------------------------------- |
| GET    | `/`          | Mensagem de status da API          |
| GET    | `/health`    | Health check da aplicação          |
| GET    | `/health/db` | Health check da conexão com o banco |

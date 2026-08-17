from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.config import get_settings

settings = get_settings()

# ─── Tamanho do pool ──────────────────────────────────────────────────────
#
# ⚠ O Supabase em **session mode** (porta 5432) permite 15 clientes NO TOTAL,
# somando tudo que fala com o banco. O default do SQLAlchemy é pool_size=5 +
# max_overflow=10 — ou seja, um único processo do backend já podia sozinho
# ocupar os 15 e derrubar todo o resto com
# `FATAL: (EMAXCONNSESSION) max clients reached in session mode`.
#
# A conta que estes números fecham, no pior momento (um deploy, quando a
# instância velha ainda não morreu e a nova já subiu):
#
#     2 instâncias x (3 + 2) = 10  +  1 do `alembic upgrade head`  =  11
#
# Sobram 4 para migration manual, script de manutenção ou alguém conectando
# pelo painel do Supabase. Subir estes valores exige refazer essa conta.
#
# 5 conexões por instância é folgado para o volume real (um núcleo de ~70
# pessoas): cada request segura uma conexão só enquanto responde.
POOL_SIZE = 3
MAX_OVERFLOW = 2

#: O pooler derruba conexão ociosa sem avisar, e o SQLAlchemy só descobre
#: quando tenta usar — o que vira um 500 numa request que não tinha nada de
#: errado. `pre_ping` faz um `SELECT 1` antes de entregar a conexão, e
#: `recycle` aposenta a conexão antes de o pooler pensar em fazer isso.
POOL_RECYCLE_SEGUNDOS = 300

# SQLite não aceita estes parâmetros (usa outra classe de pool) e nenhum
# ambiente real roda nele — os testes montam engine próprio.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(settings.DATABASE_URL)
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=POOL_RECYCLE_SEGUNDOS,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

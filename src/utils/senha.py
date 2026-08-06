"""Senha: hash, verificação e a provisória que vai no e-mail de cadastro."""

import secrets

import bcrypt

#: Piso de tamanho da senha. O sistema não tem política formal; 8 é o mínimo
#: que não deixa passar "1234". Mora aqui, e não num use case, porque agora
#: são DOIS os caminhos que definem senha — o link de "esqueci minha senha" e
#: a primeira definição de quem entrou com senha provisória — e duas cópias da
#: constante viram duas regras no dia em que alguém mudar uma delas.
TAMANHO_MINIMO_SENHA = 8

#: Sem `0/O`, `1/l/I` e sem minúsculas parecidas com maiúsculas: esta senha é
#: LIDA de um e-mail e digitada à mão (às vezes ditada por telefone). Trocar
#: entropia por legibilidade aqui é barato — são 10 caracteres de um alfabeto
#: de 30, e ela só vale até a pessoa definir a própria.
ALFABETO_PROVISORIA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_BLOCO_PROVISORIA = 5


def hash_senha(senha: str) -> str:
    senha_bytes = senha.encode("utf-8")
    hash_bytes = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    senha_bytes = senha.encode("utf-8")
    hash_bytes = senha_hash.encode("utf-8")
    return bcrypt.checkpw(senha_bytes, hash_bytes)


def gerar_senha_provisoria() -> str:
    """A senha de primeiro acesso, no formato `XXXXX-XXXXX`.

    `secrets`, não `random`: é credencial, e o gerador padrão do Python é
    previsível a partir do estado interno.

    O hífen no meio é para o olho — quem copia de um e-mail e digita erra
    menos com dois blocos curtos do que com dez caracteres corridos. Ele não
    entra no alfabeto, então não conta como entropia nem confunde a leitura.
    """
    bloco = lambda: "".join(  # noqa: E731
        secrets.choice(ALFABETO_PROVISORIA) for _ in range(TAMANHO_BLOCO_PROVISORIA)
    )
    return f"{bloco()}-{bloco()}"

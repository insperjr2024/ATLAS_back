class ResourceInUseError(Exception):
    """Levantada quando uma exclusão viola uma Foreign Key (registro ainda referenciado)."""
    pass


class RegraDeNegocioError(Exception):
    """Levantada quando uma regra de negócio é violada (dado tecnicamente válido, mas semanticamente errado).

    ⭐ **O `codigo` existe para a interface reagir SEM ler o texto.**

    A mensagem é escrita para a pessoa e muda quando a regra muda de redação.
    Quem precisa fazer algo diferente diante de UMA recusa específica olha o
    código, que é contrato; quem só precisa exibir o problema continua usando
    a mensagem, que é texto.

    ⚠ A distinção não é teórica — ela já custou uma funcionalidade. O modal de
    realizar banca reconhecia a recusa de composição procurando a frase
    "Composição incompleta" dentro da mensagem. Quando o piso por frente saiu
    do §8, a frase mudou, e o botão "registrar assim mesmo" da diretoria
    simplesmente parou de aparecer: a plataforma recusava e não oferecia saída
    nenhuma. Uma segunda tela nasceu depois com a mesma ideia e um `includes`
    ainda mais frouxo, que também não casa com o texto atual.

    ⚠ Só declare código onde a interface REAGE à recusa. Regra que só precisa
    ser mostrada não ganha código — seria vocabulário morto para manter.
    """

    def __init__(self, mensagem: str, codigo: str | None = None):
        super().__init__(mensagem)
        self.codigo = codigo


#: Recusa que a diretoria pode atropelar reenviando com `forcar`. É o que
#: destrava o "registrar assim mesmo" no modal de realizar banca e na aba
#: Banca do projeto.
CODIGO_BANCA_ABAIXO_DO_MINIMO = "banca_abaixo_do_minimo"

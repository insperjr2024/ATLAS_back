"""Templates HTML profissionais para e-mails do ATLAS.

Usa estilos inline e tabelas (não flexbox/grid) para compatibilidade com
clientes de e-mail — mesmo padrão visual usado no GP2 (Gestão de Pessoas),
para manter a identidade da Insper Jr. consistente entre as duas plataformas.
"""

# Cores da marca Insper Jr (vermelho principal) — mesmas do theme.ts do front
PRIMARY_COLOR = "#DC2626"  # hsl(0, 72%, 51%)
TEXT_COLOR = "#1F2937"
TEXT_MUTED = "#6B7280"
BG_COLOR = "#F9FAFB"
BORDER_COLOR = "#E5E7EB"


def _email_shell(titulo_pagina: str, subtitulo_header: str, conteudo_html: str, rodape_extra: str = "") -> str:
    """Casca comum a todo e-mail: header vermelho, card branco, footer cinza.

    `conteudo_html` entra pronto (já com o padding lateral do card) porque
    cada e-mail tem uma quantidade e ordem de blocos diferente — texto, tabela
    de dados, botão CTA — e forçar todos no mesmo esqueleto de parágrafos
    engessaria templates futuros sem ganhar nada em troca.
    """
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{titulo_pagina} - ATLAS</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F3F4F6; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #F3F4F6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 520px; margin: 0 auto;">
                    <!-- Card container -->
                    <tr>
                        <td style="background-color: #FFFFFF; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1); overflow: hidden;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <!-- Header com branding -->
                                <tr>
                                    <td style="background-color: {PRIMARY_COLOR}; padding: 32px 40px; text-align: center;">
                                        <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.5px;">Insper Jr.</h1>
                                        <p style="margin: 4px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.9);">{subtitulo_header}</p>
                                    </td>
                                </tr>
                                <!-- Conteúdo -->
                                <tr>
                                    <td style="padding: 40px;">
                                        {conteudo_html}
                                    </td>
                                </tr>
                                <!-- Footer -->
                                <tr>
                                    <td style="padding: 24px 40px; background-color: {BG_COLOR}; border-top: 1px solid {BORDER_COLOR};">
                                        {rodape_extra}
                                        <p style="margin: 0; font-size: 11px; color: #9CA3AF; text-align: center;">© Insper Jr. · ATLAS</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
""".strip()


def _botao_cta(link: str, texto: str) -> str:
    return f"""
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                            <tr>
                                                <td align="center" style="padding: 8px 0 8px 0;">
                                                    <a href="{link}" style="display: inline-block; padding: 14px 32px; background-color: {PRIMARY_COLOR}; color: #FFFFFF !important; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 8px; box-shadow: 0 2px 4px rgba(220, 38, 38, 0.3);">{texto}</a>
                                                </td>
                                            </tr>
                                        </table>"""


def get_senha_provisoria_html(nome: str, senha: str, link_login: str) -> str:
    """Template do e-mail de boas-vindas com a senha provisória de primeiro acesso."""
    conteudo = f"""
                                        <p style="margin: 0 0 24px 0; font-size: 18px; font-weight: 600; color: {TEXT_COLOR};">Olá, {nome}!</p>
                                        <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: {TEXT_COLOR};">A sua conta no ATLAS foi criada. Entre com esta senha provisória:</p>
                                        <div style="background-color: {BG_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; padding: 20px; margin: 0 0 24px 0; text-align: center;">
                                            <p style="margin: 0; font-size: 20px; font-weight: 600; color: {TEXT_COLOR}; font-family: monospace; letter-spacing: 1px;">{senha}</p>
                                        </div>
                                        {_botao_cta(link_login, "Acessar o ATLAS")}
                                        <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 1.5; color: {TEXT_MUTED};">Assim que entrar, o sistema vai pedir para você escolher a <strong>sua</strong> senha — a provisória deixa de valer nesse momento, e até lá o resto da plataforma fica bloqueado.</p>
                                        <p style="margin: 16px 0 0 0; font-size: 13px; line-height: 1.5; color: {TEXT_MUTED};">Se você não esperava este e-mail, avise a diretoria.</p>"""
    return _email_shell("Seu acesso ao ATLAS", "Acesso à plataforma", conteudo)


def get_recuperacao_senha_html(nome: str, link: str, minutos: int) -> str:
    """Template do e-mail de redefinição de senha."""
    conteudo = f"""
                                        <p style="margin: 0 0 24px 0; font-size: 18px; font-weight: 600; color: {TEXT_COLOR};">Olá, {nome}!</p>
                                        <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: {TEXT_COLOR};">Recebemos um pedido para redefinir a sua senha no ATLAS. Clique no botão abaixo para escolher uma nova.</p>
                                        {_botao_cta(link, "Escolher uma nova senha")}
                                        <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 1.5; color: {TEXT_MUTED};">O link vale por <strong>{minutos} minutos</strong> e só pode ser usado uma vez.</p>
                                        <p style="margin: 16px 0 0 0; font-size: 13px; line-height: 1.5; color: {TEXT_MUTED};">Se não foi você que pediu, ignore este e-mail — a sua senha atual continua valendo.</p>"""
    return _email_shell("Redefinição de senha", "Redefinição de senha", conteudo)


def get_notificacao_html(nome: str, titulo: str, corpo: str | None, link: str) -> str:
    """Template do e-mail espelho de uma notificação do sino do ATLAS."""
    bloco_corpo = f'<p style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: {TEXT_COLOR};">{corpo}</p>' if corpo else ""
    conteudo = f"""
                                        <p style="margin: 0 0 24px 0; font-size: 18px; font-weight: 600; color: {TEXT_COLOR};">Olá, {nome}!</p>
                                        <p style="margin: 0 0 24px 0; font-size: 16px; line-height: 1.6; color: {TEXT_COLOR};"><strong>{titulo}</strong></p>
                                        {bloco_corpo}
                                        {_botao_cta(link, "Ver no ATLAS")}"""
    rodape_extra = f'<p style="margin: 0 0 16px 0; font-size: 12px; line-height: 1.5; color: {TEXT_MUTED}; text-align: center;">Você recebeu este e-mail porque esta notificação apareceu no seu sino do ATLAS.</p>'
    return _email_shell(titulo, "Notificação", conteudo, rodape_extra)

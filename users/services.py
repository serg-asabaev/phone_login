import secrets

def generate_invite_code(length=6):
    """
    Генерирует случайный инвайт-код из латинских букв и цифр.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    return ''.join(secrets.choice(alphabet) for _ in range(length))
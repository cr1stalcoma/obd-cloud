from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_fernet: Fernet | None = None


def _box() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.encryption_key.encode())
    return _fernet


def encrypt(value: str) -> str:
    return _box().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _box().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("invalid encrypted token") from exc

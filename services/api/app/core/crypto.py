from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretBox:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("invalid encrypted token") from exc


secret_box = SecretBox(settings.encryption_key)

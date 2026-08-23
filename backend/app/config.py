from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./ventas_stock.db"
    secret_key: str = "dev-secret-key-cambiar-en-produccion"
    access_token_expire_minutes: int = 480
    admin_username: str = "admin"
    admin_password: str = "admin123"
    sendgrid_api_key: str = ""
    email_from: str = ""
    frontend_url: str = "http://127.0.0.1:5500"

    class Config:
        env_file = ".env"
        # Permite leer DATABASE_URL, SECRET_KEY, etc. (mayusculas) del entorno
        case_sensitive = False

    @field_validator("database_url", mode="before")
    @classmethod
    def _default_si_vacio(cls, valor):
        # Si DATABASE_URL quedo vacio en el .env (caso tipico en desarrollo local),
        # usar SQLite en vez de intentar parsear un string vacio.
        if not valor or not str(valor).strip():
            return "sqlite:///./ventas_stock.db"
        return valor


settings = Settings()

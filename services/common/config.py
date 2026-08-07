from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # API Credentials
    GEMINI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")

    # Tier Mapping — "-latest" rolling aliases rather than dated snapshots
    # (e.g. gemini-2.0-flash-lite), because Google zeroes free-tier quota on
    # older dated models before the alias catches up; see docs/LEARN.md.
    MODEL_TIER_FRONTIER: str = Field(default="gemini-flash-latest")
    MODEL_TIER_MID: str = Field(default="gemini-flash-lite-latest")
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-small-en-v1.5")

    # Database (MySQL 8 — sync SQLAlchemy + PyMySQL, see docs/LEARN.md for why)
    DATABASE_URL: str = Field(
        default="mysql+pymysql://finops_user:finops_password@localhost:3306/finops_db"
    )

    # Encryption / Security Keys
    PII_VAULT_AES_KEY: str = Field(default="32_byte_secret_key_for_pii_aes!!")
    APPROVAL_JWT_SECRET: str = Field(default="secret_approval_jwt_key")
    AUDIT_SIGNING_SECRET: str = Field(default="secret_audit_export_signing_key")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRY_MINUTES: int = Field(default=480)

    # Golden-path policy version, quoted verbatim in every DecisionRecord
    POLICY_VERSION: str = Field(default="2026.08.01")


# Singleton instance
settings = Settings()

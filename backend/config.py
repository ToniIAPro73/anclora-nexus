from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Anclora Nexus"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    APP_ENV: str = "development"
    # GuestHub product environment (renamed from Anclora SyncXML, 2026-08).
    # Canonical env name: GUESTHUB_ENV; legacy SYNCXML_ENV still accepted as fallback.
    GUESTHUB_ENV: str = Field(default="development", validation_alias=AliasChoices("GUESTHUB_ENV", "SYNCXML_ENV"))
    ALLOW_REAL_SUPABASE_WRITE: bool = False
    USE_SYNTHETIC_DATA_ONLY: bool = False
    
    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    PUBLIC_CTA_ORG_ID: str = "00000000-0000-0000-0000-000000000000"
    LEGACY_SINGLE_TENANT_ORG_ID: Optional[str] = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
    ALLOW_LEGACY_ORG_FALLBACK: bool = False
    APP_BASE_URL: str = "http://localhost:3000"
    
    # AI Runtime Settings
    AI_RUNTIME_PROFILE: str = "groq-cloudflare"

    GROQ_API_KEY: Optional[str] = None
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL_PRIMARY: str = "openai/gpt-oss-20b"
    GROQ_MODEL_FALLBACK: str = "llama-3.3-70b-versatile"
    GROQ_MODEL_FAST: str = "llama-3.1-8b-instant"
    GROQ_MODEL_NO_EVIDENCE: str = "llama-3.1-8b-instant"
    GROQ_MODEL_GUARD: str = "llama-3.1-8b-instant"

    CLOUDFLARE_ACCOUNT_ID: Optional[str] = None
    CLOUDFLARE_API_TOKEN: Optional[str] = None
    CLOUDFLARE_AI_BASE_URL: Optional[str] = None
    CLOUDFLARE_MODEL_PRIMARY: str = "@cf/openai/gpt-oss-20b"
    CLOUDFLARE_MODEL_FALLBACK: str = "@cf/meta/llama-3.1-8b-instruct"
    CLOUDFLARE_MODEL_FAST: str = "@cf/meta/llama-3.1-8b-instruct"
    CLOUDFLARE_MODEL_NO_EVIDENCE: str = "@cf/meta/llama-3.1-8b-instruct"
    CLOUDFLARE_MODEL_GUARD: str = "@cf/meta/llama-3.1-8b-instruct"
    CLOUDFLARE_EMBED_MODEL: str = "@cf/baai/bge-small-en-v1.5"

    INTERNAL_AUDIT_SECRET: Optional[str] = None

    # Native email transport (BL-next-03)
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM: Optional[str] = None
    RESEND_FROM_EMAIL: Optional[str] = None
    RESEND_REPLY_TO: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "Anclora Nexus"
    SMTP_REPLY_TO: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    RECAPTCHA_SECRET_KEY: Optional[str] = None
    RECAPTCHA_VERIFY_URL: str = "https://www.google.com/recaptcha/api/siteverify"
    
    TURNSTILE_SECRET_KEY: Optional[str] = None
    TURNSTILE_VERIFY_URL: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    TURNSTILE_PRIVATE_ESTATES_HOSTNAMES: str = "private-estates.anclora.com"
    
    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_API_KEY: Optional[str] = None

    # GuestHub Pilot Settings (product renamed from Anclora SyncXML to Anclora GuestHub, 2026-08)
    # Canonical env names are GUESTHUB_*; each setting falls back to the legacy SYNCXML_* name.
    # NOTE: default URLs still point to the legacy anclora-syncxml.vercel.app deployment
    # pending the owner's domain decision — do not invent a new domain here.
    # NOTE: GUESTHUB_ADMIN_PASSWORD is used by the product-side ops flow and intentionally
    # not listed in .env.example (pre-existing drift kept as-is).
    GUESTHUB_ADMIN_PASSWORD: Optional[str] = Field(default=None, validation_alias=AliasChoices("GUESTHUB_ADMIN_PASSWORD", "SYNCXML_ADMIN_PASSWORD"))
    GUESTHUB_APP_URL: str = Field(default="https://anclora-syncxml.vercel.app", validation_alias=AliasChoices("GUESTHUB_APP_URL", "SYNCXML_APP_URL"))
    GUESTHUB_LOGIN_URL: str = Field(default="https://anclora-syncxml.vercel.app/login", validation_alias=AliasChoices("GUESTHUB_LOGIN_URL", "SYNCXML_LOGIN_URL"))
    GUESTHUB_WEBHOOK_SECRET: Optional[str] = Field(default=None, validation_alias=AliasChoices("GUESTHUB_WEBHOOK_SECRET", "SYNCXML_WEBHOOK_SECRET"))
    GUESTHUB_INTERNAL_API_URL: str = Field(default="https://anclora-syncxml.vercel.app/api/internal/pilot-users", validation_alias=AliasChoices("GUESTHUB_INTERNAL_API_URL", "SYNCXML_INTERNAL_API_URL"))
    GUESTHUB_INTERNAL_API_SECRET: Optional[str] = Field(default=None, validation_alias=AliasChoices("GUESTHUB_INTERNAL_API_SECRET", "SYNCXML_INTERNAL_API_SECRET"))
    GUESTHUB_PILOT_AUTO_APPROVE: bool = Field(default=False, validation_alias=AliasChoices("GUESTHUB_PILOT_AUTO_APPROVE", "SYNCXML_PILOT_AUTO_APPROVE"))

    ADMIN_EMAIL: str = "toni@anclora.com"
    ADMIN_EMAILS: str = "antonio@anclora.com"
    # Anclora Identity Service Settings
    IDENTITY_SERVICE_URL: str = "http://localhost:4001"
    IDENTITY_SERVICE_TOKEN: Optional[str] = None
    IDENTITY_PROVISIONING_ENABLED: bool = True

    # Hermes Worker Settings
    HERMES_WORKER_URL: str = "http://localhost:8787"
    HERMES_WORKER_API_KEY: Optional[str] = None

    # Real Estate DMS / signatures / Advisor AI
    NEXUS_DOCUMENT_ENCRYPTION_KEY: Optional[str] = None
    NEXUS_DMS_BUCKET: str = "dms"
    NEXUS_DMS_MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    DOCUSEAL_WEBHOOK_SECRET: Optional[str] = None
    DOCUSEAL_API_KEY: Optional[str] = None
    DOCUSEAL_API_URL: str = "https://api.docuseal.com"
    ADVISOR_AI_BASE_URL: Optional[str] = None
    ADVISOR_AI_INTERNAL_API_KEY: Optional[str] = None
    ADVISOR_AI_TIMEOUT_SECONDS: float = 12.0

    # Exclusiva Webhook Dispatcher (Req 15.1, 15.4)
    CONTENT_GENERATOR_WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SHARED_SECRET: Optional[str] = None

    # Legacy compatibility - deprecated
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    CRON_SECRET: Optional[str] = None
    
    # LangGraph Settings
    MAX_ITERATIONS: int = 10
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        extra="ignore"
    )

settings = Settings()

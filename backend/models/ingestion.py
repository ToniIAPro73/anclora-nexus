from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

class EntityType(str, Enum):
    LEAD = "lead"
    PROPERTY = "property"
    SELLER_SIGNAL = "seller_signal"

class IngestionStatus(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    PROCESSED = "processed"
    REJECTED = "rejected"
    FAILED = "failed"

class LeadSourceSystem(str, Enum):
    MANUAL = "manual"
    CTA_WEB = "cta_web"
    IMPORT = "import"
    REFERRAL = "referral"
    PARTNER = "partner"
    SOCIAL = "social"

class LeadSourceChannel(str, Enum):
    WEBSITE = "website"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    EMAIL = "email"
    PHONE = "phone"
    OTHER = "other"

class HNWIQualificationTier(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"

class HNWISourceChannel(str, Enum):
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"
    REDDIT = "reddit"
    GOOGLE_ALERT = "google-alert"
    OTHER = "other"

class PropertySourceSystem(str, Enum):
    MANUAL = "manual"
    WIDGET = "widget"
    PBM = "pbm"
    IMPORT = "import"

class PropertySourcePortal(str, Enum):
    IDEALISTA = "idealista"
    FOTOCASA = "fotocasa"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    RIGHTMOVE = "rightmove"
    KYERO = "kyero"
    OTHER = "other"

class LeadIngestionPayload(BaseModel):
    org_id: str
    external_id: str
    connector_name: Optional[str] = None
    trace_id: Optional[str] = None
    source_system: LeadSourceSystem
    source_channel: LeadSourceChannel
    source_detail: Optional[str] = None
    source_url: Optional[str] = None
    source_referrer: Optional[str] = None
    gdpr_consent: bool = False
    gdpr_consent_at: Optional[datetime] = None
    gdpr_consent_text_version: Optional[str] = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)

    # Business data
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    budget: Optional[float] = None
    property_interest: Optional[str] = None
    notes: Optional[str] = None
    nationality: Optional[str] = None
    zone_interest: Optional[str] = None
    qualification_score: Optional[int] = Field(default=None, ge=0, le=100)
    qualification_tier: Optional[HNWIQualificationTier] = None
    hnwi_intent_signal: Optional[str] = None
    email_verified: bool = False
    email_verification_source: Optional[str] = None
    hnwi_source_channel: Optional[HNWISourceChannel] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicLeadCaptureRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=64)
    budget: Optional[float] = None
    property_interest: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=3000)
    nationality: Optional[str] = Field(default=None, max_length=64)
    zone_interest: Optional[str] = Field(default=None, max_length=128)
    source: Optional[str] = Field(default="web-cta", max_length=128)
    source_system: str = Field(default="cta_web", max_length=64)
    source_channel: str = Field(default="website", max_length=64)
    source_detail: str = Field(default="public_cta_form", max_length=128)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    source_referrer: Optional[str] = Field(default=None, max_length=1000)
    gdpr_consent: bool
    gdpr_consent_at: Optional[datetime] = None
    gdpr_consent_text_version: Optional[str] = Field(default="v1", max_length=32)

    @model_validator(mode="after")
    def validate_gdpr_consent(self) -> "PublicLeadCaptureRequest":
        if not self.gdpr_consent:
            raise ValueError("gdpr_consent is required")
        return self

class PropertyIngestionPayload(BaseModel):
    org_id: str
    external_id: str
    connector_name: Optional[str] = None
    trace_id: Optional[str] = None
    source_system: PropertySourceSystem
    source_portal: PropertySourcePortal
    captured_at: datetime = Field(default_factory=datetime.utcnow)

    # Business data
    title: str
    address: str
    price_eur: float
    zone: Optional[str] = None
    built_area_m2: Optional[float] = None
    useful_area_m2: Optional[float] = None
    plot_area_m2: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SellerSignalItem(BaseModel):
    external_id: Optional[str] = None
    nombre_propietario: Optional[str] = None
    empresa: Optional[str] = None
    website_url: Optional[str] = None
    anuncio_url: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono_contacto: Optional[str] = None
    whatsapp_contacto: Optional[str] = None
    direccion: Optional[str] = None
    zona: Optional[str] = None
    fuente: Optional[str] = None
    precio_publicado: Optional[float] = None
    precio_estimado: Optional[float] = None
    superficie_m2: Optional[float] = None
    tipo_propiedad: Optional[str] = None
    dias_en_mercado: Optional[int] = None
    prioridad: Optional[int] = None
    notas: Optional[str] = None
    senales_motivacion: List[str] = Field(default_factory=list)
    datos_extraidos: Dict[str, Any] = Field(default_factory=dict)

class SellerSignalIngestionPayload(BaseModel):
    org_id: str
    connector_name: str
    trace_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    signals: List[SellerSignalItem] = Field(default_factory=list)

class IngestionEvent(BaseModel):
    id: Optional[str] = None
    org_id: str
    entity_type: EntityType
    external_id: str
    connector_name: str
    status: IngestionStatus
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    payload: Dict[str, Any]
    error_detail: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    processed_entity_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    dedupe_key: str

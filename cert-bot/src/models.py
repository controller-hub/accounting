from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FormType(str, Enum):
    """Certificate form types the bot can identify."""

    MTC_UNIFORM = "MTC Uniform Certificate"
    SST_F0003 = "SST Certificate of Exemption (F0003)"
    TX_01_339 = "Texas 01-339"
    NY_ST_120 = "New York ST-120 (Resale)"
    NY_ST_121 = "New York ST-121 (Exempt Use)"
    NY_ST_119_1 = "New York ST-119.1 (Exempt Org)"
    NY_GOV_LETTER = "New York Government Letter"
    OH_STEC_B = "Ohio STEC-B"
    OH_DIRECT_PAY = "Ohio Direct Pay Permit"
    PA_REV_1220 = "Pennsylvania REV-1220"
    IA_31_014A = "Iowa 31-014a"
    MA_ST_2 = "Massachusetts ST-2 (Exempt Org)"
    MA_ST_5 = "Massachusetts ST-5 (Resale)"
    TN_GOV = "Tennessee Government (RV-F1301301)"
    TN_EXEMPT_ORG = "Tennessee Exempt Org (RV-F1306901)"
    CT_CERT_119 = "Connecticut CERT-119"
    CT_CERT_100 = "Connecticut CERT-100/101"
    MD_GOV_1 = "Maryland GOV-1 Card"
    MD_NONGOV_1 = "Maryland NONGOV-1 Card"
    FL_DR_14 = "Florida DR-14"
    IL_E99 = "Illinois E-99"
    IL_STAX_70 = "Illinois STAX-70"
    AL_STE_1 = "Alabama STE-1"
    WA_RESELLER = "Washington Reseller Permit"
    VT_S_3 = "Vermont S-3"
    AZ_5000 = "Arizona Form 5000"
    KY_51A126 = "Kentucky 51A126"
    FEDERAL_SF_1094 = "Federal SF-1094"
    FEDERAL_GSA_CARD = "Federal GSA SmartPay Card"
    FEDERAL_LETTERHEAD = "Federal Agency Letterhead"
    GOVERNMENT_ISSUED_CARD = "Government-Issued Exemption Card"
    STATE_ISSUED_CERT = "State-Issued Certificate"
    CUSTOM_LETTER = "Custom Letter/Other"
    UNKNOWN = "Unknown"


class EntityType(str, Enum):
    FEDERAL_GOVERNMENT = "Federal Government"
    STATE_GOVERNMENT = "State Government"
    LOCAL_GOVERNMENT = "Local Government"
    TRIBAL = "Tribal Nation/Enterprise"
    NONPROFIT_501C3 = "501(c)(3) Nonprofit"
    EXEMPT_ORG_OTHER = "Exempt Organization (Other)"
    FOR_PROFIT = "For-Profit Business"
    EDUCATIONAL = "Educational Institution"
    RELIGIOUS = "Religious Organization"
    UNKNOWN = "Unknown"


class ValidationPathway(int, Enum):
    STANDARD_SELF_COMPLETED = 1
    GOV_CARD_NO_EXPIRY = 2
    GOV_CARD_WITH_EXPIRY = 3
    STATE_ISSUED_CERT = 4
    FEDERAL_EXEMPTION = 5
    MULTI_STATE_UNIFORM = 6
    SPECIAL_PERMIT = 7


class ExemptionCategory(str, Enum):
    GOVERNMENT = "Government Entity"
    RESALE = "Resale"
    NONPROFIT = "Nonprofit/Tax-Exempt Organization"
    MANUFACTURING = "Manufacturing"
    AGRICULTURE = "Agriculture"
    COMMON_CARRIER = "Common Carrier/Transportation"
    INDUSTRIAL_RD = "Industrial Use / R&D"
    CONSTRUCTION = "Construction Contractor"
    DIRECT_PAY = "Direct Pay Permit"
    DIPLOMATIC = "Diplomatic/Foreign"
    OTHER = "Other"


class ResaleTier(int, Enum):
    STRONG = 1
    PLAUSIBLE = 2
    WEAK = 3
    IMPLAUSIBLE = 4


class Disposition(str, Enum):
    VALIDATED = "VALIDATED"
    VALIDATED_WITH_NOTES = "VALIDATED_WITH_NOTES"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class SellerProtectionStandard(str, Enum):
    SST_FOUR_CORNERS = "SST Four Corners (SSUTA § 317)"
    GOOD_FAITH = "Good Faith"
    FEDERAL_SUPREMACY = "Federal Supremacy Clause"


class CheckSeverity(str, Enum):
    HARD_FAIL = "HARD_FAIL"
    SOFT_FLAG = "SOFT_FLAG"
    REASONABLENESS = "REASON"
    INFO = "INFO"


class CheckResult(BaseModel):
    """Result of a single validation check."""

    check_name: str
    passed: bool
    severity: CheckSeverity
    message: str
    field: Optional[str] = None
    recommendation: Optional[str] = None


class ExtractedFields(BaseModel):
    """Fields extracted from a certificate via OCR/parsing."""

    purchaser_name: Optional[str] = None
    purchaser_address: Optional[str] = None
    purchaser_state: Optional[str] = None
    purchaser_city: Optional[str] = None
    purchaser_zip: Optional[str] = None
    purchaser_tax_id: Optional[str] = None
    purchaser_fein: Optional[str] = None
    seller_name: Optional[str] = None
    seller_address: Optional[str] = None
    exemption_reason: Optional[str] = None
    exemption_category: Optional[ExemptionCategory] = None
    exemption_states: list[str] = Field(default_factory=list)
    signature_present: Optional[bool] = None
    cert_date: Optional[date] = None
    expiration_date: Optional[date] = None
    is_blanket: Optional[bool] = None
    single_purchase_ref: Optional[str] = None
    description_of_items: Optional[str] = None
    business_type: Optional[str] = None
    form_type_detected: Optional[FormType] = None
    account_number: Optional[str] = None
    issuing_authority: Optional[str] = None
    permit_number: Optional[str] = None
    permit_expiration: Optional[date] = None
    raw_text: Optional[str] = None
    extraction_confidence: float = 0.0


class ValidationResult(BaseModel):
    """Complete validation output for a single certificate."""

    cert_id: Optional[str] = None
    avalara_cert_id: Optional[int] = None
    customer_name: str
    customer_sfdc_id: Optional[str] = None
    state: str
    form_type: FormType
    entity_type: EntityType
    pathway: ValidationPathway
    exemption_category: Optional[ExemptionCategory] = None
    seller_protection_standard: SellerProtectionStandard
    disposition: Disposition
    confidence_score: int = Field(ge=0, le=100)
    checks: list[CheckResult] = Field(default_factory=list)
    hard_fails: list[CheckResult] = Field(default_factory=list)
    soft_flags: list[CheckResult] = Field(default_factory=list)
    reasonableness_flags: list[CheckResult] = Field(default_factory=list)
    expiration_date: Optional[date] = None
    expiration_rule: Optional[str] = None
    renewal_action: Optional[str] = None
    resale_tier: Optional[ResaleTier] = None
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_confidence: float = 0.0
    correction_email_needed: bool = False
    correction_items: list[str] = Field(default_factory=list)
    human_review_needed: bool = False
    human_review_reason: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

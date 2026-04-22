from __future__ import annotations

from typing import Literal, TypedDict, NotRequired, Any


# ============================================================
# Core enums / literals
# ============================================================

ProductGroup = Literal["textiles", "batteries", "electrical_appliances"]

SectorProfileName = Literal[
    "textile_core_v1",
    "battery_passport_annex_xiii_v1",
    "electrical_appliance_espr_ready_v1",
]

RegulatorySource = Literal[
    "REG_2024_1781_ESPR",
    "REG_2023_1542_BATTERIES",
    "REG_2017_1369_ENERGY_LABELLING",
    "SECTORAL_ACT_PENDING",
]

ConfidenceSource = Literal[
    "lookup_table",
    "regulation_text",
    "model_estimate",
    "insufficient_data",
]

MissingSeverity = Literal["critical", "required", "recommended", "optional"]

RiskSeverity = Literal["high", "medium", "low"]

ActionPriority = Literal["now", "soon", "later"]

ActionOwner = Literal[
    "manufacturer",
    "importer",
    "brand_owner",
    "supplier",
    "internal_compliance",
    "unknown",
]

SourceDomain = Literal[
    "vision",
    "regulatory",
    "legal",
    "lca",
    "gs1",
    "audit",
    "system",
]

GranularityLevel = Literal["item", "batch", "model"]

HumanReviewStatus = Literal["not_reviewed", "reviewed", "approved", "rejected"]


AgentName = Literal[
    "VisionAgent",
    "RegulatoryConsultant",
    "LegalAgent",
    "LCASpecialist",
    "GS1Specialist",
    "DataAuditAgent",
]

AGENT_NAME_VALUES = (
    "VisionAgent",
    "RegulatoryConsultant",
    "LegalAgent",
    "LCASpecialist",
    "GS1Specialist",
    "DataAuditAgent",
)

PRODUCT_GROUP_VALUES = (
    "textiles",
    "batteries",
    "electrical_appliances",
)

SECTOR_PROFILE_NAME_VALUES = (
    "textile_core_v1",
    "battery_passport_annex_xiii_v1",
    "electrical_appliance_espr_ready_v1",
)

CONFIDENCE_SOURCE_VALUES = (
    "lookup_table",
    "regulation_text",
    "model_estimate",
    "insufficient_data",
)

# ============================================================
# Shared helper objects
# ============================================================

class SectorProfile(TypedDict):
    name: SectorProfileName
    version: str
    regulatory_source: list[RegulatorySource]


class MissingField(TypedDict, total=False):
    field: str
    severity: MissingSeverity
    reason: str
    action: str | None
    regulatory_basis: str | None
    deadline: str | None
    can_be_inferred: bool
    requires_supplier_confirmation: bool
    source_domain: SourceDomain


class BusinessRisk(TypedDict):
    title: str
    severity: RiskSeverity
    why_it_matters: str


class RecommendedAction(TypedDict):
    priority: ActionPriority
    action: str
    owner: ActionOwner


class SupplierRequest(TypedDict, total=False):
    request: str
    why_needed: str
    document_type: str | None


class WhereToGetData(TypedDict):
    missing_topic: str
    source: str
    how_to_obtain: str


# ============================================================
# Domain data: ESPR core slice
# This is NOT a full copy of regulatedCore from universal_dpp.json.
# It is the agent-owned intermediate slice used by DPPGenerator.
# ============================================================

class EsprCoreData(TypedDict, total=False):
    product_group: ProductGroup
    sector_profile: SectorProfile

    product_name: str | None
    product_description: str | None
    brand_name: str | None
    model_name: str | None
    model_number: str | None
    serial_number: str | None
    batch_lot: str | None
    product_image_url: str | None

    espr_category: ProductGroup
    cn_code: str | None
    granularity_level: GranularityLevel | None
    legal_basis: list[str]

    country_of_manufacture: str | None
    country_of_origin: str | None
    year_of_manufacture: int | None

    visible_markings: list[str]
    visible_certifications: list[str]
    visible_warnings: list[str]

    identifiers_hint: dict[str, Any]
    data_carrier_hint: dict[str, Any]
    compliance_hint: dict[str, Any]
    operator_hint: dict[str, Any]
    facility_hint: dict[str, Any]
    registry_hint: dict[str, Any]

    product_group_hint: ProductGroup | None


# ============================================================
# Sectoral slices
# Only ONE of these must be non-None in domain_data.sectoral
# ============================================================

class TextileMaterialCompositionItem(TypedDict, total=False):
    component: str
    material: str
    percentage: float | None
    recycled_content_percentage: float | None
    recycled_content_type: Literal["post_consumer", "pre_consumer", "unknown"] | None
    bio_based: bool | None
    material_origin_country: str | None
    certifications: list[str]


class TextileSectorData(TypedDict, total=False):
    care_symbols: list[str]
    care_instructions_text: str | None
    material_composition: list[TextileMaterialCompositionItem]
    substances_of_concern_present: bool | None
    svhc_list: list[dict[str, Any]]
    manufacturing_steps: list[dict[str, Any]]
    country_of_manufacture: str | None
    country_of_origin: str | None
    year_of_manufacture: int | None
    durability_years: float | None
    durability_basis: Literal["measured", "estimated"] | None
    wash_resistance: dict[str, Any]
    abrasion_resistance: dict[str, Any]
    colour_fastness: dict[str, Any]
    pilling_resistance: dict[str, Any]
    repairability_applicable: bool | None
    repair_service_available: bool | None
    repair_instructions_url: str | None
    reusable: bool | None
    recyclable: bool | None
    take_back_available: bool | None
    disassembly_required: bool | None
    certifications: list[dict[str, Any]]


class BatterySectorData(TypedDict, total=False):
    battery_category: Literal["portable", "lmt", "sli", "industrial", "electric_vehicle"] | None
    chemistry: Literal[
        "lithium_ion",
        "lithium_metal",
        "lead_acid",
        "nickel_metal_hydride",
        "nickel_cadmium",
        "sodium_ion",
        "other",
    ] | None
    is_rechargeable: bool | None
    passport_required: bool | None
    passport_requirement_basis: str | None

    battery_model_identifier: str | None
    manufacturer_battery_identifier: str | None
    serial_number: str | None
    manufacturing_date: str | None
    manufacturing_place: str | None

    battery_mass_kg: float | None
    active_material_mass_kg: float | None
    capacity_kwh: float | None
    rated_capacity_ah: float | None
    nominal_voltage_v: float | None

    round_trip_energy_efficiency: float | None
    cycle_life: int | None
    calendar_life_years: float | None

    state_of_health_present: bool | None
    state_of_health_value_percent: float | None
    bms_present: bool | None

    carbon_footprint_declared: bool | None
    gwp_kg_co2e_per_kwh: float | None
    performance_class: str | None
    methodology_reference: str | None
    verification_reference: str | None

    critical_raw_materials: list[dict[str, Any]]
    hazardous_substances: dict[str, Any]
    recycled_content: list[dict[str, Any]]

    ce_marking_present: bool | None
    declaration_of_conformity_reference: str | None
    label_information: dict[str, Any]
    safety_instructions_url: str | None
    technical_documentation_reference: str | None

    removability_and_replaceability: dict[str, Any]
    collection_and_take_back: dict[str, Any]
    second_life_status: dict[str, Any]


class ElectricalSectorData(TypedDict, total=False):
    appliance_type: Literal[
        "washing_machine",
        "washer_dryer",
        "dishwasher",
        "refrigerator",
        "freezer",
        "television",
        "display",
        "vacuum_cleaner",
        "oven",
        "range_hood",
        "air_conditioner",
        "heat_pump",
        "water_heater",
        "lighting",
        "small_household_appliance",
        "other",
    ] | None
    energy_related_product: bool | None
    energy_label_required: bool | None
    eprel_registered: bool | None

    energy_class: str | None
    energy_consumption_kwh_per_year: float | None
    energy_consumption_per_cycle_kwh: float | None
    eco_programme_available: bool | None
    test_standard: str | None
    water_consumption_litres_per_cycle: float | None
    noise_emission_db: float | None
    performance_claims: list[str]

    repairability_applicable: bool | None
    repairability_score: float | None
    disassembly_method: str | None
    service_information_available: bool | None
    repair_instructions_url: str | None
    software_support_years: float | None
    spare_parts: dict[str, Any]

    material_composition_summary: list[dict[str, Any]]
    substances_of_concern: dict[str, Any]
    contains_battery: bool | None
    embedded_battery_removability: Literal[
        "user_removable",
        "professional_removable",
        "not_removable",
    ] | None

    user_manual_url: str | None
    installation_manual_url: str | None
    technical_documentation_reference: str | None
    firmware_version: str | None
    software_update_policy: str | None
    cybersecurity_support_statement: str | None

    recyclable: bool | None
    recycling_instructions: str | None
    waste_collection_information_available: bool | None
    take_back_available: bool | None
    critical_components_for_depollution: list[str]


class SectoralData(TypedDict):
    textiles: TextileSectorData | None
    batteries: BatterySectorData | None
    electrical_appliances: ElectricalSectorData | None


class DomainData(TypedDict):
    espr_core: EsprCoreData
    sectoral: SectoralData


# ============================================================
# Assessment
# ============================================================

class Assessment(TypedDict, total=False):
    confidence_source: ConfidenceSource
    confidence_score: float | None
    missing_fields: list[MissingField]
    warnings: list[str]
    assumptions: list[str]
    contradictions: list[str]
    needs_human_review: bool


# ============================================================
# Advisory
# agent_summary is the only field expected everywhere.
# Other fields may be empty/absent for Vision/GS1.
# ============================================================

class Advisory(TypedDict, total=False):
    agent_summary: str
    business_risks: list[BusinessRisk]
    recommended_next_actions: list[RecommendedAction]
    supplier_requests: list[SupplierRequest]
    where_to_get_data: list[WhereToGetData]
    next_batch_improvements: list[str]


# ============================================================
# Main agent payload
# ============================================================

class AgentPayload(TypedDict):
    domain_data: DomainData
    assessment: Assessment
    advisory: Advisory


# ============================================================
# Optional: full BaseAgent result envelope
# Keep compatible with BaseAgent._format_success/_format_error
# ============================================================

class AgentResult(TypedDict, total=False):
    success: bool
    agent: str
    is_mock: bool
    data: AgentPayload
    errors: list[str]


# ============================================================
# Per-agent expectations
# These are NOT validation results themselves.
# They are declarative rules used by validators.
# ============================================================

AGENT_NAMES = Literal[
    "VisionAgent",
    "RegulatoryConsultant",
    "LegalAgent",
    "LCASpecialist",
    "GS1Specialist",
    "DataAuditAgent",
]

MAX_AGENT_SUMMARY_CHARS = 500

EXPECTED_SECTOR_PROFILE_BY_GROUP: dict[ProductGroup, SectorProfileName] = {
    "textiles": "textile_core_v1",
    "batteries": "battery_passport_annex_xiii_v1",
    "electrical_appliances": "electrical_appliance_espr_ready_v1",
}

EXPECTED_ESPR_CATEGORY_BY_GROUP: dict[ProductGroup, ProductGroup] = {
    "textiles": "textiles",
    "batteries": "batteries",
    "electrical_appliances": "electrical_appliances",
}
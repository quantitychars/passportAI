from __future__ import annotations

from typing import Any, cast

from .contracts import (
    AGENT_NAME_VALUES,
    AgentPayload,
    ProductGroup,
    CONFIDENCE_SOURCE_VALUES,
    EXPECTED_ESPR_CATEGORY_BY_GROUP,
    EXPECTED_SECTOR_PROFILE_BY_GROUP,
    MAX_AGENT_SUMMARY_CHARS,
    PRODUCT_GROUP_VALUES,
    SECTOR_PROFILE_NAME_VALUES,
)


VALID_AGENT_NAMES = set(AGENT_NAME_VALUES)
VALID_PRODUCT_GROUPS = set(PRODUCT_GROUP_VALUES)
VALID_SECTOR_PROFILE_NAMES = set(SECTOR_PROFILE_NAME_VALUES)
VALID_CONFIDENCE_SOURCES = set(CONFIDENCE_SOURCE_VALUES)


def validate_common_agent_output(payload: AgentPayload) -> list[str]:
    """Validate structural rules shared by all agent payloads.

    Important:
    - This function checks only truly common invariants.
    - Regulatory alignment (product_group/espr_category/sector_profile)
      is validated in agent-specific rules where appropriate.
    """
    errors: list[str] = []

    if not isinstance(payload, dict):
        return ["payload must be a dict"]

    domain_data = payload.get("domain_data")
    assessment = payload.get("assessment")
    advisory = payload.get("advisory")

    if not isinstance(domain_data, dict):
        errors.append("domain_data must be a dict")
        return errors

    if not isinstance(assessment, dict):
        errors.append("assessment must be a dict")
        return errors

    if not isinstance(advisory, dict):
        errors.append("advisory must be a dict")
        return errors

    espr_core = domain_data.get("espr_core")
    sectoral = domain_data.get("sectoral")

    if not isinstance(espr_core, dict):
        errors.append("domain_data.espr_core must be a dict")
        return errors

    if not isinstance(sectoral, dict):
        errors.append("domain_data.sectoral must be a dict")
        return errors

    errors.extend(_validate_exactly_one_sectoral_block(sectoral))
    errors.extend(_validate_agent_summary(advisory))

    return errors


def validate_agent_specific_output(agent_name: str, payload: AgentPayload) -> list[str]:
    """Validate per-agent minimum usefulness and ownership rules."""
    errors: list[str] = []

    if agent_name not in VALID_AGENT_NAMES:
        return [f"unknown agent name: {agent_name}"]

    domain_data = cast(dict[str, Any], payload.get("domain_data", {}))
    espr_core = cast(dict[str, Any], domain_data.get("espr_core", {}))
    sectoral = cast(dict[str, Any], domain_data.get("sectoral", {}))
    assessment = cast(dict[str, Any], payload.get("assessment", {}))
    advisory = cast(dict[str, Any], payload.get("advisory", {}))

    missing_fields = assessment.get("missing_fields", [])
    warnings = assessment.get("warnings", [])
    needs_human_review = assessment.get("needs_human_review")
    confidence_source = assessment.get("confidence_source")

    business_risks = advisory.get("business_risks", [])
    recommended_next_actions = advisory.get("recommended_next_actions", [])
    where_to_get_data = advisory.get("where_to_get_data", [])
    agent_summary = advisory.get("agent_summary")

    if agent_name == "VisionAgent":
        if not _is_valid_confidence_source(confidence_source):
            errors.append(
                "VisionAgent.assessment.confidence_source is required and must be valid"
            )
        if not isinstance(warnings, list):
            errors.append("VisionAgent.assessment.warnings must be a list")
        if not isinstance(needs_human_review, bool):
            errors.append("VisionAgent.assessment.needs_human_review must be a bool")
        if not _is_non_empty_string(agent_summary):
            errors.append("VisionAgent.advisory.agent_summary is required")

    elif agent_name == "RegulatoryConsultant":
        if not _is_valid_product_group(espr_core.get("product_group")):
            errors.append(
                "RegulatoryConsultant.domain_data.espr_core.product_group is required"
            )
        if not isinstance(espr_core.get("sector_profile"), dict):
            errors.append(
                "RegulatoryConsultant.domain_data.espr_core.sector_profile is required"
            )
        if not _is_valid_product_group(espr_core.get("espr_category")):
            errors.append(
                "RegulatoryConsultant.domain_data.espr_core.espr_category is required"
            )

        errors.extend(_validate_group_alignment(espr_core, sectoral))

        if not _has_any_signal(missing_fields, business_risks, recommended_next_actions):
            errors.append(
                "RegulatoryConsultant must provide at least one of: "
                "assessment.missing_fields, advisory.business_risks, "
                "advisory.recommended_next_actions"
            )
        if not _is_non_empty_string(agent_summary):
            errors.append("RegulatoryConsultant.advisory.agent_summary is required")

    elif agent_name == "LegalAgent":
        if not _has_any_signal(
            missing_fields,
            business_risks,
            espr_core.get("compliance_hint"),
        ):
            errors.append(
                "LegalAgent must provide at least one of: "
                "assessment.missing_fields, advisory.business_risks, "
                "domain_data.espr_core.compliance_hint"
            )
        if not _is_non_empty_string(agent_summary):
            errors.append("LegalAgent.advisory.agent_summary is required")

    elif agent_name == "LCASpecialist":
        has_domain_lca_signal = _has_any_signal(
            domain_data.get("voluntary_esg"),
            _get_selected_sectoral_block(sectoral),
        )
        has_supporting_signal = _has_any_signal(
            missing_fields,
            where_to_get_data,
        )

        if not (has_domain_lca_signal or has_supporting_signal):
            errors.append(
                "LCASpecialist must provide either domain LCA data, "
                "assessment.missing_fields, or advisory.where_to_get_data"
            )

        if not _is_valid_confidence_source(confidence_source):
            errors.append(
                "LCASpecialist.assessment.confidence_source is required and must be valid"
            )
        if not _is_non_empty_string(agent_summary):
            errors.append("LCASpecialist.advisory.agent_summary is required")

    elif agent_name == "GS1Specialist":
        if not _has_any_signal(
            espr_core.get("identifiers_hint"),
            espr_core.get("data_carrier_hint"),
        ):
            errors.append(
                "GS1Specialist must provide domain_data.espr_core.identifiers_hint "
                "or domain_data.espr_core.data_carrier_hint"
            )
        if not isinstance(warnings, list):
            errors.append("GS1Specialist.assessment.warnings must be a list")
        if not _is_non_empty_string(agent_summary):
            errors.append("GS1Specialist.advisory.agent_summary is required")

    elif agent_name == "DataAuditAgent":
        if not isinstance(missing_fields, list) or len(missing_fields) == 0:
            errors.append(
                "DataAuditAgent.assessment.missing_fields must be a non-empty list"
            )
        if not isinstance(warnings, list):
            errors.append("DataAuditAgent.assessment.warnings must be a list")
        if not isinstance(needs_human_review, bool):
            errors.append("DataAuditAgent.assessment.needs_human_review must be a bool")
        if not isinstance(recommended_next_actions, list) or len(recommended_next_actions) == 0:
            errors.append(
                "DataAuditAgent.advisory.recommended_next_actions must be a non-empty list"
            )
        if not _is_non_empty_string(agent_summary):
            errors.append("DataAuditAgent.advisory.agent_summary is required")

        # DataAuditAgent is the second place where sector/classification alignment
        # should be enforced to catch pipeline drift.
        errors.extend(_validate_group_alignment(espr_core, sectoral))

    return errors


def validate_agent_output(agent_name: str, payload: AgentPayload) -> list[str]:
    """Convenience wrapper: common + agent-specific validation."""
    errors: list[str] = []
    errors.extend(validate_common_agent_output(payload))
    errors.extend(validate_agent_specific_output(agent_name, payload))
    return errors


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _validate_exactly_one_sectoral_block(sectoral: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_keys = {"textiles", "batteries", "electrical_appliances"}
    actual_keys = set(sectoral.keys())
    missing_keys = expected_keys - actual_keys
    if missing_keys:
        errors.append(
            "domain_data.sectoral is missing keys: " + ", ".join(sorted(missing_keys))
        )

    filled = [
        key
        for key in ("textiles", "batteries", "electrical_appliances")
        if sectoral.get(key) is not None
    ]

    if len(filled) != 1:
        errors.append(
            "exactly one sectoral block must be non-None; "
            f"found {len(filled)} filled blocks: {filled}"
        )

    return errors


def _validate_group_alignment(espr_core: dict[str, Any], sectoral: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    product_group = espr_core.get("product_group")
    espr_category = espr_core.get("espr_category")
    sector_profile = espr_core.get("sector_profile")

    if not _is_valid_product_group(product_group):
        errors.append("domain_data.espr_core.product_group must be set to a valid product group")
        return errors

    if not _is_valid_product_group(espr_category):
        errors.append("domain_data.espr_core.espr_category must be set to a valid product group")
        return errors

    if not isinstance(sector_profile, dict):
        errors.append("domain_data.espr_core.sector_profile must be a dict")
        return errors

    sector_profile_name = sector_profile.get("name")
    if not _is_valid_sector_profile_name(sector_profile_name):
        errors.append("domain_data.espr_core.sector_profile.name must be a valid sector profile")
        return errors

    filled_block = _get_filled_sectoral_name(sectoral)
    if filled_block is None:
        return errors

    if filled_block != product_group:
        errors.append(
            f"sectoral block '{filled_block}' does not match "
            f"espr_core.product_group '{product_group}'"
        )

    expected_category = EXPECTED_ESPR_CATEGORY_BY_GROUP[product_group]
    if espr_category != expected_category:
        errors.append(
            f"espr_core.espr_category must be '{expected_category}' "
            f"for product_group '{product_group}'"
        )

    expected_profile = EXPECTED_SECTOR_PROFILE_BY_GROUP[product_group]
    if sector_profile_name != expected_profile:
        errors.append(
            f"sector_profile.name must be '{expected_profile}' "
            f"for product_group '{product_group}'"
        )

    return errors


def _validate_agent_summary(advisory: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = advisory.get("agent_summary")

    if summary is None:
        return errors

    if not isinstance(summary, str):
        errors.append("advisory.agent_summary must be a string")
        return errors

    if len(summary) > MAX_AGENT_SUMMARY_CHARS:
        errors.append(
            f"advisory.agent_summary exceeds {MAX_AGENT_SUMMARY_CHARS} characters"
        )

    if "\n-" in summary or "\n•" in summary:
        errors.append("advisory.agent_summary must not contain inline bullet lists")

    return errors


def _get_filled_sectoral_name(sectoral: dict[str, Any]) -> ProductGroup | None:
    filled = [
        key
        for key in ("textiles", "batteries", "electrical_appliances")
        if sectoral.get(key) is not None
    ]
    if len(filled) != 1:
        return None
    return cast(ProductGroup, filled[0])


def _get_selected_sectoral_block(sectoral: dict[str, Any]) -> Any:
    filled_name = _get_filled_sectoral_name(sectoral)
    if filled_name is None:
        return None
    return sectoral.get(filled_name)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_valid_product_group(value: Any) -> bool:
    return value in VALID_PRODUCT_GROUPS


def _is_valid_sector_profile_name(value: Any) -> bool:
    return value in VALID_SECTOR_PROFILE_NAMES


def _is_valid_confidence_source(value: Any) -> bool:
    return value in VALID_CONFIDENCE_SOURCES


def _has_any_signal(*values: Any) -> bool:
    for value in values:
        if isinstance(value, bool):
            if value:
                return True
        elif isinstance(value, (list, dict, str, tuple, set)):
            if len(value) > 0:
                return True
        elif value is not None:
            return True
    return False

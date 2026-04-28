from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PassportRenderer:
    """Projection-only HTML renderer for a generated Digital Product Passport.

    This component renders the already-generated passport.json into a human-readable
    artifact. It must not synthesize product facts, rerun audit logic, or call agents.
    """

    TEMPLATE_NAME = "passport.html.jinja2"
    SECTOR_KEY_BY_GROUP = {
        "textiles": "sectoralTextile",
        "batteries": "sectoralBattery",
        "electrical_appliances": "sectoralElectricalAppliance",
    }

    FIELD_LABELS = {
        "dpp.regulatedCore.compliance.declarationOfConformity": "Declaration of conformity",
        "dpp.regulatedCore.compliance.technicalDocumentation": "Technical documentation",
        "dpp.regulatedCore.dataCarrier.carrierValue": "QR / data carrier value",
        "dpp.regulatedCore.dataCarrier.resolverUrl": "Public resolver URL",
        "dpp.regulatedCore.dataCarrier.isPersistent": "Persistent data carrier URL",
        "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.scheme": "Product identifier scheme",
        "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.value": "Persistent product identifier",
        "dpp.regulatedCore.identifiers.uniqueOperatorIdentifier.value": "Economic operator identifier",
        "dpp.regulatedCore.identifiers.uniqueFacilityIdentifier.value": "Manufacturing facility identifier",
        "dpp.regulatedCore.productIdentity.cnCode": "Customs CN code",
        "dpp.sectoralTextile.composition.materialComposition": "Textile material composition",
        "dpp.sectoralTextile.substances": "Textile substances declaration",
        "dpp.sectoralTextile.careAndUse.careSymbols": "Care symbols",
        "dpp.sectoralTextile.certificationAndClaims.certifications": "Textile certifications",
        "dpp.sectoralBattery.batteryClassification.batteryCategory": "Battery category",
        "dpp.sectoralBattery.batteryClassification.chemistry": "Battery chemistry",
        "dpp.sectoralBattery.conformityAndInformation.declarationOfConformityReference": "Battery declaration of conformity",
        "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint": "Battery carbon footprint",
        "dpp.sectoralBattery.sustainabilityAndComposition.criticalRawMaterials": "Critical raw materials",
        "dpp.sectoralBattery.sustainabilityAndComposition.recycledContent": "Battery recycled content",
        "dpp.sectoralElectricalAppliance.applianceClassification.applianceType": "Appliance type",
        "dpp.sectoralElectricalAppliance.energyAndPerformance.energyEfficiency.energyClass": "Energy efficiency class",
        "dpp.sectoralElectricalAppliance.documentationAndSoftware.userManualUrl": "User manual URL",
        "dpp.voluntaryEsg.packaging.material": "Packaging material",
    }

    def __init__(
        self,
        *,
        templates_dir: str | Path | None = None,
        jinja_environment: Any | None = None,
    ) -> None:
        self.templates_dir = Path(templates_dir or Path("templates"))
        self.jinja_environment = jinja_environment

    def generate(
        self,
        *,
        passport_json: dict[str, Any],
        output_dir: str | Path,
        passport_id: str,
        gap_report_filename: str = "gap_report.html",
        passport_json_filename: str = "passport.json",
        generated_at: datetime | None = None,
    ) -> Path:
        """Write passport.html for an already-generated passport.json artifact."""
        view_model = self.build_view_model(
            passport_json=passport_json,
            passport_id=passport_id,
            gap_report_filename=gap_report_filename,
            passport_json_filename=passport_json_filename,
            generated_at=generated_at,
        )

        rendered = self._render_template(view_model)
        output_path = Path(output_dir) / "passport.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        return output_path

    def build_view_model(
        self,
        *,
        passport_json: dict[str, Any],
        passport_id: str | None = None,
        gap_report_filename: str = "gap_report.html",
        passport_json_filename: str = "passport.json",
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Project passport.json into a human-readable template model."""
        if not isinstance(passport_json, dict):
            raise ValueError("passport_json must be a dict")

        credential_subject = passport_json.get("credentialSubject")
        if not isinstance(credential_subject, dict):
            raise ValueError("passport_json.credentialSubject must be a dict")

        dpp = credential_subject.get("dpp")
        if not isinstance(dpp, dict):
            raise ValueError("passport_json.credentialSubject.dpp must be a dict")
        if isinstance(dpp.get("dpp"), dict):
            raise ValueError(
                "passport_json.credentialSubject.dpp must contain the DPP payload directly, "
                "not nested under credentialSubject.dpp.dpp"
            )

        regulated_core = self._dict(dpp.get("regulatedCore"))
        product_identity = self._dict(regulated_core.get("productIdentity"))
        passport_identity = self._dict(regulated_core.get("passportIdentity"))
        data_carrier = self._dict(regulated_core.get("dataCarrier"))
        identifiers = self._dict(regulated_core.get("identifiers"))
        compliance = self._dict(regulated_core.get("compliance"))
        operator = self._dict(
            self._dict(regulated_core.get("economicOperators")).get(
                "responsibleEconomicOperator"
            )
        )
        access_control = self._dict(regulated_core.get("accessControl"))
        system_metadata = self._dict(dpp.get("systemMetadata"))
        quality = self._dict(system_metadata.get("qualityAssessment"))
        platform = self._dict(system_metadata.get("platform"))
        technical_assets = self._dict(system_metadata.get("technicalAssets"))
        provenance = self._dict(regulated_core.get("provenance"))

        product_group = self._string(dpp.get("productGroup")) or self._string(
            product_identity.get("esprCategory")
        ) or "unknown"
        sector_key = self.SECTOR_KEY_BY_GROUP.get(product_group, "")
        sector_data = self._dict(dpp.get(sector_key)) if sector_key else {}

        now = generated_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        readiness_score = self._int(quality.get("readinessScore"), default=0)
        status = self._string(passport_identity.get("status")) or "draft"
        human_review_status = self._string(platform.get("humanReviewStatus")) or "not_reviewed"
        missing_fields = self._normalize_missing_fields(quality.get("missingFields"))
        sector_summary = self._sector_summary(product_group, sector_data, compliance)

        return {
            "schema_version": "passport_html.v1",
            "generated_at": self._isoformat(now),
            "passport": {
                "id": self._string(passport_json.get("id")),
                "type": passport_json.get("type", []),
                "issuer_name": self._string(self._dict(passport_json.get("issuer")).get("name")) or "PassportAI",
                "issuer_id": self._string(self._dict(passport_json.get("issuer")).get("id")),
                "credential_subject_id": self._string(credential_subject.get("id")),
                "valid_from": self._string(passport_json.get("validFrom")),
                "valid_until": self._string(passport_json.get("validUntil")),
                "passport_id": self._string(dpp.get("passportId")) or passport_id,
                "schema_version": self._string(dpp.get("schemaVersion")),
                "status": status,
                "status_label": self._label(status),
                "is_draft": status != "issued",
                "readiness_score": readiness_score,
                "readiness_label": self._readiness_label(readiness_score, status),
                "human_review_status": human_review_status,
                "human_review_label": self._label(human_review_status),
            },
            "links": {
                "gap_report": gap_report_filename,
                "passport_json": passport_json_filename,
            },
            "product": {
                "name": self._display(product_identity.get("productName")),
                "brand": self._display(product_identity.get("brandName")),
                "description": self._display(product_identity.get("productDescription")),
                "group": product_group,
                "group_label": self._label(product_group),
                "espr_category": self._display(product_identity.get("esprCategory")),
                "cn_code": self._display(product_identity.get("cnCode")),
                "model_name": self._display(product_identity.get("modelName")),
                "model_number": self._display(product_identity.get("modelNumber")),
                "serial_number": self._display(product_identity.get("serialNumber")),
                "batch_lot": self._display(product_identity.get("batchLot")),
                "image_url": self._string(product_identity.get("productImageUrl")),
                "granularity_level": self._display(product_identity.get("granularityLevel")),
            },
            "identifiers": {
                "product": self._identifier_view(
                    self._dict(identifiers.get("persistentUniqueProductIdentifier"))
                ),
                "operator": self._identifier_view(
                    self._dict(identifiers.get("uniqueOperatorIdentifier"))
                ),
                "facility": self._identifier_view(
                    self._dict(identifiers.get("uniqueFacilityIdentifier"))
                ),
            },
            "data_carrier": {
                "type": self._display(data_carrier.get("type")),
                "standard": self._display(data_carrier.get("standard")),
                "carrier_value": self._display(data_carrier.get("carrierValue")),
                "resolver_url": self._display(data_carrier.get("resolverUrl")),
                "placement": self._display(data_carrier.get("physicalPlacement")),
                "is_persistent": bool(data_carrier.get("isPersistent", False)),
                "persistence_label": "Persistent" if data_carrier.get("isPersistent") else "Not yet persistent",
            },
            "operator": {
                "name": self._display(operator.get("name")),
                "role": self._display(operator.get("role")),
                "identifier_ref": self._display(operator.get("identifierRef")),
                "country": self._display(operator.get("country")),
                "email": self._display(operator.get("contactEmail")),
                "phone": self._display(operator.get("contactPhone")),
                "website": self._display(operator.get("website")),
            },
            "compliance": self._compliance_view(compliance),
            "sector": sector_summary,
            "evidence": {
                "missing_count": len(missing_fields),
                "required_missing_count": sum(
                    1 for item in missing_fields if item["severity"] in {"critical", "required"}
                ),
                "top_missing_fields": missing_fields[:8],
                "readiness_breakdown": self._dict(quality.get("readinessScoreBreakdown")),
            },
            "access_control": {
                "public_sections": self._list(access_control.get("publicSections")),
                "confidential_sections": self._list(access_control.get("confidentialBusinessInformation")),
                "restricted_sections": self._dict(access_control.get("restrictedSections")),
            },
            "technical": {
                "content_hash": self._display(technical_assets.get("contentHash")),
                "attachments": self._list(technical_assets.get("attachments")),
                "generator_name": self._display(platform.get("generatorName")),
                "generator_version": self._display(platform.get("generatorVersion")),
                "generation_method": self._display(platform.get("generationMethod")),
                "issuer_did": self._display(self._dict(provenance.get("issuer")).get("did")),
                "schema_version": self._display(dpp.get("schemaVersion")),
            },
        }

    # def _render_template(self, view_model: dict[str, Any]) -> str:
    #     try:
    #         environment = self.jinja_environment
    #         if environment is None:
    #             from jinja2 import Environment, FileSystemLoader, select_autoescape

    #             environment = Environment(
    #                 loader=FileSystemLoader(str(self.templates_dir)),
    #                 autoescape=select_autoescape(["html", "xml"]),
    #             )
    #         template = environment.get_template(self.TEMPLATE_NAME)
    #         return template.render(**view_model)
    #     except Exception:
    #         return self._render_fallback(view_model)
    def _render_template(self, view_model: dict[str, Any]) -> str:
        try:
            environment = self.jinja_environment
            if environment is None:
                from jinja2 import Environment, FileSystemLoader, select_autoescape

                environment = Environment(
                    loader=FileSystemLoader(str(self.templates_dir)),
                    autoescape=select_autoescape(["html", "xml"]),
                )

            template = environment.get_template(self.TEMPLATE_NAME)
            return template.render(**view_model)
        except Exception as exc:
            raise RuntimeError(
                f"PassportRenderer failed to render primary template "
                f"{self.templates_dir / self.TEMPLATE_NAME}: {exc}"
            ) from exc

    def _render_fallback(self, model: dict[str, Any]) -> str:
        product = model["product"]
        passport = model["passport"]
        links = model["links"]
        sector = model["sector"]
        evidence = model["evidence"]
        technical = model["technical"]

        sector_rows = "".join(
            (
                "<li>"
                f"<strong>{html.escape(item['label'])}</strong>: "
                f"{html.escape(str(item['value']))}"
                "</li>"
            )
            for item in sector.get("items", [])
        )

        missing_rows = "".join(
            (
                "<li>"
                f"{html.escape(item['field_label'])}: "
                f"{html.escape(item['action'])}"
                "</li>"
            )
            for item in evidence.get("top_missing_fields", [])
        )

        return f"""<!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <title>Digital Product Passport — {html.escape(product['name'])}</title>
    </head>
    <body>
    <h1>Digital Product Passport</h1>
    <h2>{html.escape(product['name'])}</h2>

    <p><strong>Status:</strong> {html.escape(passport['status_label'])}</p>
    <p><strong>Readiness:</strong> {passport['readiness_score']}/100</p>
    <p><strong>{html.escape(passport['readiness_label'])}</strong></p>

    <p>
        <a href="{html.escape(links['gap_report'])}">View Gap Report</a>
        ·
        <a href="{html.escape(links['passport_json'])}">Download JSON</a>
    </p>

    <h2>Product identity</h2>
    <p><strong>Brand:</strong> {html.escape(product['brand'])}</p>
    <p><strong>Product group:</strong> {html.escape(product['group_label'])}</p>
    <p><strong>Description:</strong> {html.escape(product['description'])}</p>

    <h2>{html.escape(sector.get('title', 'Sector passport data'))}</h2>
    <ul>{sector_rows}</ul>

    <h2>Top missing evidence</h2>
    <ul>{missing_rows}</ul>

    <h2>Technical appendix</h2>
    <p><strong>Content hash:</strong> {html.escape(technical['content_hash'])}</p>
    <p><strong>Machine-readable artifact:</strong> {html.escape(links['passport_json'])}</p>
    <p><strong>Readiness report:</strong> {html.escape(links['gap_report'])}</p>
    </body>
    </html>"""

    def _sector_summary(
        self,
        product_group: str,
        sector_data: dict[str, Any],
        compliance: dict[str, Any],
    ) -> dict[str, Any]:
        if product_group == "batteries":
            classification = self._dict(sector_data.get("batteryClassification"))
            identity = self._dict(sector_data.get("batteryIdentity"))
            sustainability = self._dict(sector_data.get("sustainabilityAndComposition"))
            conformity = self._dict(sector_data.get("conformityAndInformation"))
            carbon = self._dict(sustainability.get("carbonFootprint"))
            recycled = self._dict(sustainability.get("recycledContent"))
            return {
                "type": "batteries",
                "title": "Battery passport data",
                "items": [
                    self._item("Battery category", classification.get("batteryCategory"), "Regulatory battery category for passport obligations."),
                    self._item("Battery chemistry", classification.get("chemistry"), "Electrochemical chemistry confirmed from product evidence."),
                    self._item("Rechargeable", self._yes_no(classification.get("isRechargeable")), "Whether the battery is declared rechargeable."),
                    self._item("Battery model identifier", identity.get("batteryModelIdentifier"), "Battery model identifier from product or supplier data."),
                    self._item("Manufacturer battery identifier", identity.get("manufacturerBatteryIdentifier"), "Manufacturer-specific battery identifier."),
                    self._item("Declaration reference", conformity.get("declarationOfConformityReference"), "Sector-specific conformity document reference."),
                    self._item("Carbon footprint", self._declared_value(carbon.get("declared"), carbon.get("valueKgCo2e"), "kg CO₂e"), "Declared product-level carbon footprint evidence."),
                    self._item("Critical raw materials", self._list_display(sustainability.get("criticalRawMaterials")), "Declared critical raw material information."),
                    self._item("Recycled content", self._declared_value(recycled.get("declared"), recycled.get("overallPercentage"), "%"), "Declared recycled content percentage."),
                    self._item("CE marking visible", self._yes_no(conformity.get("ceMarkingPresent")), "Whether CE marking was visible or declared."),
                ],
            }

        if product_group == "textiles":
            composition = self._dict(sector_data.get("composition"))
            care = self._dict(sector_data.get("careAndUse"))
            substances = self._dict(sector_data.get("substances"))
            certifications = self._dict(sector_data.get("certificationAndClaims"))
            end_of_life = self._dict(sector_data.get("endOfLife"))
            return {
                "type": "textiles",
                "title": "Textile passport data",
                "items": [
                    self._item("Material composition", self._material_display(composition.get("materialComposition")), "Fiber or material breakdown from label/BOM evidence."),
                    self._item("Composition percentage check", composition.get("totalPercentageCheck"), "Total percentage validation for declared composition."),
                    self._item("Care symbols", self._list_display(care.get("careSymbols")), "Care label symbols or instructions."),
                    self._item("Care instructions", care.get("careInstructionsText"), "Text care instructions, if provided."),
                    self._item("Substances of concern", self._yes_no(substances.get("substancesOfConcernPresent")), "Declared substances-of-concern status."),
                    self._item("SVHC present", self._yes_no(substances.get("reachSvhcPresent")), "Declared REACH/SVHC status."),
                    self._item("Certifications", self._list_display(certifications.get("certifications")), "Verified textile certificates or claims."),
                    self._item("Reusable", self._yes_no(end_of_life.get("reusable")), "Whether reuse is supported by evidence."),
                    self._item("Recyclable", self._yes_no(end_of_life.get("recyclable")), "Whether recycling is supported by evidence."),
                ],
            }

        if product_group == "electrical_appliances":
            classification = self._dict(sector_data.get("applianceClassification"))
            energy = self._dict(self._dict(sector_data.get("energyAndPerformance")).get("energyEfficiency"))
            repair = self._dict(sector_data.get("repairAndService"))
            materials = self._dict(sector_data.get("materialsAndSubstances"))
            docs = self._dict(sector_data.get("documentationAndSoftware"))
            return {
                "type": "electrical_appliances",
                "title": "Electrical appliance passport data",
                "items": [
                    self._item("Appliance type", classification.get("applianceType"), "Appliance class used for sectoral evidence expectations."),
                    self._item("Energy class", energy.get("energyClass"), "Declared energy efficiency class."),
                    self._item("Energy label required", self._yes_no(classification.get("energyLabelRequired")), "Whether energy labelling applies."),
                    self._item("Repairability score", repair.get("repairabilityScore"), "Declared repairability score or status."),
                    self._item("Repair instructions", repair.get("repairInstructionsUrl"), "Stable repair instructions URL."),
                    self._item("User manual", docs.get("userManualUrl"), "Stable user manual URL."),
                    self._item("Technical documentation", docs.get("technicalDocumentationReference"), "Technical documentation reference."),
                    self._item("Battery included", self._yes_no(materials.get("batteryIncluded")), "Whether the appliance includes a battery."),
                ],
            }

        return {
            "type": product_group or "unknown",
            "title": "Sector passport data",
            "items": [],
        }

    def _normalize_missing_fields(self, value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            field = self._string(item.get("field"))
            if not field:
                continue
            severity = self._string(item.get("severity")) or "required"
            normalized.append(
                {
                    "field": field,
                    "field_label": self._field_label(field),
                    "severity": severity,
                    "severity_label": self._label(severity),
                    "action": self._humanize_field_references(
                        self._string(item.get("action"))
                        or f"Provide authoritative evidence for {self._field_label(field)}."
                    ),
                    "regulatory_basis": self._display(item.get("regulatoryBasis")),
                }
            )

        severity_order = {"critical": 0, "required": 1, "recommended": 2, "optional": 3}
        return sorted(
            normalized,
            key=lambda item: (severity_order.get(item["severity"], 99), item["field_label"]),
        )

    def _compliance_view(self, compliance: dict[str, Any]) -> dict[str, Any]:
        declaration = self._dict(compliance.get("declarationOfConformity"))
        technical = self._dict(compliance.get("technicalDocumentation"))
        return {
            "declaration_present": bool(declaration.get("present", False)),
            "declaration_required": bool(declaration.get("required", False)),
            "declaration_reference": self._display(declaration.get("documentReference")),
            "declaration_url": self._display(declaration.get("documentUrl")),
            "technical_present": bool(technical.get("present", False)),
            "technical_reference": self._display(technical.get("documentReference")),
            "technical_url": self._display(technical.get("documentUrl")),
            "technical_storage": self._display(technical.get("storageLocation")),
        }

    def _identifier_view(self, value: dict[str, Any]) -> dict[str, str]:
        return {
            "value": self._display(value.get("value")),
            "scheme": self._display(value.get("scheme")),
            "issuing_body": self._display(value.get("issuingBody")),
            "format": self._display(value.get("format")),
        }

    def _item(self, label: str, value: Any, description: str) -> dict[str, str]:
        return {
            "label": label,
            "value": self._display(value),
            "description": description,
            "is_missing": self._is_missing_value(value),
        }

    def _field_label(self, field: str) -> str:
        label = self.FIELD_LABELS.get(field)
        if label:
            return label
        leaf = field.split(".")[-1] if field else "field"
        return self._label(leaf)

    def _humanize_field_references(self, text: str) -> str:
        if not text:
            return ""
        result = text
        for field in sorted(self.FIELD_LABELS, key=len, reverse=True):
            result = result.replace(field, self.FIELD_LABELS[field])
        return result

    def _readiness_label(self, score: int, status: str) -> str:
        if status == "issued" and score >= 75:
            return "Publication-ready"
        if score >= 75:
            return "Ready for review"
        if score >= 50:
            return "Evidence gaps remain"
        return "Not publication-ready"

    def _declared_value(self, declared: Any, value: Any, suffix: str) -> str:
        if not declared:
            return "Not declared"
        if value is None or value == "":
            return "Declared; value not provided"
        return f"{value} {suffix}".strip()

    def _material_display(self, value: Any) -> str:
        if not isinstance(value, list) or not value:
            return "Not provided"
        parts = []
        for item in value:
            if not isinstance(item, dict):
                continue
            material = self._display(item.get("material"))
            percentage = item.get("percentage")
            component = self._display(item.get("component"))
            if percentage is None:
                parts.append(f"{material} ({component})")
            else:
                parts.append(f"{material} {percentage}% ({component})")
        return "; ".join(parts) or "Not provided"

    def _list_display(self, value: Any) -> str:
        items = self._list(value)
        if not items:
            return "Not provided"
        display_items = []
        for item in items:
            if isinstance(item, dict):
                display_items.append(
                    self._display(item.get("name") or item.get("material") or item.get("value") or item)
                )
            else:
                display_items.append(self._display(item))
        return ", ".join(display_items) if display_items else "Not provided"

    def _yes_no(self, value: Any) -> str:
        if value is None:
            return "Not provided"
        return "Yes" if bool(value) else "No"

    def _is_missing_value(self, value: Any) -> bool:
        if value is None:
            return True
        if value is False:
            return False
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized in {"", "not provided", "unknown", "none", "null"} or normalized.startswith("pending_")
        if isinstance(value, list):
            return len(value) == 0
        if isinstance(value, dict):
            return len(value) == 0
        return False

    def _display(self, value: Any) -> str:
        if value is None:
            return "Not provided"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else "Not provided"
        if isinstance(value, list):
            return self._list_display(value)
        if isinstance(value, dict):
            return ", ".join(f"{self._label(str(k))}: {self._display(v)}" for k, v in value.items()) or "Not provided"
        return str(value)

    def _string(self, value: Any) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else ""

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _list(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _int(self, value: Any, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _label(self, value: str) -> str:
        if not value:
            return "Not provided"
        text = value.replace("_", " ").replace("-", " ")
        chars: list[str] = []
        previous = ""
        for char in text:
            if previous and char.isupper() and (previous.islower() or previous.isdigit()):
                chars.append(" ")
            chars.append(char)
            previous = char
        return " ".join("".join(chars).split()).title()

    def _isoformat(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

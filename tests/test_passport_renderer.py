from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.passport_renderer import PassportRenderer


def _battery_passport(passport_id: str = "demo-passport") -> dict:
    return {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": f"did:web:passportai.example.com:passports:{passport_id}",
        "type": ["VerifiableCredential", "DigitalProductPassportCredential"],
        "issuer": {"id": "did:web:passportai.example.com", "name": "PassportAI"},
        "validFrom": "2026-04-27T00:00:00Z",
        "validUntil": "2036-04-25T00:00:00Z",
        "credentialSubject": {
            "id": "did:web:passportai.example.com:products:12345678901234",
            "dpp": {
                "schemaVersion": "3.0.0",
                "passportId": passport_id,
                "productGroup": "batteries",
                "sectorProfile": {
                    "name": "battery_passport_annex_xiii_v1",
                    "version": "1.0.0",
                    "regulatorySource": ["REG_2023_1542_BATTERIES"],
                },
                "regulatedCore": {
                    "passportIdentity": {
                        "passportId": passport_id,
                        "passportVersion": "1.0.0",
                        "status": "draft",
                        "issuedAt": "2026-04-27T00:00:00Z",
                        "validFrom": "2026-04-27T00:00:00Z",
                        "validUntil": "2036-04-25T00:00:00Z",
                    },
                    "productIdentity": {
                        "productId": "did:web:passportai.example.com:products:12345678901234",
                        "productName": "AA alkaline battery pack",
                        "productDescription": "Photo-only battery product for DPP readiness demo",
                        "brandName": "Demo Brand",
                        "modelName": None,
                        "modelNumber": None,
                        "batchLot": None,
                        "serialNumber": None,
                        "productImageUrl": "demo_images/product_small.jpg",
                        "esprCategory": "batteries",
                        "cnCode": "8506",
                        "granularityLevel": "model",
                        "legalBasis": ["REG_2023_1542_BATTERIES"],
                    },
                    "identifiers": {
                        "persistentUniqueProductIdentifier": {
                            "value": "12345678901234",
                            "scheme": "GTIN",
                            "format": "GTIN-14",
                            "issuingBody": "GS1",
                            "checkDigitVerified": True,
                        },
                        "uniqueOperatorIdentifier": {
                            "value": "PENDING_OPERATOR_IDENTIFIER",
                            "scheme": "OTHER",
                            "issuingBody": None,
                        },
                        "uniqueFacilityIdentifier": {
                            "value": "PENDING_FACILITY_IDENTIFIER",
                            "scheme": None,
                            "issuingBody": None,
                        },
                    },
                    "dataCarrier": {
                        "type": "QR",
                        "standard": "GS1_Digital_Link",
                        "carrierValue": "http://localhost:8000/demo-passport",
                        "resolverUrl": "http://localhost:8000/demo-passport",
                        "physicalPlacement": "on_packaging",
                        "isPersistent": False,
                    },
                    "economicOperators": {
                        "responsibleEconomicOperator": {
                            "name": "Demo Brand",
                            "role": "manufacturer",
                            "identifierRef": "PENDING_OPERATOR_IDENTIFIER",
                            "country": "ZZ",
                            "contactEmail": None,
                            "contactPhone": None,
                            "website": None,
                        }
                    },
                    "compliance": {
                        "declarationOfConformity": {
                            "present": False,
                            "required": True,
                            "documentReference": None,
                            "documentUrl": None,
                        },
                        "technicalDocumentation": {
                            "present": False,
                            "documentReference": None,
                            "documentUrl": None,
                            "storageLocation": "internal",
                        },
                    },
                    "accessControl": {
                        "publicSections": ["productIdentity", "dataCarrier", "passportIdentity"],
                        "confidentialBusinessInformation": [],
                        "restrictedSections": {
                            "marketSurveillanceAuthorities": ["compliance", "auditTrail"]
                        },
                    },
                    "provenance": {
                        "issuer": {"did": "did:web:passportai.example.com", "name": "PassportAI"}
                    },
                },
                "sectoralBattery": {
                    "batteryClassification": {
                        "batteryCategory": "portable",
                        "chemistry": "alkaline",
                        "isRechargeable": False,
                        "passportRequired": True,
                    },
                    "batteryIdentity": {
                        "batteryModelIdentifier": "UNKNOWN_BATTERY_MODEL",
                        "manufacturerBatteryIdentifier": "UNKNOWN_MANUFACTURER_BATTERY_ID",
                        "serialNumber": None,
                    },
                    "sustainabilityAndComposition": {
                        "carbonFootprint": {
                            "declared": False,
                            "valueKgCo2e": None,
                            "methodology": None,
                        },
                        "criticalRawMaterials": [],
                        "hazardousSubstances": [],
                        "recycledContent": {
                            "declared": False,
                            "overallPercentage": None,
                            "byMaterial": [],
                        },
                    },
                    "conformityAndInformation": {
                        "ceMarkingPresent": False,
                        "declarationOfConformityReference": None,
                        "labelInformation": {
                            "visibleWarnings": [],
                            "visibleMarkings": ["AA", "1.5V"],
                        },
                    },
                },
                "systemMetadata": {
                    "platform": {
                        "generationMethod": "hybrid",
                        "generatorName": "PassportAI",
                        "generatorVersion": "1.0.0",
                        "humanReviewStatus": "not_reviewed",
                    },
                    "qualityAssessment": {
                        "readinessScore": 0,
                        "readinessScoreBreakdown": {
                            "total": 0,
                            "max": 100,
                            "essentialFields": 8,
                        },
                        "missingFields": [
                            {
                                "field": "dpp.sectoralBattery.batteryClassification.batteryCategory",
                                "severity": "required",
                                "action": "Confirm Battery category from supplier documentation.",
                                "regulatoryBasis": "REG_2023_1542_BATTERIES",
                            },
                            {
                                "field": "dpp.regulatedCore.compliance.technicalDocumentation",
                                "severity": "required",
                                "action": "Request Technical documentation.",
                                "regulatoryBasis": "REG_2023_1542_BATTERIES",
                            },
                        ],
                    },
                    "technicalAssets": {
                        "attachments": [
                            {
                                "name": "product_image",
                                "type": "image",
                                "url": "demo_images/product_small.jpg",
                                "hash": None,
                            }
                        ],
                        "contentHash": "sha256:abc123",
                    },
                },
            },
        },
    }


def test_generate_writes_human_readable_passport_html(tmp_path):
    renderer = PassportRenderer()
    fixed_now = datetime(2026, 4, 27, 13, 0, tzinfo=timezone.utc)

    output_path = renderer.generate(
        passport_json=_battery_passport(),
        output_dir=tmp_path,
        passport_id="demo-passport",
        generated_at=fixed_now,
    )

    assert output_path == tmp_path / "passport.html"
    html = output_path.read_text(encoding="utf-8")

    assert "Digital Product Passport" in html
    assert "AA alkaline battery pack" in html
    assert "Demo Brand" in html
    assert "Not publication-ready" in html
    assert "Battery passport data" in html
    assert "Battery category" in html
    assert "Battery chemistry" in html
    assert "View Gap Report" in html
    assert "Download JSON" in html
    assert "passport.json" in html
    assert "gap_report.html" in html
    assert "sha256:abc123" in html


def test_build_view_model_extracts_battery_sector_fields():
    model = PassportRenderer().build_view_model(
        passport_json=_battery_passport(),
        passport_id="demo-passport",
        generated_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    )

    assert model["product"]["name"] == "AA alkaline battery pack"
    assert model["product"]["group"] == "batteries"
    assert model["passport"]["status"] == "draft"
    assert model["passport"]["readiness_score"] == 0
    assert model["passport"]["readiness_label"] == "Not publication-ready"
    assert model["identifiers"]["product"]["value"] == "12345678901234"
    assert model["data_carrier"]["persistence_label"] == "Not yet persistent"

    sector_items = {item["label"]: item["value"] for item in model["sector"]["items"]}
    assert sector_items["Battery category"] == "portable"
    assert sector_items["Battery chemistry"] == "alkaline"
    assert sector_items["Carbon footprint"] == "Not declared"
    assert sector_items["Recycled content"] == "Not declared"

    missing_labels = [item["field_label"] for item in model["evidence"]["top_missing_fields"]]
    assert "Battery category" in missing_labels
    assert "Technical documentation" in missing_labels


def test_renderer_rejects_old_nested_dpp_shape(tmp_path):
    passport = _battery_passport()
    passport["credentialSubject"]["dpp"] = {"dpp": passport["credentialSubject"]["dpp"]}

    with pytest.raises(ValueError, match="not nested under credentialSubject.dpp.dpp"):
        PassportRenderer().generate(
            passport_json=passport,
            output_dir=tmp_path,
            passport_id="demo-passport",
        )


def test_renderer_rejects_missing_dpp_payload(tmp_path):
    passport = _battery_passport()
    passport["credentialSubject"].pop("dpp")

    with pytest.raises(ValueError, match="credentialSubject.dpp must be a dict"):
        PassportRenderer().generate(
            passport_json=passport,
            output_dir=tmp_path,
            passport_id="demo-passport",
        )

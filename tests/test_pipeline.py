import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import PassportPipeline
from src.storage.base import StorageProvider


class _DummyStorage(StorageProvider):
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir
        self.saved_files: dict[str, dict[str, Path]] = {}

    def save_package(self, passport_id: str, files: dict[str, Path]) -> str:
        self.saved_files[passport_id] = dict(files)
        return f"http://example.test/{passport_id}"

    def get_public_url(self, passport_id: str, filename: str) -> str:
        return f"http://example.test/{passport_id}/{filename}"

    def file_exists(self, passport_id: str, filename: str) -> bool:
        if self.output_dir is None:
            return False
        return (self.output_dir / passport_id / filename).exists()

    def delete_package(self, passport_id: str) -> None:
        return None

    def get_package_dir(self, passport_id: str) -> Path:
        if self.output_dir is None:
            raise RuntimeError("output_dir is required for artifact-writing tests")
        return self.output_dir / passport_id


class _StubVisionAgent:
    def run(self, **kwargs):
        return {
            "success": True,
            "agent": "VisionAgent",
            "is_mock": True,
            "data": {
                "domain_data": {
                    "espr_core": {
                        "product_group_hint": "textiles",
                        "product_name": "Photo-derived tote bag",
                        "visible_certifications": ["CE"],
                    },
                    "sectoral": {
                        "textiles": {
                            "material_visual_hint": "woven textile"
                        },
                        "batteries": None,
                        "electrical_appliances": None,
                    },
                },
                "assessment": {
                    "confidence_source": "model_estimate",
                    "missing_fields": [],
                    "warnings": [],
                    "assumptions": [],
                    "contradictions": [],
                    "needs_human_review": False,
                },
                "advisory": {
                    "agent_summary": "Vision extracted visible fields.",
                    "business_risks": [],
                    "recommended_next_actions": [],
                    "supplier_requests": [],
                    "where_to_get_data": [],
                    "next_batch_improvements": [],
                },
            },
        }


class _StubRegulatoryAgent:
    def __init__(self, *, success=True):
        self.success = success

    def run(self, **kwargs):
        if not self.success:
            return {
                "success": False,
                "agent": "RegulatoryConsultant",
                "is_mock": True,
                "error": "regulatory failed",
            }

        return {
            "success": True,
            "agent": "RegulatoryConsultant",
            "is_mock": True,
            "data": {
                "domain_data": {
                    "espr_core": {
                        "product_group": "textiles",
                        "espr_category": "textiles",
                        "sector_profile": {
                            "name": "textile_core_v1",
                            "version": "1.0",
                            "regulatory_source": ["REG_2024_1781_ESPR"],
                        },
                    },
                    "sectoral": {
                        "textiles": {
                            "fiber_composition": None,
                        },
                        "batteries": None,
                        "electrical_appliances": None,
                    },
                    "voluntary_esg": None,
                },
                "assessment": {
                    "confidence_source": "lookup_table",
                    "missing_fields": [],
                    "warnings": [],
                    "assumptions": [],
                    "contradictions": [],
                    "needs_human_review": False,
                },
                "advisory": {
                    "agent_summary": "Regulatory classification established.",
                    "business_risks": [],
                    "recommended_next_actions": [],
                    "supplier_requests": [],
                    "where_to_get_data": [],
                    "next_batch_improvements": [],
                },
            },
        }


class _StubLegalAgent:
    def run(self, **kwargs):
        return {
            "success": True,
            "agent": "LegalAgent",
            "is_mock": True,
            "data": {
                "domain_data": {
                    "espr_core": {
                        "compliance_hint": {
                            "doc_presence": "missing"
                        }
                    },
                    "sectoral": {
                        "textiles": {
                            "legal_doc_status": "missing"
                        },
                        "batteries": None,
                        "electrical_appliances": None,
                    },
                },
                "assessment": {
                    "confidence_source": "insufficient_data",
                    "missing_fields": [],
                    "warnings": [],
                    "assumptions": [],
                    "contradictions": [],
                    "needs_human_review": False,
                },
                "advisory": {
                    "agent_summary": "Legal review added documentary hints.",
                    "business_risks": [],
                    "recommended_next_actions": [],
                    "supplier_requests": [],
                    "where_to_get_data": [],
                    "next_batch_improvements": [],
                },
            },
        }


class _StubLCAAgent:
    def run(self, **kwargs):
        return {
            "success": True,
            "agent": "LCASpecialist",
            "is_mock": True,
            "data": {
                "domain_data": {
                    "espr_core": {},
                    "sectoral": {
                        "textiles": {},
                        "batteries": None,
                        "electrical_appliances": None,
                    },
                    "voluntary_esg": None,
                },
                "assessment": {
                    "confidence_source": "insufficient_data",
                    "missing_fields": [],
                    "warnings": [],
                    "assumptions": [],
                    "contradictions": [],
                    "needs_human_review": False,
                },
                "advisory": {
                    "agent_summary": "No declared ESG values provided.",
                    "business_risks": [],
                    "recommended_next_actions": [],
                    "supplier_requests": [],
                    "where_to_get_data": [],
                    "next_batch_improvements": [],
                },
            },
        }


class _StubGS1Agent:
    def run(self, **kwargs):
        return {
            "success": True,
            "agent": "GS1Specialist",
            "is_mock": True,
            "data": {
                "domain_data": {
                    "espr_core": {
                        "identifiers_hint": {
                            "gtin": "12345678901234"
                        },
                        "data_carrier_hint": {
                            "resolver_url_ready": False
                        },
                    },
                    "sectoral": {
                        "textiles": None,
                        "batteries": None,
                        "electrical_appliances": None,
                    },
                },
                "assessment": {
                    "confidence_source": "model_estimate",
                    "missing_fields": [],
                    "warnings": [],
                    "assumptions": [],
                    "contradictions": [],
                    "needs_human_review": False,
                },
                "advisory": {
                    "agent_summary": "GS1 readiness hints prepared.",
                    "business_risks": [],
                    "recommended_next_actions": [],
                    "supplier_requests": [],
                    "where_to_get_data": [],
                    "next_batch_improvements": [],
                },
            },
        }


class _StubAuditAgent:
    def __init__(self):
        self.last_kwargs = None

    def run(self, **kwargs):
        self.last_kwargs = kwargs
        domain_data = kwargs["reconciled_domain_data"]

        return {
            "success": True,
            "agent": "DataAuditAgent",
            "is_mock": True,
            "data": {
                "domain_data": domain_data,
                "assessment": {
                    "missing_fields": [],
                    "warnings": [],
                    "assumptions": [],
                    "contradictions": [],
                    "needs_human_review": False,
                    "readiness_verdict": "ready",
                    "readiness_score": 96,
                    "is_publishable": True,
                    "blocking_issues": [],
                },
                "advisory": {
                    "agent_summary": "Audit passed on reconciled domain data.",
                    "business_risks": [],
                    "recommended_next_actions": [],
                    "supplier_requests": [],
                    "where_to_get_data": [],
                    "next_batch_improvements": [],
                },
            },
        }


class _StubDPPGenerator:
    def __init__(self, *, validation_errors: list[str] | None = None):
        self.validation_errors = validation_errors or []
        self.last_kwargs = None

    def generate_from_reconciled_state(self, **kwargs):
        self.last_kwargs = kwargs
        passport_id = kwargs["passport_id"]
        product_group = kwargs["reconciled_domain_data"]["espr_core"]["product_group"]
        return {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "id": f"did:web:passportai.example.com:passports:{passport_id}",
            "type": ["VerifiableCredential", "DigitalProductPassportCredential"],
            "issuer": {"id": "did:web:passportai.example.com", "name": "PassportAI"},
            "validFrom": "2026-04-27T00:00:00Z",
            "credentialSubject": {
                "id": f"did:web:passportai.example.com:products:{passport_id}",
                "dpp": {
                    "dpp": {
                        "passportId": passport_id,
                        "productGroup": product_group,
                        "regulatedCore": {
                            "productIdentity": {"esprCategory": product_group}
                        },
                        "sectoralTextile": {},
                    }
                },
            },
        }

    def validate(self, passport):
        if self.validation_errors:
            return False, list(self.validation_errors)
        return True, []


def test_pipeline_runs_reconciled_audit_flow_without_dpp_generator(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"fake-image")

    audit_agent = _StubAuditAgent()

    pipeline = PassportPipeline(
        agents={
            "vision": _StubVisionAgent(),
            "regulatory": _StubRegulatoryAgent(),
            "legal": _StubLegalAgent(),
            "lca": _StubLCAAgent(),
            "gs1": _StubGS1Agent(),
            "audit": audit_agent,
        },
        storage=_DummyStorage(),
    )

    result = pipeline.run(
        image_path=image_path,
        description="photo-only textile product",
        user_inputs={"brand_name": "User Brand"},
    )

    assert result.success is True
    assert result.reconciled_domain_data is not None
    assert result.passport_json is None
    assert result.readiness_verdict == "ready"
    assert result.readiness_score == 96
    assert result.is_publishable is True

    espr_core = result.reconciled_domain_data["espr_core"]
    assert espr_core["product_group"] == "textiles"
    assert espr_core["espr_category"] == "textiles"
    assert espr_core["sector_profile"]["name"] == "textile_core_v1"

    # Vision overlay applied
    assert espr_core["product_name"] == "Photo-derived tote bag"

    # User input overlay applied without overriding classification truth
    assert espr_core["brand_name"] == "User Brand"

    # Legal overlay applied
    assert espr_core["compliance_hint"]["doc_presence"] == "missing"

    # GS1 moved before audit and is visible in reconciled state
    assert espr_core["identifiers_hint"]["gtin"] == "12345678901234"

    # Audit received gs1_result and reconciled_domain_data
    assert audit_agent.last_kwargs is not None
    assert audit_agent.last_kwargs["gs1_result"] is not None
    assert audit_agent.last_kwargs["reconciled_domain_data"]["espr_core"]["product_group"] == "textiles"

    assert any("DPPGenerator is not configured yet" in warning for warning in result.warnings)


def test_pipeline_blocks_on_failed_regulatory_payload(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"fake-image")

    pipeline = PassportPipeline(
        agents={
            "vision": _StubVisionAgent(),
            "regulatory": _StubRegulatoryAgent(success=False),
            "audit": _StubAuditAgent(),
        },
        storage=_DummyStorage(),
    )

    result = pipeline.run(image_path=image_path)

    assert result.success is False
    assert result.reconciled_domain_data is None
    assert any("RegulatoryConsultant did not return a usable success payload" in err for err in result.errors)

def test_pipeline_packages_dpp_from_reconciled_state(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"fake-image")

    storage = _DummyStorage(output_dir=tmp_path / "output")
    dpp_generator = _StubDPPGenerator()

    pipeline = PassportPipeline(
        agents={
            "vision": _StubVisionAgent(),
            "regulatory": _StubRegulatoryAgent(),
            "legal": _StubLegalAgent(),
            "lca": _StubLCAAgent(),
            "gs1": _StubGS1Agent(),
            "audit": _StubAuditAgent(),
            "dpp_generator": dpp_generator,
        },
        storage=storage,
    )

    result = pipeline.run(
        image_path=image_path,
        description="photo-only textile product",
        user_inputs={"brand_name": "User Brand"},
    )

    assert result.success is True
    assert result.passport_json is not None
    assert result.package_url == f"http://example.test/{result.passport_id}"

    artifact_path = result.artifact_paths["passport.json"]
    assert artifact_path == tmp_path / "output" / result.passport_id / "passport.json"
    assert artifact_path.exists()
    assert json.loads(artifact_path.read_text(encoding="utf-8")) == result.passport_json
    assert storage.saved_files[result.passport_id] == {"passport.json": artifact_path}

    assert dpp_generator.last_kwargs is not None
    assert dpp_generator.last_kwargs["reconciled_domain_data"] == result.reconciled_domain_data
    assert dpp_generator.last_kwargs["audit_payload"]["assessment"]["readiness_verdict"] == "ready"
    assert dpp_generator.last_kwargs["passport_id"] == result.passport_id
    assert dpp_generator.last_kwargs["public_package_url"].endswith("/passport.json")

    raw_agent_fields = {
        "vision_result",
        "regulatory_result",
        "legal_result",
        "lca_result",
        "gs1_result",
        "agent_outputs",
        "passport_json",
    }
    assert raw_agent_fields.isdisjoint(dpp_generator.last_kwargs)


def test_pipeline_fails_closed_when_dpp_validation_fails(tmp_path):
    image_path = tmp_path / "product.jpg"
    image_path.write_bytes(b"fake-image")

    storage = _DummyStorage(output_dir=tmp_path / "output")
    dpp_generator = _StubDPPGenerator(validation_errors=["missing credentialSubject"])

    pipeline = PassportPipeline(
        agents={
            "vision": _StubVisionAgent(),
            "regulatory": _StubRegulatoryAgent(),
            "legal": _StubLegalAgent(),
            "lca": _StubLCAAgent(),
            "gs1": _StubGS1Agent(),
            "audit": _StubAuditAgent(),
            "dpp_generator": dpp_generator,
        },
        storage=storage,
    )

    result = pipeline.run(image_path=image_path)

    assert result.success is False
    assert result.passport_json is None
    assert "passport.json" not in result.artifact_paths
    assert result.package_url is None
    assert storage.saved_files == {}
    assert not (tmp_path / "output" / result.passport_id / "passport.json").exists()
    assert any("DPPGenerator validation failed" in err for err in result.errors)


"""Human-readable compliance gap report generation.

GapReportGenerator is a projection-only renderer for DataAuditAgent output.
It does not read rendered DPP JSON, raw agent outputs, or legal/vision/LCA/GS1
results directly. DataAuditAgent remains the single source of audit semantics.

Output: ``gap_report.html`` in the requested output directory.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


_PRIORITY_ORDER = {"now": 0, "soon": 1, "later": 2}
_SEVERITY_ORDER = {"critical": 0, "required": 1, "recommended": 2, "optional": 3}
_PUBLICATION_BLOCKING_SEVERITIES = {"critical", "required"}

_FIELD_HELP: dict[str, tuple[str, str]] = {
    "dpp.regulatedCore.compliance.declarationOfConformity": (
        "Declaration of conformity",
        "The declaration or conformity evidence that supports regulated product claims.",
    ),
    "dpp.regulatedCore.compliance.technicalDocumentation": (
        "Technical documentation",
        "The technical file or document reference that supports the passport claims.",
    ),
    "dpp.regulatedCore.dataCarrier.carrierValue": (
        "QR / data carrier value",
        "The exact value encoded in the product QR code or other data carrier.",
    ),
    "dpp.regulatedCore.dataCarrier.resolverUrl": (
        "Public resolver URL",
        "The stable public URL where the passport package can be resolved.",
    ),
    "dpp.regulatedCore.dataCarrier.isPersistent": (
        "Persistent data carrier URL",
        "Whether the QR/resolver URL is stable enough for printed labels and long-lived access.",
    ),
    "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.value": (
        "Persistent product identifier",
        "The stable product identifier that links the passport to product master data.",
    ),
    "dpp.regulatedCore.identifiers.persistentUniqueProductIdentifier.scheme": (
        "Product identifier scheme",
        "The identifier standard used for the product, such as GTIN, DID, or an internal master-data scheme.",
    ),
    "dpp.regulatedCore.identifiers.uniqueOperatorIdentifier.value": (
        "Economic operator identifier",
        "The manufacturer, importer, or responsible operator identifier used for traceability.",
    ),
    "dpp.regulatedCore.identifiers.uniqueFacilityIdentifier.value": (
        "Manufacturing facility identifier",
        "The plant or facility identifier used when facility-level traceability is required.",
    ),
    "dpp.regulatedCore.productIdentity.cnCode": (
        "Customs CN code",
        "The Combined Nomenclature customs code used to classify the product for EU trade and compliance workflows.",
    ),
    "dpp.sectoralBattery.batteryClassification.batteryCategory": (
        "Battery category",
        "The regulatory battery category, such as portable, LMT, SLI, industrial, or EV battery.",
    ),
    "dpp.sectoralBattery.batteryClassification.chemistry": (
        "Battery chemistry",
        "The electrochemical chemistry, such as alkaline, lithium-ion, lead-acid, or another supplier-confirmed chemistry.",
    ),
    "dpp.sectoralBattery.conformityAndInformation.declarationOfConformityReference": (
        "Battery declaration of conformity",
        "Reference to the document that supports conformity and safety claims for the battery product.",
    ),
    "dpp.sectoralBattery.sustainabilityAndComposition.carbonFootprint": (
        "Battery carbon footprint",
        "Supplier or lifecycle evidence for the product-level carbon footprint.",
    ),
    "dpp.sectoralBattery.sustainabilityAndComposition.criticalRawMaterials": (
        "Critical raw materials",
        "Information about battery materials that may trigger sectoral disclosure requirements.",
    ),
    "dpp.sectoralBattery.sustainabilityAndComposition.recycledContent": (
        "Battery recycled content",
        "Evidence for recycled content percentages or supplier declarations.",
    ),
    "dpp.voluntaryEsg.packaging.material": (
        "Packaging material",
        "Packaging material, recyclability, and recycled-content information.",
    ),
}

_SOURCE_PROCESS_LABELS = {
    "VisionAgent": "Visual evidence extraction",
    "RegulatoryConsultant": "Regulatory field mapping",
    "LegalAgent": "Legal evidence check",
    "LCASpecialist": "Sustainability evidence check",
    "GS1Specialist": "Identifier and data-carrier check",
    "DataAuditAgent": "Evidence readiness audit",
}

_SOURCE_PROCESS_EXPLANATIONS = {
    "DataAuditAgent": (
        "Evidence readiness audit combines the pipeline outputs into a publication-readiness verdict. "
        "It checks missing fields, weak evidence, contradictions, and publication blockers. "
        "It does not invent product facts."
    ),
}

class GapReportGenerator:
    """Render an SME-readable remediation report from DataAuditAgent output.

    Invariants:
    - audit_result is the only semantic input.
    - passport_json is never used as source data.
    - raw agent outputs are never accepted by this renderer.
    - missing values remain explicit placeholders instead of invented facts.
    """

    def __init__(
        self,
        client: Any | None = None,
        template_path: Path | None = None,
    ) -> None:
        # Kept for constructor compatibility; intentionally unused by rendering.
        self.client = client
        self.template_path = template_path or Path("templates/gap_report.html.jinja2")

    def generate(
        self,
        *,
        audit_result: dict[str, Any],
        output_dir: Path | str | None = None,
        passport_id: str | None = None,
        generated_at: datetime | None = None,
    ) -> Path:
        """Generate ``gap_report.html`` from DataAuditAgent output.

        Args:
            audit_result: DataAuditAgent success envelope or raw audit payload.
            output_dir: Directory where ``gap_report.html`` is written.
            passport_id: Stable passport identifier for display metadata.
            generated_at: Optional deterministic timestamp for tests/demos.

        Returns:
            Path to the generated HTML report.

        Raises:
            ValueError: If audit_result is not a successful DataAuditAgent payload.
            FileNotFoundError: If the HTML template is missing.
            ImportError: If jinja2 is unavailable.
        """
        output_path = Path(output_dir or ".")
        output_path.mkdir(parents=True, exist_ok=True)

        view_model = self.build_view_model(
            audit_result=audit_result,
            passport_id=passport_id,
            generated_at=generated_at,
        )
        html = self._render_template(view_model)

        report_path = output_path / "gap_report.html"
        report_path.write_text(html, encoding="utf-8")
        return report_path

    def build_view_model(
        self,
        *,
        audit_result: dict[str, Any],
        passport_id: str | None = None,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Build the stable template model used by the HTML report."""
        payload = self._extract_audit_payload(audit_result)
        payload = deepcopy(payload)

        domain_data = self._require_mapping(payload.get("domain_data"), "domain_data")
        assessment = self._require_mapping(payload.get("assessment"), "assessment")
        advisory = self._require_mapping(payload.get("advisory"), "advisory")

        espr_core = self._safe_mapping(domain_data.get("espr_core"))
        gaps = self._normalize_gaps(assessment.get("missing_fields", []))
        gap_groups = self._group_gaps(gaps)

        action_plan = self._normalize_action_plan(
            advisory.get("recommended_next_actions", [])
        )
        top_actions = self._build_top_actions(gaps=gaps, fallback_actions=action_plan)
        blocking_items = self._build_publication_blocker_items(
            raw_blocking_issues=assessment.get("blocking_issues", []),
            gaps=gaps,
        )

        blocking_issues = self._clean_string_list(assessment.get("blocking_issues", []))
        contradictions = self._clean_string_list(assessment.get("contradictions", []))
        is_publishable = bool(assessment.get("is_publishable", False))
        needs_human_review = bool(assessment.get("needs_human_review", False))
        has_blockers = (
            bool(blocking_items)
            or bool(contradictions)
            or needs_human_review
            or not is_publishable
        )

        now = generated_at or datetime.now(timezone.utc)

        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        action_plan = self._normalize_action_plan(
            advisory.get("recommended_next_actions", [])
        )


        return {
            "schema_version": "gap_report.v1",
            "generated_at": self._format_timestamp(now),
            "product_context": self._build_product_context(
                espr_core=espr_core,
                passport_id=passport_id,
            ),
            "readiness": {
                "score": self._normalize_score(assessment.get("readiness_score")),
                "verdict": self._clean_string(assessment.get("readiness_verdict")) or "not_ready",
                "verdict_label": self._verdict_label(assessment.get("readiness_verdict")),
                "is_publishable": is_publishable,
                "needs_human_review": needs_human_review,
                "summary": self._build_readiness_summary(
                    score=self._normalize_score(assessment.get("readiness_score")),
                    verdict=self._clean_string(assessment.get("readiness_verdict")) or "not_ready",
                    total_gaps=len(gaps),
                    publication_blockers=len(blocking_items),
                ),
            },
            "publication_blockers": {
                "has_blockers": has_blockers,
                "blocking_issues": blocking_issues,
                "blocking_items": blocking_items,
                "contradictions": contradictions,
            },
            "gap_counts": {
                "total": len(gaps),
                "blocking": len(gap_groups["blocking"]),
                "missing": len(gap_groups["missing"]),
                "weak_evidence": len(gap_groups["weak_evidence"]),
                "unverified": len(gap_groups["unverified"]),
                "recommended": len(gap_groups["recommended"]),
            },
            "gap_groups": gap_groups,
            "action_plan": action_plan,
            "top_actions": top_actions,
            "supplier_requests": self._normalize_supplier_requests(
                advisory.get("supplier_requests", [])
            ),
            "data_sources": self._normalize_data_sources(
                advisory.get("where_to_get_data", [])
            ),
            "business_risks": self._clean_string_list(advisory.get("business_risks", [])),
            "warnings": [
                self._humanize_process_message(item)
                for item in self._clean_string_list(assessment.get("warnings", []))
            ],
            "assumptions": [
                self._humanize_process_message(item)
                for item in self._clean_string_list(assessment.get("assumptions", []))
            ],
            "audit_metadata": {
                "source": "DataAuditAgent",
                "source_label": _SOURCE_PROCESS_LABELS["DataAuditAgent"],
                "source_explanation": _SOURCE_PROCESS_EXPLANATIONS["DataAuditAgent"],
                "raw_agent_outputs_included": False,
                "dpp_json_used_as_source": False,
            },
        }

    def analyze_gaps(self, passport_json: dict, required_fields: list[str]) -> dict:
        """Deprecated: gap analysis belongs to DataAuditAgent, not this renderer."""
        raise RuntimeError(
            "GapReportGenerator.analyze_gaps() is deprecated. "
            "Gap analysis belongs to DataAuditAgent; this class only renders audit output."
        )

    def _render_template(self, context: dict[str, Any]) -> str:
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
        except ImportError:
            return self._render_fallback_html(context)

        if not self.template_path.exists():
            return self._render_fallback_html(context)

        env = Environment(
            loader=FileSystemLoader(str(self.template_path.parent)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template(self.template_path.name)
        return template.render(**context)

    def _render_fallback_html(self, context: dict[str, Any]) -> str:
        """Dependency-free HTML renderer used when Jinja2 is unavailable."""
        product = context["product_context"]
        readiness = context["readiness"]
        blockers = context["publication_blockers"]
        gap_groups = context["gap_groups"]
        counts = context["gap_counts"]

        def text(value: Any) -> str:
            return escape(str(value), quote=True)

        def paragraph_list(items: list[str], empty: str) -> str:
            if not items:
                return f"<p class='empty'>{text(empty)}</p>"
            return "<ul>" + "".join(f"<li>{text(item)}</li>" for item in items) + "</ul>"

        def gap_rows(gaps: list[dict[str, Any]]) -> str:
            if not gaps:
                return "<tr><td colspan='6' class='empty'>No issues in this group.</td></tr>"
            rows = []
            for gap in gaps:
                evidence = ", ".join(gap.get("acceptable_evidence") or []) or "not specified"
                rows.append(
                    "<tr>"
                    f"<td><code>{text(gap['field'])}</code><br>{text(gap['severity_label'])}</td>"
                    f"<td><strong>{text(gap['current_evidence_status'].replace('_', ' '))}</strong><br>{text(gap['reason'])}</td>"
                    f"<td>{text(gap['why_it_matters'])}</td>"
                    f"<td>{text(gap['where_to_get_data'])}</td>"
                    f"<td>{text(gap['closure_condition'])}<br><span class='muted'>Acceptable evidence: {text(evidence)}</span></td>"
                    f"<td>{text(gap['owner_hint'])}</td>"
                    "</tr>"
                )
            return "".join(rows)

        def gap_table(title: str, gaps: list[dict[str, Any]]) -> str:
            return (
                f"<h2>{text(title)}</h2>"
                "<table><thead><tr>"
                "<th>Field</th><th>Current state</th><th>Why it matters</th>"
                "<th>Where to get data</th><th>Closure condition</th><th>Owner</th>"
                "</tr></thead><tbody>"
                + gap_rows(gaps)
                + "</tbody></table>"
            )

        action_rows = "".join(
            "<tr>"
            f"<td>{text(action['priority_label'])}</td>"
            f"<td>{text(action['owner'])}</td>"
            f"<td>{text(action['action'])}</td>"
            "</tr>"
            for action in context["action_plan"]
        ) or "<tr><td colspan='3' class='empty'>No action plan was provided by the audit.</td></tr>"

        supplier_html = paragraph_list(
            [
                f"{item['request']} — {item['why_needed']} ({item['document_type']})"
                for item in context["supplier_requests"]
            ],
            "No supplier-specific requests.",
        )
        source_html = paragraph_list(
            [
                f"{item['missing_topic']}: {item['source']} — {item['how_to_obtain']}"
                for item in context["data_sources"]
            ],
            "No data-source guidance was provided by the audit.",
        )

        blocker_html = paragraph_list(blockers["blocking_issues"], "No blocking issues listed.")
        contradiction_html = paragraph_list(blockers["contradictions"], "No contradictions listed.")
        risk_html = paragraph_list(context["business_risks"], "No business risks listed.")
        warning_html = paragraph_list(context["warnings"], "No warnings.")
        assumption_html = paragraph_list(context["assumptions"], "No assumptions.")

        status = "Publishable" if readiness["is_publishable"] else "Publication is blocked"

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PassportAI Gap Report — {text(product['product_name'])}</title>
  <style>
    body {{ margin: 0; padding: 32px; color: #111827; font-family: Arial, sans-serif; line-height: 1.48; }}
    .page {{ max-width: 1080px; margin: 0 auto; }}
    .hero, .card, .banner {{ border: 1px solid #e5e7eb; border-radius: 14px; padding: 16px; margin-bottom: 14px; }}
    .banner.blocked {{ background: #fef2f2; color: #991b1b; border-color: #fecaca; }}
    .muted, .empty {{ color: #6b7280; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 18px; }}
    th, td {{ border-top: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; font-size: 12px; text-transform: uppercase; }}
    code {{ font-family: Consolas, monospace; }}
    .score {{ font-size: 42px; font-weight: 800; }}
  </style>
</head>
<body><div class="page">
  <section class="hero">
    <h1>PassportAI Gap Report</h1>
    <p class="muted">Human-readable remediation plan generated from <strong>{text(context['audit_metadata']['source'])}</strong>. This report requires human review before official publication.</p>
    <p class="muted">Schema {text(context['schema_version'])} · Generated {text(context['generated_at'])} · Passport ID {text(product['passport_id'])}</p>
  </section>

  <section class="card">
    <h2>Product context</h2>
    <table><tbody>
      <tr><th>Product</th><td>{text(product['product_name'])}</td></tr>
      <tr><th>Brand / model</th><td>{text(product['brand_name'])} / {text(product['model_name'])}</td></tr>
      <tr><th>Product group</th><td>{text(product['product_group'])}</td></tr>
      <tr><th>ESPR category</th><td>{text(product['espr_category'])}</td></tr>
      <tr><th>Sector profile</th><td>{text(product['sector_profile'])}</td></tr>
    </tbody></table>
  </section>

  <section class="card">
    <h2>Readiness</h2>
    <div class="score">{text(readiness['score'])}/100</div>
    <p><strong>Status:</strong> {text(status)}</p>
    <p><strong>Verdict:</strong> {text(readiness['verdict_label'])}</p>
    <p><strong>Human review:</strong> {text('required' if readiness['needs_human_review'] else 'not flagged')}</p>
    <p>{text(readiness['summary'])}</p>
  </section>

  <div class="banner blocked"><strong>{text(status)}</strong><br>Fail-closed audit: weak, missing, or contradictory evidence is not converted into publishable product truth.</div>

  <section class="card">
    <h2>Gap counts</h2>
    <p>Blocking: {text(counts['blocking'])} · Missing: {text(counts['missing'])} · Weak evidence: {text(counts['weak_evidence'])} · Unverified: {text(counts['unverified'])} · Recommended: {text(counts['recommended'])}</p>
  </section>

  <h2>Publication blockers</h2>
  <h3>Blocking issues</h3>{blocker_html}
  <h3>Contradictions</h3>{contradiction_html}

  {gap_table('1. Blocking gaps', gap_groups['blocking'])}
  {gap_table('2. Missing required data', gap_groups['missing'])}
  {gap_table('3. Weak evidence', gap_groups['weak_evidence'])}
  {gap_table('4. Present but unverified', gap_groups['unverified'])}
  {gap_table('5. Recommended improvements', gap_groups['recommended'])}

  <h2>Action plan</h2>
  <table><thead><tr><th>Priority</th><th>Owner</th><th>Action</th></tr></thead><tbody>{action_rows}</tbody></table>

  <section class="card"><h2>Supplier request pack</h2>{supplier_html}</section>
  <section class="card"><h2>Where to get missing data</h2>{source_html}</section>
  <section class="card"><h2>Business risks</h2>{risk_html}</section>
  <section class="card"><h2>Audit notes</h2><h3>Warnings</h3>{warning_html}<h3>Assumptions</h3>{assumption_html}</section>

  <footer class="muted">
    Boundary statement: raw agent outputs included = {text(context['audit_metadata']['raw_agent_outputs_included'])};
    DPP JSON used as source = {text(context['audit_metadata']['dpp_json_used_as_source'])}.
    Product facts and audit semantics come from DataAuditAgent output only.
  </footer>
</div></body></html>"""

    def _extract_audit_payload(self, audit_result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(audit_result, dict):
            raise ValueError("audit_result must be a dict.")

        if {"domain_data", "assessment", "advisory"}.issubset(audit_result.keys()):
            return audit_result

        if audit_result.get("success") is not True:
            raise ValueError("Gap report requires a successful DataAuditAgent result.")

        payload = audit_result.get("data")
        if not isinstance(payload, dict):
            raise ValueError("DataAuditAgent result has no usable data payload.")

        required_keys = {"domain_data", "assessment", "advisory"}
        if not required_keys.issubset(payload.keys()):
            missing = ", ".join(sorted(required_keys - set(payload.keys())))
            raise ValueError(f"DataAuditAgent payload is missing required keys: {missing}")

        return payload

    def _build_product_context(
        self,
        *,
        espr_core: dict[str, Any],
        passport_id: str | None,
    ) -> dict[str, str]:
        sector_profile = espr_core.get("sector_profile")
        if isinstance(sector_profile, dict):
            sector_profile_value = self._clean_string(sector_profile.get("name"))
        else:
            sector_profile_value = self._clean_string(sector_profile)

        return {
            "passport_id": passport_id or "not assigned",
            "product_name": self._clean_string(espr_core.get("product_name")) or "Unnamed product",
            "brand_name": self._clean_string(espr_core.get("brand_name")) or "not provided",
            "model_name": self._clean_string(espr_core.get("model_name")) or "not provided",
            "product_group": self._clean_string(espr_core.get("product_group")) or "unknown",
            "espr_category": self._clean_string(espr_core.get("espr_category")) or "unknown",
            "sector_profile": sector_profile_value or "not assigned",
        }

    def _normalize_gaps(self, raw_gaps: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_gaps, list):
            return []

        normalized = []
        for index, raw in enumerate(raw_gaps, start=1):
            if not isinstance(raw, dict):
                continue

            field = self._clean_string(raw.get("field")) or f"unknown.field.{index}"
            severity = self._clean_string(raw.get("severity")) or "required"

            raw_blocking = bool(raw.get("blocking", False))
            display_blocking = self._is_publication_blocking(
                raw_blocking=raw_blocking,
                severity=severity,
            )

            reason_code = self._clean_string(raw.get("reason_code")) or "missing"
            source_agents = raw.get("source_agents")
            acceptable_evidence = raw.get("acceptable_evidence")

            normalized.append(
                {
                    "gap_id": self._clean_string(raw.get("gap_id")) or f"{field}:{reason_code}",
                    "field": field,
                    "field_label": self._field_label(field),
                    "field_description": self._field_description(field),
                    "severity": severity,
                    "severity_label": severity.replace("_", " ").title(),
                    "raw_blocking": raw_blocking,
                    "blocking": display_blocking,
                    "display_blocking": display_blocking,
                    "blocking_downgraded": raw_blocking and not display_blocking,
                    "reason_code": reason_code,
                    "reason": self._humanize_field_references(
                        self._clean_string(raw.get("reason"))
                        or "Missing or weak evidence for this field."
                    ),
                    "why_it_matters": self._humanize_field_references(
                        self._clean_string(raw.get("why_it_matters"))
                        or "This field affects passport completeness or defensibility."
                    ),
                    "current_evidence_status": self._clean_string(
                        raw.get("current_evidence_status")
                    )
                    or "absent",
                    "current_evidence_status_label": self._evidence_status_label(
                        self._clean_string(raw.get("current_evidence_status")) or "absent"
                    ),
                    "acceptable_evidence": self._clean_string_list(acceptable_evidence),
                    "where_to_get_data": self._humanize_field_references(
                        self._clean_string(raw.get("where_to_get_data"))
                        or "authoritative product records or supplier evidence"
                    ),
                    "closure_condition": self._humanize_field_references(
                        self._clean_string(raw.get("closure_condition"))
                        or "Provide a documented value from an authoritative source."
                    ),
                    "action": self._humanize_field_references(
                        self._clean_string(raw.get("action"))
                        or f"Provide authoritative evidence for {self._field_label(field)}."
                    ),
                    "owner_hint": self._clean_string(raw.get("owner_hint")) or "unknown",
                    "owner_label": self._owner_label(
                        self._clean_string(raw.get("owner_hint")) or "unknown"
                    ),
                    "source_agents": self._clean_string_list(source_agents),
                    "source_processes": self._source_processes(source_agents),
                    "requires_supplier_confirmation": bool(
                        raw.get("requires_supplier_confirmation", False)
                    ),
                    "regulatory_basis": self._clean_string(raw.get("regulatory_basis")),
                    "deadline": self._clean_string(raw.get("deadline")),
                }
            )

        return sorted(
            normalized,
            key=lambda gap: (
                0 if gap["blocking"] else 1,
                _SEVERITY_ORDER.get(gap["severity"], 99),
                gap["field"],
            ),
        )

    def _group_gaps(self, gaps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {
            "blocking": [],
            "missing": [],
            "weak_evidence": [],
            "unverified": [],
            "recommended": [],
        }

        for gap in gaps:
            reason_code = gap.get("reason_code")
            evidence_status = gap.get("current_evidence_status")

            if gap.get("display_blocking"):
                groups["blocking"].append(gap)
            elif reason_code in {"missing", "document_absent"} or evidence_status == "absent":
                groups["missing"].append(gap)
            elif evidence_status in {"photo_only", "claim_only"}:
                groups["weak_evidence"].append(gap)
            elif reason_code == "unverified" or evidence_status == "document_present_unverified":
                groups["unverified"].append(gap)
            else:
                groups["recommended"].append(gap)

        return groups

    def _normalize_action_plan(self, raw_actions: Any) -> list[dict[str, str]]:
        if not isinstance(raw_actions, list):
            return []

        actions: list[dict[str, str]] = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                continue
            action = self._clean_string(raw.get("action"))
            if not action:
                continue

            priority = self._clean_string(raw.get("priority")) or "later"
            owner = self._clean_string(raw.get("owner")) or "unknown"

            actions.append(
                {
                    "priority": priority,
                    "priority_label": priority.replace("_", " ").title(),
                    "action": self._humanize_field_references(action),
                    "owner": owner,
                    "owner_label": self._owner_label(owner),
                    "field_label": "",
                    "field": "",
                    "severity": "",
                }
            )

        return sorted(
            actions,
            key=lambda action: (
                _PRIORITY_ORDER.get(action["priority"], 99),
                action["owner_label"],
                action["action"],
            ),
        )

    def _normalize_supplier_requests(self, raw_requests: Any) -> list[dict[str, str]]:
        if not isinstance(raw_requests, list):
            return []

        requests = []
        for raw in raw_requests:
            if not isinstance(raw, dict):
                continue

            request = self._clean_string(raw.get("request"))
            if not request:
                continue

            field_path = self._extract_field_path(request)
            request_label = (
                f"Provide authoritative evidence for {self._field_label(field_path)}."
                if field_path
                else self._humanize_field_references(request)
            )

            requests.append(
                {
                    "request": self._humanize_field_references(request),
                    "request_label": request_label,
                    "technical_field_path": field_path,
                    "why_needed": self._humanize_field_references(
                        self._clean_string(raw.get("why_needed"))
                        or "Needed to close a passport evidence gap."
                    ),
                    "document_type": self._clean_string(raw.get("document_type"))
                    or "supporting document or supplier statement",
                }
            )
        return requests

    def _normalize_data_sources(self, raw_sources: Any) -> list[dict[str, str]]:
        if not isinstance(raw_sources, list):
            return []

        sources = []
        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            topic = self._clean_string(raw.get("missing_topic"))
            source = self._clean_string(raw.get("source"))
            if not topic or not source:
                continue
            sources.append(
                {
                    "missing_topic": topic,
                    "missing_topic_label": self._field_label(topic),
                    "source": source,
                    "how_to_obtain": self._humanize_field_references(
                        self._clean_string(raw.get("how_to_obtain"))
                        or "Collect this from the authoritative owner and rerun audit."
                    ),
                }
            )
        return sources

    def _field_label(self, field: str) -> str:
        help_entry = _FIELD_HELP.get(field)
        if help_entry is not None:
            return help_entry[0]

        leaf = field.split(".")[-1] if field else "field"
        return self._split_identifier(leaf).title()


    def _field_description(self, field: str) -> str:
        help_entry = _FIELD_HELP.get(field)
        if help_entry is not None:
            return help_entry[1]

        if field.startswith("dpp."):
            return "A Digital Product Passport field that needs stronger evidence before publication."

        return "A passport readiness field that needs stronger evidence before publication."


    def _source_processes(self, source_agents: Any) -> list[dict[str, str]]:
        processes = []
        for agent in self._clean_string_list(source_agents):
            processes.append(
                {
                    "name": agent,
                    "label": _SOURCE_PROCESS_LABELS.get(
                        agent,
                        self._split_identifier(agent).title(),
                    ),
                }
            )
        return processes


    def _owner_label(self, owner: str) -> str:
        labels = {
            "brand_owner": "Brand owner",
            "manufacturer": "Manufacturer",
            "supplier": "Supplier",
            "internal_compliance": "Internal compliance",
            "economic_operator": "Responsible economic operator",
            "unknown": "Owner to assign",
        }
        return labels.get(owner, self._split_identifier(owner).title())


    def _evidence_status_label(self, status: str) -> str:
        labels = {
            "absent": "No evidence yet",
            "photo_only": "Photo evidence only",
            "claim_only": "Claim without proof",
            "document_present_unverified": "Document present but unverified",
            "verified_documented": "Verified documented evidence",
        }
        return labels.get(status, self._split_identifier(status).title())


    def _split_identifier(self, value: str) -> str:
        if not value:
            return "field"

        text = value.replace("_", " ").replace("-", " ")
        chars = []
        previous = ""

        for char in text:
            if previous and char.isupper() and (previous.islower() or previous.isdigit()):
                chars.append(" ")
            chars.append(char)
            previous = char

        return " ".join("".join(chars).split())

    def _is_publication_blocking(self, *, raw_blocking: bool, severity: str) -> bool:
        return raw_blocking and severity in _PUBLICATION_BLOCKING_SEVERITIES


    def _build_publication_blocker_items(
        self,
        *,
        raw_blocking_issues: Any,
        gaps: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        seen = set()

        for gap in gaps:
            if not gap.get("display_blocking"):
                continue

            key = gap["field"]
            seen.add(key)
            items.append(
                {
                    "label": f"{gap['field_label']} is missing or not defensible",
                    "field": gap["field"],
                    "reason": gap["reason"],
                    "owner_label": gap["owner_label"],
                    "severity_label": gap["severity_label"],
                }
            )

        for raw in self._clean_string_list(raw_blocking_issues):
            field = self._extract_field_path(raw)
            if field and field in seen:
                continue

            items.append(
                {
                    "label": self._humanize_field_references(raw),
                    "field": field or "",
                    "reason": "Audit marked this issue as blocking publication readiness.",
                    "owner_label": "Owner to assign",
                    "severity_label": "Blocking",
                }
            )

        return items


    def _build_top_actions(
        self,
        *,
        gaps: list[dict[str, Any]],
        fallback_actions: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []

        sorted_gaps = sorted(
            gaps,
            key=lambda gap: (
                0 if gap.get("display_blocking") else 1,
                _SEVERITY_ORDER.get(gap.get("severity", ""), 99),
                0 if gap.get("requires_supplier_confirmation") else 1,
                gap.get("field_label", ""),
            ),
        )

        for gap in sorted_gaps:
            if len(actions) >= 5:
                break

            if not gap.get("display_blocking") and gap.get("severity") not in {
                "critical",
                "required",
            }:
                continue

            actions.append(
                {
                    "priority": "now" if gap.get("display_blocking") else "soon",
                    "priority_label": "Now" if gap.get("display_blocking") else "Soon",
                    "owner": gap.get("owner_hint", "unknown"),
                    "owner_label": gap.get("owner_label", "Owner to assign"),
                    "action": gap.get("action", f"Provide evidence for {gap['field_label']}."),
                    "field": gap.get("field", ""),
                    "field_label": gap.get("field_label", ""),
                    "severity": gap.get("severity", ""),
                }
            )

        if actions:
            return actions

        return fallback_actions[:5]


    def _build_readiness_summary(
        self,
        *,
        score: int,
        verdict: str,
        total_gaps: int,
        publication_blockers: int,
    ) -> str:
        if publication_blockers:
            return (
                f"Passport readiness is {verdict.replace('_', ' ')} ({score}/100). "
                f"The audit found {publication_blockers} publication-blocking issue(s) "
                f"and {total_gaps} total evidence gap(s)."
            )

        if total_gaps:
            return (
                f"Passport readiness is {verdict.replace('_', ' ')} ({score}/100). "
                f"The audit found {total_gaps} evidence gap(s), but none are classified "
                "as direct publication blockers."
            )

        return f"Passport readiness is {verdict.replace('_', ' ')} ({score}/100)."


    def _field_label(self, field: str) -> str:
        help_entry = _FIELD_HELP.get(field)
        if help_entry is not None:
            return help_entry[0]

        leaf = field.split(".")[-1] if field else "field"
        return self._split_identifier(leaf).title()


    def _field_description(self, field: str) -> str:
        help_entry = _FIELD_HELP.get(field)
        if help_entry is not None:
            return help_entry[1]

        if field.startswith("dpp."):
            return "A Digital Product Passport field that needs stronger evidence before publication."

        return "A passport readiness field that needs stronger evidence before publication."


    def _source_processes(self, source_agents: Any) -> list[dict[str, str]]:
        processes = []
        for agent in self._clean_string_list(source_agents):
            processes.append(
                {
                    "name": agent,
                    "label": _SOURCE_PROCESS_LABELS.get(
                        agent,
                        self._split_identifier(agent).title(),
                    ),
                }
            )
        return processes


    def _owner_label(self, owner: str) -> str:
        labels = {
            "brand_owner": "Brand owner",
            "manufacturer": "Manufacturer",
            "supplier": "Supplier",
            "internal_compliance": "Internal compliance",
            "economic_operator": "Responsible economic operator",
            "unknown": "Owner to assign",
        }
        return labels.get(owner, self._split_identifier(owner).title())


    def _evidence_status_label(self, status: str) -> str:
        labels = {
            "absent": "No evidence yet",
            "photo_only": "Photo evidence only",
            "claim_only": "Claim without proof",
            "document_present_unverified": "Document present but unverified",
            "verified_documented": "Verified documented evidence",
        }
        return labels.get(status, self._split_identifier(status).title())


    def _humanize_process_message(self, message: str) -> str:
        cleaned = message
        for internal_name, label in _SOURCE_PROCESS_LABELS.items():
            cleaned = cleaned.replace(f"{internal_name}:", f"{label}:")
            cleaned = cleaned.replace(internal_name, label)
        return self._humanize_field_references(cleaned)


    def _extract_field_path(self, text: str) -> str:
        if not text:
            return ""

        for field in sorted(_FIELD_HELP, key=len, reverse=True):
            if field in text:
                return field

        import re

        match = re.search(r"dpp(?:\.[A-Za-z0-9_]+)+", text)
        return match.group(0) if match else ""


    def _humanize_field_references(self, text: str) -> str:
        if not text:
            return ""

        result = text

        for field in sorted(_FIELD_HELP, key=len, reverse=True):
            result = result.replace(field, self._field_label(field))

        import re

        def replace_unknown(match: Any) -> str:
            field = match.group(0)
            return self._field_label(field)

        return re.sub(r"dpp(?:\.[A-Za-z0-9_]+)+", replace_unknown, result)


    def _split_identifier(self, value: str) -> str:
        if not value:
            return "field"

        text = value.replace("_", " ").replace("-", " ")
        chars = []
        previous = ""

        for char in text:
            if previous and char.isupper() and (previous.islower() or previous.isdigit()):
                chars.append(" ")
            chars.append(char)
            previous = char

        return " ".join("".join(chars).split())

    def _normalize_score(self, value: Any) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, score))

    def _verdict_label(self, value: Any) -> str:
        verdict = self._clean_string(value) or "not_ready"
        return verdict.replace("_", " ").title()

    def _format_timestamp(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _require_mapping(self, value: Any, name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"DataAuditAgent payload field {name!r} must be a dict.")
        return value

    def _safe_mapping(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _clean_string(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""

    def _clean_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned


if __name__ == "__main__":
    print("GapReportGenerator loaded OK")

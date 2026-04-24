from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from .contracts import AgentPayload


_SEVERITY_RANK = {
    "critical": 4,
    "required": 3,
    "recommended": 2,
    "optional": 1,
}

_BLOCKING_REASON_CODES = {
    "inconsistent",
    "document_absent",
    "unverified",
}

_FIELD_PRIORITY_HINTS = (
    "identifiers.",
    "declaration",
    "technical_documentation",
    "legal_basis",
    "sector_profile",
    "espr_category",
)

_EVIDENCE_STATUS_RANK = {
    "absent": 1,
    "claim_only": 2,
    "photo_only": 3,
    "document_present_unverified": 4,
    "verified_documented": 5,
}
class DataAuditAgent(BaseAgent):
    """
    Cross-agent evidence auditor and passport readiness synthesizer.

    Owns:
    - aggregated completeness review
    - contradiction aggregation
    - normalized gap synthesis
    - readiness verdict / score / blocking issues
    - remediation-oriented advisory for gap report generation

    Does NOT own:
    - product facts
    - classification truth
    - legal truth
    - GS1 truth
    - LCA values
    - final DPP rendering
    """

    IS_MOCK = True

    def run(
        self,
        *,
        reconciled_domain_data: dict[str, Any] | None = None,
        domain_data: dict[str, Any] | None = None,
        vision_result: dict[str, Any] | None = None,
        regulatory_result: dict[str, Any] | None = None,
        legal_result: dict[str, Any] | None = None,
        lca_result: dict[str, Any] | None = None,
        gs1_result: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        try:
            final_domain_data = reconciled_domain_data or domain_data
            if not isinstance(final_domain_data, dict):
                raise ValueError(
                    "DataAuditAgent requires reconciled_domain_data (or domain_data) as a dict."
                )

            source_results = {
                "VisionAgent": vision_result,
                "RegulatoryConsultant": regulatory_result,
                "LegalAgent": legal_result,
                "LCASpecialist": lca_result,
                "GS1Specialist": gs1_result,
            }

            payloads: dict[str, AgentPayload] = {}
            audit_warnings: list[str] = []

            for agent_name, raw_result in source_results.items():
                payload = self._extract_payload(agent_name, raw_result, audit_warnings)
                if payload is not None:
                    payloads[agent_name] = payload

            normalized_gaps = self._normalize_missing_fields(payloads)
            contradictions = self._dedupe_strings(
                self._collect_agent_contradictions(payloads)
                + self._build_structural_contradictions(final_domain_data)
            )

            audit_warnings.extend(self._collect_agent_warnings(payloads))
            audit_warnings.extend(
                self._build_cross_agent_warnings(final_domain_data, payloads)
            )
            audit_warnings = self._dedupe_strings(audit_warnings)

            blocking_issues = self._build_blocking_issues(
                normalized_gaps,
                contradictions,
            )
            needs_human_review = self._compute_needs_human_review(
                payloads,
                normalized_gaps,
                contradictions,
            )

            readiness_verdict = self._determine_readiness_verdict(
                normalized_gaps=normalized_gaps,
                contradictions=contradictions,
                needs_human_review=needs_human_review,
            )
            readiness_score = self._compute_readiness_score(
                normalized_gaps=normalized_gaps,
                contradictions=contradictions,
                needs_human_review=needs_human_review,
                readiness_verdict=readiness_verdict,
            )
            is_publishable = self._determine_publishability(
                readiness_verdict=readiness_verdict,
                normalized_gaps=normalized_gaps,
                contradictions=contradictions,
                needs_human_review=needs_human_review,
            )
            payload: AgentPayload = {
                "domain_data": final_domain_data,
                "assessment": {
                    "missing_fields": normalized_gaps,
                    "warnings": audit_warnings,
                    "assumptions": [
                        "DataAuditAgent synthesizes structured agent outputs and does not create new product facts.",
                    ],
                    "contradictions": contradictions,
                    "needs_human_review": needs_human_review,
                    "readiness_verdict": readiness_verdict,
                    "readiness_score": readiness_score,
                    "is_publishable": is_publishable,
                    "blocking_issues": blocking_issues,
                },
                "advisory": {
                    "agent_summary": self._build_agent_summary(
                        readiness_verdict=readiness_verdict,
                        readiness_score=readiness_score,
                        blocking_issues=blocking_issues,
                        gap_count=len(normalized_gaps),
                    ),
                    "business_risks": self._build_business_risks(
                        normalized_gaps=normalized_gaps,
                        contradictions=contradictions,
                        needs_human_review=needs_human_review,
                    ),
                    "recommended_next_actions": self._build_recommended_actions(
                        normalized_gaps=normalized_gaps,
                        contradictions=contradictions,
                    ),
                    "supplier_requests": self._build_supplier_requests(
                        normalized_gaps
                    ),
                    "where_to_get_data": self._build_where_to_get_data(
                        normalized_gaps
                    ),
                    "next_batch_improvements": self._build_next_batch_improvements(
                        normalized_gaps=normalized_gaps,
                        payloads=payloads,
                    ),
                },
            }

            return self._format_success(payload)
        except Exception as exc:
            return self._format_error(exc)
    # ------------------------------------------------------------------
    # Publishability determination
    # ------------------------------------------------------------------

    def _determine_publishability(
    self,
    *,
    readiness_verdict: str,
    normalized_gaps: list[dict[str, Any]],
    contradictions: list[str],
    needs_human_review: bool,
    ) -> bool:
        if contradictions:
            return False

        if needs_human_review:
            return False

        if any(gap.get("blocking") for gap in normalized_gaps):
            return False

        if readiness_verdict == "ready":
            return True

        if readiness_verdict == "ready_with_gaps":
            return all(
                gap.get("severity") in {"recommended", "optional"}
                for gap in normalized_gaps
            )

        return False
    # ------------------------------------------------------------------
    # Input extraction
    # ------------------------------------------------------------------

    def _extract_payload(
        self,
        agent_name: str,
        raw_result: dict[str, Any] | None,
        audit_warnings: list[str],
    ) -> AgentPayload | None:
        if raw_result is None:
            return None

        if not isinstance(raw_result, dict):
            audit_warnings.append(
                f"{agent_name} output was ignored because it is not a dict."
            )
            return None

        if {"domain_data", "assessment", "advisory"}.issubset(raw_result.keys()):
            return raw_result

        success = raw_result.get("success")
        if success is False:
            audit_warnings.append(
                f"{agent_name} failed upstream and was excluded from audit synthesis."
            )
            return None

        data = raw_result.get("data")
        if success is True and isinstance(data, dict):
            return data

        audit_warnings.append(
            f"{agent_name} output was ignored because the success envelope is malformed."
        )
        return None

    # ------------------------------------------------------------------
    # Gap normalization
    # ------------------------------------------------------------------

    def _normalize_missing_fields(
        self,
        payloads: dict[str, AgentPayload],
    ) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}

        for agent_name, payload in payloads.items():
            assessment = payload.get("assessment", {})
            for raw_item in assessment.get("missing_fields", []) or []:
                if not isinstance(raw_item, dict):
                    continue

                normalized = self._normalize_missing_field_item(
                    agent_name=agent_name,
                    item=raw_item,
                )
                # Intentionally simplified: merge key uses field + reason_code so
                # remediation stays unified across agent domains instead of splitting
                # one operational gap into multiple domain-specific duplicates.
                key = (normalized["field"], normalized["reason_code"])

                existing = grouped.get(key)
                if existing is None:
                    grouped[key] = normalized
                    continue

                grouped[key] = self._merge_gap_items(existing, normalized)

        return sorted(
            grouped.values(),
            key=lambda item: (
                0 if item["blocking"] else 1,
                -_SEVERITY_RANK.get(item["severity"], 0),
                item["field"],
            ),
        )

    def _normalize_missing_field_item(
        self,
        *,
        agent_name: str,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        field = self._clean_string(item.get("field")) or "unknown.field"
        source_domain = (
            self._clean_string(item.get("source_domain"))
            or self._default_source_domain(agent_name)
        )
        reason = (
            self._clean_string(item.get("reason"))
            or "Missing or weak evidence for this field."
        )
        reason_code = self._normalize_reason_code(
            item=item,
            source_domain=source_domain,
        )
        severity = self._normalize_severity(item.get("severity"))
        can_be_inferred = bool(item.get("can_be_inferred", False))
        requires_supplier_confirmation = bool(
            item.get("requires_supplier_confirmation", False)
        )
        blocking = self._is_blocking_gap(
            field=field,
            severity=severity,
            reason_code=reason_code,
            source_domain=source_domain,
            can_be_inferred=can_be_inferred,
        )
        action = self._clean_string(item.get("action")) or self._default_action_for_gap(
            field=field,
            source_domain=source_domain,
            requires_supplier_confirmation=requires_supplier_confirmation,
        )
        owner_hint = self._derive_owner_hint(
            source_domain=source_domain,
            requires_supplier_confirmation=requires_supplier_confirmation,
        )
        current_evidence_status = self._derive_evidence_status(
            source_domain=source_domain,
            reason_code=reason_code,
            reason=reason,
        )
        acceptable_evidence = self._derive_acceptable_evidence(source_domain)
        why_it_matters = self._derive_why_it_matters(
            field=field,
            source_domain=source_domain,
            severity=severity,
            blocking=blocking,
        )
        where_to_get_data = self._derive_where_to_get_data(
            field=field,
            source_domain=source_domain,
            requires_supplier_confirmation=requires_supplier_confirmation,
        )
        closure_condition = self._derive_closure_condition(
            field=field,
            acceptable_evidence=acceptable_evidence,
        )

        return {
            "field": field,
            "severity": severity,
            "reason": reason,
            "action": action,
            "regulatory_basis": item.get("regulatory_basis"),
            "deadline": item.get("deadline"),
            "can_be_inferred": can_be_inferred,
            "requires_supplier_confirmation": requires_supplier_confirmation,
            "source_domain": source_domain,
            # Intentionally simplified: gap_id is field + reason_code for stable
            # re-entry matching and unified remediation. We do not include source_domain
            # here because DataAuditAgent synthesizes one canonical operational gap
            # from multiple agent signals.
            "gap_id": f"{field}:{reason_code}",
            "blocking": blocking,
            "reason_code": reason_code,
            "source_agents": [agent_name],
            "current_evidence_status": current_evidence_status,
            "closure_condition": closure_condition,
            "acceptable_evidence": acceptable_evidence,
            "why_it_matters": why_it_matters,
            "owner_hint": owner_hint,
            "where_to_get_data": where_to_get_data,
        }

    def _merge_gap_items(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
    ) -> dict[str, Any]:
        left_rank = _SEVERITY_RANK.get(left.get("severity", "optional"), 0)
        right_rank = _SEVERITY_RANK.get(right.get("severity", "optional"), 0)

        primary_source = left if left_rank >= right_rank else right
        secondary = right if primary_source is left else left
        primary = dict(primary_source)

        primary["source_agents"] = sorted(
            set((left.get("source_agents") or []) + (right.get("source_agents") or []))
        )
        primary["blocking"] = bool(left.get("blocking")) or bool(right.get("blocking"))
        primary["requires_supplier_confirmation"] = bool(
            left.get("requires_supplier_confirmation")
        ) or bool(right.get("requires_supplier_confirmation"))
        primary["can_be_inferred"] = bool(left.get("can_be_inferred")) and bool(
            right.get("can_be_inferred")
        )

        primary["acceptable_evidence"] = self._dedupe_list(
            (left.get("acceptable_evidence") or [])
            + (right.get("acceptable_evidence") or [])
        )

        primary["reason"] = self._merge_sentences(
            left.get("reason"),
            right.get("reason"),
        )
        primary["why_it_matters"] = self._merge_sentences(
            left.get("why_it_matters"),
            right.get("why_it_matters"),
        )
        primary["action"] = self._choose_preferred_text(
            left.get("action"),
            right.get("action"),
        )
        primary["where_to_get_data"] = self._choose_preferred_text(
            left.get("where_to_get_data"),
            right.get("where_to_get_data"),
        )
        primary["closure_condition"] = self._choose_preferred_text(
            left.get("closure_condition"),
            right.get("closure_condition"),
        )

        primary["current_evidence_status"] = self._merge_evidence_status(
            left.get("current_evidence_status"),
            right.get("current_evidence_status"),
        )

        if not primary.get("regulatory_basis"):
            primary["regulatory_basis"] = secondary.get("regulatory_basis")
        if not primary.get("deadline"):
            primary["deadline"] = secondary.get("deadline")

        return primary

    # ------------------------------------------------------------------
    # Contradictions / warnings
    # ------------------------------------------------------------------

    def _collect_agent_contradictions(
        self,
        payloads: dict[str, AgentPayload],
    ) -> list[str]:
        contradictions: list[str] = []

        for agent_name, payload in payloads.items():
            assessment = payload.get("assessment", {})
            for entry in assessment.get("contradictions", []) or []:
                if isinstance(entry, str) and entry.strip():
                    contradictions.append(f"{agent_name}: {entry.strip()}")

        return contradictions

    def _collect_agent_warnings(
        self,
        payloads: dict[str, AgentPayload],
    ) -> list[str]:
        warnings: list[str] = []

        for agent_name, payload in payloads.items():
            assessment = payload.get("assessment", {})
            for entry in assessment.get("warnings", []) or []:
                if isinstance(entry, str) and entry.strip():
                    warnings.append(f"{agent_name}: {entry.strip()}")

        return warnings

    def _build_structural_contradictions(
        self,
        domain_data: dict[str, Any],
    ) -> list[str]:
        contradictions: list[str] = []

        espr_core = domain_data.get("espr_core", {})
        sectoral = domain_data.get("sectoral", {})

        filled_sectoral = [
            key
            for key in ("textiles", "batteries", "electrical_appliances")
            if sectoral.get(key) is not None
        ]
        if len(filled_sectoral) != 1:
            contradictions.append(
                "Final state must contain exactly one non-null sectoral block."
            )
            return contradictions

        selected_sector = filled_sectoral[0]
        product_group = espr_core.get("product_group")
        espr_category = espr_core.get("espr_category")
        sector_profile_name = (espr_core.get("sector_profile") or {}).get("name")

        if product_group != selected_sector:
            contradictions.append(
                f"Final state product_group '{product_group}' does not match selected sectoral block '{selected_sector}'."
            )

        expected_profile = {
            "textiles": "textile_core_v1",
            "batteries": "battery_passport_annex_xiii_v1",
            "electrical_appliances": "electrical_appliance_espr_ready_v1",
        }.get(selected_sector)

        if espr_category != selected_sector:
            contradictions.append(
                f"Final state espr_category '{espr_category}' does not match product_group '{selected_sector}'."
            )

        if sector_profile_name != expected_profile:
            contradictions.append(
                f"Final state sector_profile.name '{sector_profile_name}' does not match expected profile '{expected_profile}'."
            )

        return contradictions

    def _build_cross_agent_warnings(
        self,
        domain_data: dict[str, Any],
        payloads: dict[str, AgentPayload],
    ) -> list[str]:
        warnings: list[str] = []

        final_group = (domain_data.get("espr_core") or {}).get("product_group")
        vision_payload = payloads.get("VisionAgent")
        if vision_payload is not None:
            hinted_group = (
                (vision_payload.get("domain_data") or {})
                .get("espr_core", {})
                .get("product_group_hint")
            )
            if hinted_group and final_group and hinted_group != final_group:
                warnings.append(
                    "VisionAgent product-group hint differs from final classification; this is non-blocking because vision owns only a weak hint."
                )

        if (
            vision_payload is not None
            and (vision_payload.get("domain_data") or {})
            .get("espr_core", {})
            .get("visible_certifications")
            and payloads.get("LegalAgent") is not None
        ):
            warnings.append(
                "Visible certification claims should not be treated as confirmed certification validity without documentary support."
            )

        return warnings

    # ------------------------------------------------------------------
    # Verdict and scoring
    # ------------------------------------------------------------------

    def _build_blocking_issues(
        self,
        normalized_gaps: list[dict[str, Any]],
        contradictions: list[str],
    ) -> list[str]:
        issues: list[str] = []

        for contradiction in contradictions:
            issues.append(f"conflict:{contradiction}")

        for gap in normalized_gaps:
            if gap.get("blocking"):
                issues.append(f"{gap['field']}:{gap['reason_code']}")

        return self._dedupe_strings(issues)

    def _compute_needs_human_review(
        self,
        payloads: dict[str, AgentPayload],
        normalized_gaps: list[dict[str, Any]],
        contradictions: list[str],
    ) -> bool:
        if contradictions:
            return True

        for payload in payloads.values():
            assessment = payload.get("assessment", {})
            if assessment.get("needs_human_review") is True:
                return True

        return any(
            gap.get("reason_code") in {"human_review_required", "unverified", "inconsistent"}
            for gap in normalized_gaps
        )

    def _determine_readiness_verdict(
        self,
        *,
        normalized_gaps: list[dict[str, Any]],
        contradictions: list[str],
        needs_human_review: bool,
    ) -> str:
        if contradictions:
            return "blocked_by_conflicts"

        if any(gap.get("blocking") for gap in normalized_gaps):
            return "not_ready"

        if normalized_gaps or needs_human_review:
            return "ready_with_gaps"

        return "ready"

    def _compute_readiness_score(
        self,
        *,
        normalized_gaps: list[dict[str, Any]],
        contradictions: list[str],
        needs_human_review: bool,
        readiness_verdict: str,
    ) -> int:
        score = 100

        for gap in normalized_gaps:
            severity = gap.get("severity")
            if severity == "critical":
                score -= 20
            elif severity == "required":
                score -= 10
            elif severity == "recommended":
                score -= 4
            else:
                score -= 1

            if gap.get("blocking"):
                score -= 5

        score -= 15 * len(contradictions)

        if needs_human_review:
            score -= 5

        score = max(0, min(100, score))

        if readiness_verdict == "blocked_by_conflicts":
            score = min(score, 24)
        elif readiness_verdict == "not_ready":
            score = min(score, 49)
        elif readiness_verdict == "ready_with_gaps":
            score = min(max(score, 50), 89)
        else:
            score = max(score, 90)

        return score

    # ------------------------------------------------------------------
    # Advisory synthesis
    # ------------------------------------------------------------------

    def _build_agent_summary(
        self,
        *,
        readiness_verdict: str,
        readiness_score: int,
        blocking_issues: list[str],
        gap_count: int,
    ) -> str:
        status_map = {
            "ready": "ready",
            "ready_with_gaps": "ready with gaps",
            "not_ready": "not ready",
            "blocked_by_conflicts": "blocked by conflicts",
        }
        summary = (
            f"Passport readiness is {status_map[readiness_verdict]} "
            f"({readiness_score}/100). "
            f"Normalized audit found {gap_count} gap(s) and {len(blocking_issues)} blocking issue(s)."
        )
        return summary[:500]

    def _build_business_risks(
        self,
        *,
        normalized_gaps: list[dict[str, Any]],
        contradictions: list[str],
        needs_human_review: bool,
    ) -> list[dict[str, str]]:
        risks: list[dict[str, str]] = []

        if contradictions:
            risks.append(
                {
                    "title": "Conflicting evidence blocks a defensible passport",
                    "severity": "high",
                    "why_it_matters": (
                        "Conflicting sector/classification or cross-agent signals undermine trust, "
                        "traceability and audit defensibility."
                    ),
                }
            )

        if any(gap.get("blocking") for gap in normalized_gaps):
            risks.append(
                {
                    "title": "Blocking evidence gaps prevent publishable output",
                    "severity": "high",
                    "why_it_matters": (
                        "Required identifiers, documentation or regulatory evidence are still missing "
                        "or unverified, so publication should be blocked."
                    ),
                }
            )

        if any(gap.get("current_evidence_status") == "photo_only" for gap in normalized_gaps):
            risks.append(
                {
                    "title": "Photo-only evidence leaves key fields weakly supported",
                    "severity": "medium",
                    "why_it_matters": (
                        "Visible labels can support a draft, but they are often insufficient for strong "
                        "documentary traceability or legal defensibility."
                    ),
                }
            )

        if needs_human_review:
            risks.append(
                {
                    "title": "Human review remains necessary",
                    "severity": "medium",
                    "why_it_matters": (
                        "Some findings need manual confirmation before the passport can be treated as "
                        "operationally reliable."
                    ),
                }
            )

        return risks

    def _build_recommended_actions(
        self,
        *,
        normalized_gaps: list[dict[str, Any]],
        contradictions: list[str],
    ) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []

        if contradictions:
            actions.append(
                {
                    "priority": "now",
                    "action": "Resolve classification and sector alignment conflicts before re-running packaging or publication checks.",
                    "owner": "internal_compliance",
                }
            )

        seen: set[tuple[str, str, str]] = set()
        for gap in normalized_gaps:
            owner = gap.get("owner_hint", "unknown")
            priority = self._priority_for_gap(gap)
            action = gap.get("action") or f"Provide evidence for {gap['field']}."
            key = (priority, owner, action)
            if key in seen:
                continue
            seen.add(key)
            actions.append(
                {
                    "priority": priority,
                    "action": action,
                    "owner": owner,
                }
            )

        return actions

    def _build_supplier_requests(
        self,
        normalized_gaps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        seen: set[str] = set()

        for gap in normalized_gaps:
            if not gap.get("requires_supplier_confirmation"):
                continue

            request = f"Provide authoritative evidence for {gap['field']}."
            if request in seen:
                continue
            seen.add(request)

            requests.append(
                {
                    "request": request,
                    "why_needed": gap.get("why_it_matters"),
                    "document_type": "supporting document or supplier statement",
                }
            )

        return requests

    def _build_where_to_get_data(
        self,
        normalized_gaps: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        locations: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for gap in normalized_gaps:
            source = gap.get("where_to_get_data")
            topic = gap.get("field")
            if not source or not topic:
                continue

            key = (topic, source)
            if key in seen:
                continue
            seen.add(key)

            locations.append(
                {
                    "missing_topic": topic,
                    "source": source,
                    "how_to_obtain": gap.get("closure_condition") or gap.get("action") or "",
                }
            )

        return locations

    def _build_next_batch_improvements(
        self,
        *,
        normalized_gaps: list[dict[str, Any]],
        payloads: dict[str, AgentPayload],
    ) -> list[str]:
        improvements: list[str] = []

        if any(gap.get("current_evidence_status") == "photo_only" for gap in normalized_gaps):
            improvements.append(
                "Add a guided multi-photo capture checklist so label close-ups, packaging and rear-side markings are collected in the first submission."
            )

        if any(gap.get("source_domain") == "legal" for gap in normalized_gaps):
            improvements.append(
                "Collect declaration and technical-document references at intake instead of waiting for review-time remediation."
            )

        if any(gap.get("source_domain") == "gs1" for gap in normalized_gaps):
            improvements.append(
                "Assign stable identifiers and resolver URLs before final packaging to avoid late-stage traceability blockers."
            )

        if payloads.get("LCASpecialist") is not None and any(
            gap.get("source_domain") == "lca" for gap in normalized_gaps
        ):
            improvements.append(
                "Treat environmental data as supplier-provided evidence, not as a value to infer from weak product context."
            )

        return self._dedupe_strings(improvements)

    # ------------------------------------------------------------------
    # Derivation helpers
    # ------------------------------------------------------------------

    def _normalize_reason_code(
        self,
        *,
        item: dict[str, Any],
        source_domain: str,
    ) -> str:
        explicit = self._clean_string(item.get("reason_code"))
        if explicit:
            return explicit

        reason = (self._clean_string(item.get("reason")) or "").lower()

        if "inconsisten" in reason or "conflict" in reason or "mismatch" in reason:
            return "inconsistent"
        if "unverified" in reason or "not verified" in reason:
            return "unverified"
        if "document" in reason and any(
            token in reason for token in ("missing", "absent", "not provided")
        ):
            return "document_absent"
        if "human review" in reason:
            return "human_review_required"
        if "not accessible" in reason or "cannot access" in reason:
            return "not_accessible"
        if source_domain == "vision":
            return "photo_insufficient"
        return "missing"

    def _normalize_severity(self, value: Any) -> str:
        if value in _SEVERITY_RANK:
            return value
        return "required"

    def _is_blocking_gap(
        self,
        *,
        field: str,
        severity: str,
        reason_code: str,
        source_domain: str,
        can_be_inferred: bool,
    ) -> bool:
        if severity == "critical":
            return True

        if reason_code == "inconsistent":
            return True

        if any(token in field for token in _FIELD_PRIORITY_HINTS):
            return True

        if severity == "required" and source_domain in {"regulatory", "legal", "gs1"} and not can_be_inferred:
            return True

        if reason_code in _BLOCKING_REASON_CODES and source_domain in {"regulatory", "legal", "gs1"}:
            return True

        return False

    def _derive_owner_hint(
        self,
        *,
        source_domain: str,
        requires_supplier_confirmation: bool,
    ) -> str:
        if requires_supplier_confirmation:
            return "supplier"
        if source_domain == "gs1":
            return "brand_owner"
        if source_domain in {"regulatory", "legal"}:
            return "internal_compliance"
        if source_domain == "lca":
            return "manufacturer"
        if source_domain == "vision":
            return "manufacturer"
        return "unknown"

    def _derive_evidence_status(
        self,
        *,
        source_domain: str,
        reason_code: str,
        reason: str,
    ) -> str:
        if reason_code == "photo_insufficient" or source_domain == "vision":
            return "photo_only"
        if reason_code == "unverified":
            return "document_present_unverified"
        if "claim" in reason.lower():
            return "claim_only"
        return "absent"

    def _derive_acceptable_evidence(self, source_domain: str) -> list[str]:
        if source_domain == "vision":
            return ["photo", "document", "manual_entry"]
        if source_domain == "gs1":
            return ["system_export","document"]
        if source_domain == "lca":
            return ["document", "system_export", "supplier_confirmation"]
        if source_domain in {"legal", "regulatory"}:
            return ["document", "manual_entry", "supplier_confirmation"]
        return ["document", "manual_entry"]

    def _derive_why_it_matters(
        self,
        *,
        field: str,
        source_domain: str,
        severity: str,
        blocking: bool,
    ) -> str:
        if source_domain == "gs1":
            return (
                "Identifiers and resolver readiness are needed for durable traceability, "
                "data-carrier generation and stable product linkage."
            )
        if source_domain == "legal":
            return (
                "Documentary support is needed so the passport can be defended beyond visible claims "
                "or informal statements."
            )
        if source_domain == "regulatory":
            return (
                "Regulatory classification and requiredness signals determine which fields must be "
                "present before publication."
            )
        if source_domain == "lca":
            return (
                "Environmental values should come from declared evidence, not from inferred or invented data."
            )
        if source_domain == "vision":
            return (
                "Photo-derived observations can support a draft passport, but weak visual evidence leaves "
                "field accuracy and traceability exposed."
            )
        if blocking or severity == "critical":
            return "This gap blocks a publishable and defensible passport."
        return f"This {severity} field is still weakly supported."

    def _derive_where_to_get_data(
        self,
        *,
        field: str,
        source_domain: str,
        requires_supplier_confirmation: bool,
    ) -> str:
        if requires_supplier_confirmation:
            return "supplier documentation or direct supplier confirmation"
        if source_domain == "gs1":
            return "ERP, PIM, barcode registry, or trusted product master data"
        if source_domain == "legal":
            return "declaration of conformity, technical documentation, or compliance file"
        if source_domain == "regulatory":
            return "classification worksheet, compliance notes, or product master data"
        if source_domain == "lca":
            return "EPD, LCA report, supplier sustainability file, or verified system export"
        if source_domain == "vision":
            return "close-up product photos, packaging images, or label photos"
        return f"authoritative source for {field}"

    def _derive_closure_condition(
        self,
        *,
        field: str,
        acceptable_evidence: list[str],
    ) -> str:
        evidence_list = ", ".join(acceptable_evidence)
        return (
            f"Provide authoritative evidence for {field} using one of: {evidence_list}. "
            "The gap closes only when the value is present and defensible."
        )

    def _default_action_for_gap(
        self,
        *,
        field: str,
        source_domain: str,
        requires_supplier_confirmation: bool,
    ) -> str:
        if requires_supplier_confirmation:
            return f"Request supplier confirmation or evidence for {field}."
        if source_domain == "vision":
            return f"Upload a clearer close-up image or provide a documented value for {field}."
        if source_domain == "gs1":
            return f"Provide the authoritative identifier or resolver data for {field}."
        if source_domain == "legal":
            return f"Provide documentary support for {field}."
        if source_domain == "regulatory":
            return f"Confirm the required value for {field} from compliant product records."
        if source_domain == "lca":
            return f"Provide declared sustainability evidence for {field}."
        return f"Provide authoritative evidence for {field}."

    def _priority_for_gap(self, gap: dict[str, Any]) -> str:
        if gap.get("blocking") or gap.get("severity") == "critical":
            return "now"
        if gap.get("severity") == "required":
            return "soon"
        return "later"

    def _default_source_domain(self, agent_name: str) -> str:
        return {
            "VisionAgent": "vision",
            "RegulatoryConsultant": "regulatory",
            "LegalAgent": "legal",
            "LCASpecialist": "lca",
            "GS1Specialist": "gs1",
        }.get(agent_name, "audit")

    # ------------------------------------------------------------------
    # Generic utilities
    # ------------------------------------------------------------------

    def _choose_preferred_text(self, left: Any, right: Any) -> str:
        left_text = self._clean_string(left)
        right_text = self._clean_string(right)
        if left_text and right_text:
            return left_text if len(left_text) >= len(right_text) else right_text
        return left_text or right_text or ""

    def _merge_sentences(self, left: Any, right: Any) -> str:
        values = [
            text
            for text in [self._clean_string(left), self._clean_string(right)]
            if text
        ]
        return " ".join(self._dedupe_list(values))

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        cleaned = [
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        ]
        return self._dedupe_list(cleaned)

    def _dedupe_list(self, values: list[Any]) -> list[Any]:
        result: list[Any] = []
        seen: set[Any] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _clean_string(self, value: Any) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None
    
    def _merge_evidence_status(self, left: Any, right: Any) -> str:
        left_value = left if left in _EVIDENCE_STATUS_RANK else "absent"
        right_value = right if right in _EVIDENCE_STATUS_RANK else "absent"

        return (
            left_value
            if _EVIDENCE_STATUS_RANK[left_value] >= _EVIDENCE_STATUS_RANK[right_value]
            else right_value
        )
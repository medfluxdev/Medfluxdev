"""Feldgruppen-Extraktions-Pipeline (STEP 8B-Semantik).

Pipeline je Dokument:
  1. deterministisches Chunking
  2. je Chunk je Gruppe: spezialisierte KI-Anfrage
  3. deterministisches Merging
  4. Übernahme auf Contract
  5. Evidence-First-Verifikation
  6. deterministisches Source-Grounding + Normalisierung
  7. semantischer Verifier
  8. Review-Flags + Diagnose
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError

from app.ai.groups.evidence import verify_evidence
from app.ai.groups.normalize import ground_source_identity, run_normalization
from app.ai.groups.schema import GroupSpec, group_order, group_specs
from app.ai.groups.verifier import SENSITIVE_FIELDS, run_verifier, unsupported_fields
from app.ai.service import AIService
from app.core.config import Settings
from app.documents.extraction.schemas import ExtractionUnit
from app.models.contract import Contract
from app.models.enums import BillingInterval, ReviewFlag, ReviewStatus

logger = logging.getLogger(__name__)

MSG_GROUP_INVALID_JSON = "Die Modell-Ausgabe war kein gültiges JSON zu entnehmen."
MSG_GROUP_VALIDATION = "Die extrahierten Daten konnten nicht vollständig validiert werden."


@dataclass
class PipelineDiagnostics:
    ai_calls: int = 0
    groups_processed: int = 0
    chunk_count: int = 0
    timeouts: int = 0
    retries: int = 0
    truncated_chunks: int = 0
    parse_failures: int = 0
    group_validation_failures: int = 0
    evidence_issues: int = 0
    verifier_issues: int = 0
    normalization_issues: int = 0


class GroupPipeline:
    def __init__(
        self,
        ai_service: AIService,
        settings: Settings,
        max_retries: int = 1,
        run_verification: bool = True,
    ) -> None:
        self._ai = ai_service
        self._settings = settings
        self._max_retries = max_retries
        self._run_verification = run_verification
        self._specs: dict[str, GroupSpec] = group_specs()

    async def run(
        self,
        chunks: list[Any],
        units: list[ExtractionUnit],
    ) -> tuple[Optional[Contract], PipelineDiagnostics, list[str]]:
        diag = PipelineDiagnostics(chunk_count=len(chunks))
        messages: list[str] = []
        order = group_order()

        per_chunk: dict[int, dict[str, Any]] = {}
        for chunk in chunks:
            per_opts: dict[str, Any] = {}
            for name in order:
                outcome = await self._extract_group_for_chunk(chunk, name)
                diag.ai_calls += outcome.ai_calls
                diag.groups_processed += 1
                diag.timeouts += outcome.timeouts
                diag.retries += outcome.retries
                diag.truncated_chunks += outcome.truncated
                diag.parse_failures += outcome.parse_failures
                diag.group_validation_failures += outcome.validation_failures
                per_opts[name] = outcome
            per_chunk[chunk.index] = per_opts

        merged_groups: dict[str, Any] = {}
        for name in order:
            results = [
                per_chunk[ci][name]
                for ci in sorted(per_chunk)
                if per_chunk[ci][name].model is not None
            ]
            if not results:
                merged_groups[name] = None
                continue
            spec = self._specs[name]
            merged, conflicts = self._merge_models(
                spec.model, [r.model for r in results]
            )
            merged_groups[name] = merged
            for conflict in conflicts:
                messages.append(f"Merge-Konflikt {name}: {conflict}")

        contract = Contract()
        any_group_failures = (
            diag.parse_failures > 0
            or diag.group_validation_failures > 0
            or diag.timeouts > 0
        )
        for name in order:
            gm = merged_groups.get(name)
            if gm is not None:
                self._specs[name].apply(contract, gm)

        if any_group_failures:
            messages.append(
                "Einzelne Gruppen-Extraktionen schlugen fehl – betroffene Felder fehlen möglicherweise."
            )

        if not any(v is not None for v in merged_groups.values()):
            return None, diag, [MSG_GROUP_VALIDATION]

        # Deterministic source grounding is a successful correction path, not a
        # review condition. Keep its notes in diagnostics/logging only. Review
        # flags are reserved for actual evidence/verifier/normalization problems.
        source_notes = ground_source_identity(contract, units)
        diag.normalization_issues += len(source_notes)
        if source_notes:
            logger.info(
                "Deterministic source grounding applied %d correction(s): %s",
                len(source_notes),
                source_notes,
            )

        evidence_issues = self._verify_evidence_on_contract(contract, units)
        diag.evidence_issues += len(evidence_issues)
        messages.extend(evidence_issues)

        norm_issues = run_normalization(contract)
        diag.normalization_issues += len(norm_issues)
        messages.extend(norm_issues)

        if self._run_verification:
            expected_fields = self._expected_verifier_fields(contract)
            verifier_result, calls = await run_verifier(
                self._ai,
                contract,
                self._context_text(chunks),
                units=units,
            )
            diag.ai_calls += calls

            verifier_issues = self._apply_verifier(contract, verifier_result)
            returned_fields = {
                decision.field for decision in getattr(verifier_result, "decisions", [])
            }
            missing_fields = expected_fields - returned_fields
            for field in sorted(missing_fields):
                verifier_issues.append(
                    f"Verifier: {field} ohne Entscheidung – manuelle Prüfung erforderlich"
                )

            diag.verifier_issues += len(verifier_issues)
            messages.extend(verifier_issues)

        messages.extend(self._scan_evidence_review(contract))
        self._finalize(contract, messages)
        return contract, diag, messages

    def _field_evidence_paths(self):
        return [
            ("identity", "identity_equipment"),
            ("dates", "dates_termination"),
            ("termination", "dates_termination"),
            ("costs", "costs_payment"),
            ("payment", "costs_payment"),
            ("services", "services_sla"),
            ("sla", "services_sla"),
        ]

    def _context_text(self, chunks) -> str:
        return "\n".join(c.text for c in chunks)[:6000]

    def _expected_verifier_fields(self, contract: Contract) -> set[str]:
        """Return every non-default sensitive claim that requires a decision."""
        expected: set[str] = set()
        for field in SENSITIVE_FIELDS:
            section_name, attr_name = field.split(".", 1)
            section = getattr(contract, section_name, None)
            if section is None:
                continue
            value = getattr(section, attr_name, None)
            if value is None:
                continue
            if field == "payment.billing_interval" and value in (
                BillingInterval.OTHER,
                BillingInterval.OTHER.value,
                "other",
            ):
                continue
            expected.add(field)
        return expected

    def _scan_evidence_review(self, contract: Contract) -> list[str]:
        issues: list[str] = []
        sections = [
            contract.identity,
            contract.dates,
            contract.termination,
            contract.costs,
            contract.payment,
            contract.services,
            contract.sla,
        ]
        for sec in sections:
            ev = getattr(sec, "evidence", None)
            if ev is not None and ev.requires_review:
                issues.append(f"{type(sec).__name__}: Nachweis erfordert manuelle Prüfung")
        return issues

    def _verify_evidence_on_contract(
        self, contract: Contract, units: list[ExtractionUnit]
    ) -> list[str]:
        issues: list[str] = []
        sections = [
            contract.identity,
            contract.dates,
            contract.termination,
            contract.costs,
            contract.payment,
            contract.services,
            contract.sla,
        ]
        for sec in sections:
            ev = getattr(sec, "evidence", None)
            if ev is None:
                continue
            verified, ev_issues = verify_evidence(ev, units)
            if verified is None:
                issues.append(f"{type(sec).__name__}: Nachweis entfernt (nicht belegt)")
                continue
            sec.evidence = verified
            for issue in ev_issues:
                issues.append(f"{type(sec).__name__}: {issue}")
            if verified.requires_review:
                issues.append(f"{type(sec).__name__}: Nachweis erfordert Prüfung")
        return issues

    def _apply_verifier(self, contract: Contract, result) -> list[str]:
        """Fail closed for every unsupported sensitive field.

        Section-level evidence is still downgraded when present, but manual
        review no longer depends on a section carrying evidence. Field-scoped
        verifier evidence can legitimately exist while ``section.evidence`` is
        absent; an unsupported critical claim must still reach the final review
        state and diagnostics in that case.
        """
        unsup = unsupported_fields(result)
        if not unsup:
            return []

        logger.info(
            "Verifier: %d nicht gestützte sensible Felder: %s",
            len(unsup),
            sorted(unsup),
        )
        sections = {
            "identity": contract.identity,
            "dates": contract.dates,
            "termination": contract.termination,
            "costs": contract.costs,
            "payment": contract.payment,
        }
        prefix_map = {
            "identity.": "identity",
            "dates.": "dates",
            "termination.": "termination",
            "costs.": "costs",
            "payment.": "payment",
        }
        flagged: set[str] = set()
        for field in unsup:
            for prefix, secname in prefix_map.items():
                if field.startswith(prefix):
                    flagged.add(secname)
                    break
        for secname in flagged:
            sec = sections.get(secname)
            if sec is None:
                continue
            ev = getattr(sec, "evidence", None)
            if ev is not None:
                ev.requires_review = True
                if ev.confidence is None or ev.confidence > 0.5:
                    ev.confidence = 0.5

        reasons = {
            decision.field: decision.reason
            for decision in getattr(result, "decisions", [])
            if decision.field in unsup and decision.reason
        }
        issues: list[str] = []
        for field in sorted(unsup):
            reason = reasons.get(field)
            if reason:
                issues.append(f"Verifier: {field} nicht gestützt ({reason})")
            else:
                issues.append(f"Verifier: {field} nicht gestützt")
        return issues

    def _finalize(self, contract: Contract, messages: list[str]) -> None:
        if not messages:
            return
        contract.review.requires_manual_review = True
        contract.review.review_status = ReviewStatus.NEEDS_REVIEW
        if ReviewFlag.VAGUE not in contract.review.review_reasons:
            contract.review.review_reasons.append(ReviewFlag.VAGUE)
        notes = "; ".join(messages[:8])
        contract.review.risk_notes = (
            f"{contract.review.risk_notes}; " if contract.review.risk_notes else ""
        ) + notes

    async def _extract_group_for_chunk(self, chunk, name: str) -> "GroupOutcome":
        spec = self._specs[name]
        user_prompt = _build_group_prompt(chunk, name)
        outcome = GroupOutcome(name=name)
        attempts = 0

        for attempt in range(self._max_retries + 1):
            attempts = attempt + 1
            system_prompt = spec.prompt
            if attempt > 0:
                system_prompt += _GROUP_RETRY_SUFFIX
            try:
                raw = await self._ai.generate_structured(
                    user_prompt,
                    system_prompt,
                    spec.schema,
                    max_tokens=self._settings.ai_extraction_max_tokens,
                )
                outcome.ai_calls += 1
            except Exception:
                outcome.timeouts += 1
                if attempt >= self._max_retries:
                    return outcome
                continue

            if self._ai.last_done_reason == "length":
                outcome.truncated += 1

            parsed_data = _parse_json(raw)
            if parsed_data is None:
                outcome.parse_failures += 1
                if attempt >= self._max_retries:
                    return outcome
                continue

            try:
                model = spec.model.model_validate(parsed_data)
            except ValidationError:
                outcome.validation_failures += 1
                if attempt >= self._max_retries:
                    return outcome
                continue

            outcome.model = model
            outcome.retries = max(0, attempts - 1)
            return outcome

        outcome.retries = max(0, attempts - 1)
        return outcome

    def _merge_models(self, model_type, models: list[Any]) -> tuple[Any, list[str]]:
        merged_data = models[0].model_dump(exclude_none=False)
        all_conflicts: list[str] = []
        for model in models[1:]:
            conflicts: list[str] = []
            merged_data = _deep_merge(
                merged_data,
                model.model_dump(exclude_none=False),
                conflicts,
                "$",
            )
            all_conflicts.extend(conflicts)
        return model_type.model_validate(merged_data), all_conflicts


@dataclass
class GroupOutcome:
    name: str
    model: Any = None
    ai_calls: int = 0
    timeouts: int = 0
    retries: int = 0
    truncated: int = 0
    parse_failures: int = 0
    validation_failures: int = 0


_GROUP_RETRY_SUFFIX = (
    "\n\nWICHTIG: Deine vorherige Antwort war KEIN gültiges JSON bzw. wich vom "
    "vorgegebenen Schema ab und wurde verworfen. Antworte jetzt AUSSCHLIESSLICH "
    "mit einem gültigen JSON-Objekt gemäß der vorgegebenen Struktur. Kein "
    "Markdown, kein Text davor/danach."
)


def _build_group_prompt(chunk, name: str) -> str:
    return (
        f"Dokumentauszug (Abschnitt {chunk.index}). "
        f"Alle Angaben müssen durch diesen Auszug belegt sein. "
        f"Extrahiere NUR die Felder der Gruppe '{name}'.\n\n{chunk.text}\n"
    )


def _parse_json(raw: str) -> Optional[dict[str, Any]]:
    if not raw or not raw.strip():
        return None
    stripped = raw.strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(stripped[start : i + 1])
                    return data if isinstance(data, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _deep_merge(old: Any, new: Any, conflicts: list[str], path: str) -> Any:
    if isinstance(old, dict) and isinstance(new, dict):
        out: dict[str, Any] = dict(old)
        for key, new_val in new.items():
            child = f"{path}.{key}"
            if key not in out:
                out[key] = new_val
            else:
                out[key] = _deep_merge(out[key], new_val, conflicts, child)
        return out
    if isinstance(old, list) and isinstance(new, list):
        return _merge_lists(old, new, conflicts, path)
    if old is None:
        return new
    if new is None:
        return old
    if old == new:
        return old
    conflicts.append(f"{path}: unterschiedliche Werte ({old!r} vs {new!r})")
    return old


def _merge_lists(old: list, new: list, conflicts: list[str], path: str) -> list:
    if new and isinstance(new[0], dict):
        merged = list(old)
        seen = {_list_key(item) for item in old}
        for item in new:
            key = _list_key(item)
            if key not in seen:
                merged.append(item)
                seen.add(key)
        return merged
    merged = list(old)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged


def _list_key(item: dict) -> tuple:
    return tuple(sorted((key, str(value)) for key, value in item.items()))

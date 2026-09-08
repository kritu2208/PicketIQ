"""Evidence reference and output grounding validator for PicketIQ LLM conclusions.

Enforces that every citation and segment claim in the conclusion corresponds to
actual verified data collected during the investigation.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from app.investigation.schema import InvestigationResult


def validate_investigation_conclusion(
    conclusion_data: Dict[str, Any],
    investigation_result: InvestigationResult,
) -> Tuple[bool, List[str]]:
    """Validate that an LLM conclusion adheres to evidence grounding and schema rules.

    Validations performed:
    1. Schema integrity: Required fields present and non-empty.
    2. Confidence level: Must be 'high', 'medium', or 'low'.
    3. Evidence reference grounding: Every reference must cite an existing, executed step number.
    4. Affected segment grounding: If an affected segment is claimed, it must exist in Step 1 data.
    5. Uncertainty honesty: High confidence is rejected if critical evidence was missing or failed.

    Args:
        conclusion_data: Raw JSON dictionary returned by the LLM provider.
        investigation_result: The verified InvestigationResult that was provided to the LLM.

    Returns:
        Tuple of (is_valid: bool, error_messages: List[str]).
    """
    errors: List[str] = []

    # 1. Required schema fields
    required_fields = ["root_cause", "explanation", "confidence", "evidence_references", "recommended_action"]
    for field in required_fields:
        if field not in conclusion_data or conclusion_data[field] is None:
            errors.append(f"Missing required field '{field}'.")
        elif isinstance(conclusion_data[field], str) and not conclusion_data[field].strip():
            errors.append(f"Field '{field}' cannot be empty.")

    # 2. Confidence validation
    confidence = str(conclusion_data.get("confidence", "")).lower().strip()
    valid_confidences = {"high", "medium", "low"}
    if confidence not in valid_confidences:
        errors.append(
            f"Invalid confidence '{confidence}'. Must be one of: {', '.join(sorted(valid_confidences))}."
        )

    # 3. Evidence References Validation
    refs = conclusion_data.get("evidence_references", [])
    if not isinstance(refs, list):
        errors.append("Field 'evidence_references' must be a list of strings.")
    elif len(refs) == 0:
        errors.append("Field 'evidence_references' must contain at least one citation.")
    else:
        executed_step_nums = {e.step_number for e in investigation_result.evidence}
        for ref in refs:
            if not isinstance(ref, str) or not ref.strip():
                errors.append(f"Invalid empty reference in evidence_references.")
                continue

            # Check if reference cites a Step number
            step_match = re.search(r"Step\s*(\d+)", ref, re.IGNORECASE)
            if step_match:
                cited_step = int(step_match.group(1))
                if cited_step not in executed_step_nums:
                    errors.append(
                        f"Hallucinated reference: Reference '{ref}' cites Step {cited_step}, "
                        f"but only steps {sorted(executed_step_nums)} were executed."
                    )
            else:
                # Reference does not follow standard Step citation format
                # Allow if it clearly references one of the tool names
                tool_names = {"segment_breakdown", "check_seasonality", "get_recent_trend"}
                if not any(t in ref.lower() for t in tool_names):
                    errors.append(
                        f"Unverified citation format: Reference '{ref}' must specify a valid 'Step X' or tool name."
                    )

    # 4. Affected Segment Validation
    affected_seg = conclusion_data.get("affected_segment")
    if affected_seg is not None and str(affected_seg).strip():
        seg_str = str(affected_seg).strip().upper()
        if investigation_result.breakdown and investigation_result.breakdown.status == "success":
            valid_segments = {s.segment.upper() for s in investigation_result.breakdown.segments}
            if seg_str not in valid_segments:
                errors.append(
                    f"Hallucinated segment: Affected segment '{seg_str}' was not found in "
                    f"regional breakdown segments ({', '.join(sorted(valid_segments)[:10])}...)."
                )
        elif not investigation_result.breakdown or investigation_result.breakdown.status != "success":
            errors.append(
                f"Unsubstantiated segment: Affected segment '{seg_str}' was specified, but "
                "regional breakdown evidence was unavailable or failed."
            )

    # 5. Uncertainty Honesty
    has_insufficient_data = any(
        e.status in ("insufficient_data", "error") for e in investigation_result.evidence
    )
    if has_insufficient_data and confidence == "high":
        errors.append(
            "Confidence mismatch: Confidence cannot be 'high' when one or more investigation "
            "evidence steps yielded insufficient data or encountered errors."
        )

    is_valid = len(errors) == 0
    return is_valid, errors

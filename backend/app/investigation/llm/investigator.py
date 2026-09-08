"""LLM Investigation coordinator connecting orchestrator evidence with language model synthesis.

Execution Flow:
    Anomaly ID
        │
        ▼
    Investigation Orchestrator (Phase 5C)
        │
        ▼
    Deterministic Evidence (Phase 5B)
        │
        ▼
    Grounding Context & Prompt Builder
        │
        ▼
    LLM Provider (Pluggable: Mock, OpenAI, Anthropic, Gemini)
        │
        ▼
    Evidence Reference & Segment Validation
        │
        ▼
    PostgreSQL Persistence & Structured Output
"""

import argparse
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import InvestigationConclusion
from app.investigation.schema import (
    InvestigationResult,
    InvestigationConclusionResult,
)
from app.investigation.orchestrator import investigate_anomaly
from app.investigation.llm.providers import (
    BaseLLMProvider,
    get_llm_provider,
)
from app.investigation.llm.prompts import (
    SYSTEM_INVESTIGATION_PROMPT,
    build_user_prompt,
)
from app.investigation.llm.validator import validate_investigation_conclusion

logger = logging.getLogger("picket_iq.investigation.llm.investigator")


def explain_investigation(
    investigation_result: InvestigationResult,
    provider: Optional[BaseLLMProvider] = None,
    session: Optional[Session] = None,
) -> InvestigationConclusionResult:
    """Interpret verified investigation evidence through an LLM to produce an evidence-grounded conclusion.

    Args:
        investigation_result: Completed investigation result containing anomaly details and evidence chain.
        provider: Optional BaseLLMProvider instance. If None, resolves from application config.
        session: Optional SQLAlchemy Session for persistence.

    Returns:
        Structured, validated InvestigationConclusionResult.
    """
    active_provider = provider or get_llm_provider()

    logger.info(
        "Interpreting investigation #%d with LLM provider '%s' (model: '%s')",
        investigation_result.investigation_id,
        active_provider.provider_name,
        active_provider.model_name,
    )

    # 1. Build prompt strictly from verified evidence
    user_prompt = build_user_prompt(investigation_result)

    # 2. Invoke LLM provider
    raw_conclusion = active_provider.generate_conclusion(
        system_prompt=SYSTEM_INVESTIGATION_PROMPT,
        user_prompt=user_prompt,
    )

    # 3. Validate evidence grounding and citations
    is_valid, validation_errors = validate_investigation_conclusion(
        conclusion_data=raw_conclusion,
        investigation_result=investigation_result,
    )

    if not is_valid:
        logger.warning(
            "Investigation conclusion validation failed with %d error(s): %s",
            len(validation_errors),
            "; ".join(validation_errors),
        )

    # 4. Construct typed result object
    created_at = datetime.utcnow()
    conclusion_result = InvestigationConclusionResult(
        investigation_id=investigation_result.investigation_id,
        anomaly_id=investigation_result.anomaly.anomaly_id,
        root_cause=raw_conclusion.get("root_cause", "Inconclusive / Insufficient Evidence"),
        explanation=raw_conclusion.get("explanation", ""),
        confidence=raw_conclusion.get("confidence", "low"),
        affected_segment=raw_conclusion.get("affected_segment"),
        evidence_references=raw_conclusion.get("evidence_references", []),
        recommended_action=raw_conclusion.get("recommended_action", ""),
        provider=active_provider.provider_name,
        model=active_provider.model_name,
        validation_passed=is_valid,
        validation_errors=validation_errors,
        created_at=created_at.isoformat(),
    )

    # 5. Persist to PostgreSQL if session available
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        conclusion_record = InvestigationConclusion(
            investigation_id=investigation_result.investigation_id,
            anomaly_id=investigation_result.anomaly.anomaly_id,
            root_cause=conclusion_result.root_cause,
            explanation=conclusion_result.explanation,
            confidence=conclusion_result.confidence,
            affected_segment=conclusion_result.affected_segment,
            evidence_references=conclusion_result.evidence_references,
            recommended_action=conclusion_result.recommended_action,
            provider=conclusion_result.provider,
            model_name=conclusion_result.model,
            validation_passed=is_valid,
            created_at=created_at,
        )
        session.add(conclusion_record)
        session.commit()
    except Exception as exc:
        logger.error("Failed to persist investigation conclusion to database: %s", exc)
        session.rollback()
    finally:
        if close_session:
            session.close()

    return conclusion_result


def investigate_and_explain(
    anomaly_id: int,
    provider: Optional[BaseLLMProvider] = None,
    session: Optional[Session] = None,
) -> InvestigationConclusionResult:
    """Run the complete Phase 5 investigation pipeline from Anomaly to LLM Conclusion.

    Pipeline:
        1. Anomaly ID -> Orchestrator (Phase 5C)
        2. Evidence Tools (Phase 5B)
        3. Verified Evidence -> Prompt Context
        4. LLM Provider -> Evidence-grounded interpretation
        5. Citation Validation & Persistence

    Args:
        anomaly_id: ID of detected anomaly in PostgreSQL anomalies table.
        provider: Optional BaseLLMProvider. Defaults to configured provider.
        session: Optional SQLAlchemy Session.

    Returns:
        Structured InvestigationConclusionResult.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        # Step 1: Deterministic Evidence Gathering
        inv_result = investigate_anomaly(anomaly_id=anomaly_id, session=session)

        # Step 2: LLM Interpretation
        return explain_investigation(
            investigation_result=inv_result,
            provider=provider,
            session=session,
        )
    finally:
        if close_session:
            session.close()


def main() -> None:
    """CLI entrypoint for LLM investigation layer."""
    parser = argparse.ArgumentParser(description="PicketIQ LLM Investigation Layer (Phase 5D)")
    parser.add_argument(
        "--anomaly-id",
        type=int,
        required=True,
        help="ID of the anomaly to investigate and explain",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM provider (mock, openai, anthropic, gemini)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output conclusion as structured JSON",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        active_provider = get_llm_provider(args.provider)
        conclusion = investigate_and_explain(
            anomaly_id=args.anomaly_id,
            provider=active_provider,
        )

        if args.json:
            print(json.dumps(conclusion.to_dict(), indent=2))
        else:
            print("\n" + "=" * 72)
            print(f"  LLM INVESTIGATION CONCLUSION FOR ANOMALY #{conclusion.anomaly_id}")
            print("=" * 72)
            print(f"Provider          : {conclusion.provider} ({conclusion.model})")
            print(f"Confidence        : {conclusion.confidence.upper()}")
            print(f"Affected Segment  : {conclusion.affected_segment or 'None / Evenly Distributed'}")
            print(f"Validation Passed : {conclusion.validation_passed}")
            if conclusion.validation_errors:
                print(f"Validation Errors : {'; '.join(conclusion.validation_errors)}")
            print(f"\nROOT CAUSE:\n  {conclusion.root_cause}")
            print(f"\nEXPLANATION:\n  {conclusion.explanation}")
            print(f"\nEVIDENCE REFERENCES:")
            for ref in conclusion.evidence_references:
                print(f"  • {ref}")
            print(f"\nRECOMMENDED ACTION:\n  {conclusion.recommended_action}\n")
    except Exception as exc:
        logger.error("LLM investigation failed: %s", exc, exc_info=True)


if __name__ == "__main__":
    main()

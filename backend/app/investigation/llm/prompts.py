"""Prompt templates and context builders for PicketIQ LLM investigation.

Enforces strict evidence grounding, prevents hallucinations, requires exact step citations,
and specifies the JSON output schema.
"""

from typing import Any
from app.investigation.schema import InvestigationResult

SYSTEM_INVESTIGATION_PROMPT = """You are the Senior Business Analyst and Root-Cause Investigator for PicketIQ, an Autonomous Business Signal Investigation Platform.
Your core principle: "When the numbers move, PicketIQ finds out why."

Your responsibility is to analyze the verified investigation evidence collected by deterministic database tools and synthesize an evidence-grounded investigation conclusion.

STRICT INVESTIGATION RULES:
1. GROUNDING: Every claim you make must be directly backed by the provided investigation evidence. Do not guess, speculate, or invent external causes (such as unmentioned marketing campaigns, external holidays, or supplier disruptions) unless evidenced in the data.
2. CITATIONS: In "evidence_references", you MUST cite specific executed steps using the exact format:
   "Step X (<tool_name>): <verified finding>"
   Do not reference step numbers that were not executed.
3. AFFECTED SEGMENT: If a specific regional segment clearly drove the anomaly (e.g., top contributor driving a large portion of the deviation), specify it in "affected_segment" (e.g., "SP"). If the deviation was evenly distributed across all segments or data is missing, set "affected_segment": null.
4. INSUFFICIENT DATA / UNCERTAINTY: If the evidence is insufficient to determine a root cause (e.g. tools reported "insufficient_data", baseline sample size was zero, or multiple tools failed), you MUST explicitly state "Inconclusive / Insufficient Evidence" in "root_cause", set "confidence": "low", and explain the exact evidentiary gaps in "explanation". DO NOT GUESS.
5. CONFIDENCE TIERS:
   - "high": All 3 evidence tools succeeded, baseline is robust, and a clear driving pattern (e.g. dominant segment, non-seasonal spike, sudden step jump) is confirmed by evidence.
   - "medium": Evidence is partially complete or movement is moderate without a single dominant segment.
   - "low": Evidence is inconclusive, conflicting, or historical data is insufficient.
6. RECOMMENDED ACTION: Provide a concrete, pragmatic operational recommendation for business operators based on the metric and affected segment.

OUTPUT FORMAT:
Respond with a single, strictly valid JSON object matching this schema:
{
  "root_cause": "string (concise summary of the verified driver, <= 200 chars)",
  "explanation": "string (evidence-grounded explanation detailing how the findings explain the movement)",
  "confidence": "high" | "medium" | "low",
  "affected_segment": "string (e.g. 'SP') or null",
  "evidence_references": [
    "Step 1 (segment_breakdown): ...",
    "Step 2 (check_seasonality): ...",
    "Step 3 (get_recent_trend): ..."
  ],
  "recommended_action": "string (concrete operational next step)"
}
"""


def build_user_prompt(inv: InvestigationResult) -> str:
    """Format structured investigation evidence into context for the LLM."""
    lines = [
        "=== ANOMALY UNDER INVESTIGATION ===",
        f"Anomaly ID   : {inv.anomaly.anomaly_id}",
        f"Metric       : {inv.anomaly.metric_name}",
        f"Date         : {inv.anomaly.date}",
        f"Actual Value : {inv.anomaly.actual_value}",
        f"Expected Val : {inv.anomaly.expected_value}",
        f"Z-Score      : {inv.anomaly.z_score:+}",
        f"Severity     : {inv.anomaly.severity}",
        f"Status       : {inv.status}",
        "",
        "=== VERIFIED INVESTIGATION EVIDENCE CHAIN ===",
    ]

    # Step 1: Segment Breakdown
    lines.append(f"--- STEP 1: Regional Segment Breakdown (customer_state) ---")
    if inv.breakdown and inv.breakdown.status == "success":
        bd = inv.breakdown
        lines.append(f"Status           : {bd.status}")
        lines.append(f"Total Actual     : {bd.total_actual}")
        lines.append(f"Total Baseline   : {bd.total_baseline}")
        lines.append(f"Total Net Delta  : {bd.total_delta:+}")
        if bd.top_contributor:
            top = bd.top_contributor
            pct = f"{top.percentage_contribution:+.2f}%" if top.percentage_contribution is not None else "N/A"
            share = f"{top.share_of_total:.2f}%" if top.share_of_total is not None else "N/A"
            lines.append(f"Top Contributor  : {top.segment}")
            lines.append(f"  Actual Value   : {top.actual_value}")
            lines.append(f"  Baseline Value : {top.baseline_value}")
            lines.append(f"  Absolute Delta : {top.absolute_delta:+}")
            lines.append(f"  Contribution   : {pct}")
            lines.append(f"  Share of Total : {share}")
        # Top 3 segments summary
        top_segs = [s.segment for s in bd.segments[:5]]
        lines.append(f"Leading Segments : {', '.join(top_segs)}")
        lines.append(f"Tool Summary     : {bd.summary}")
    elif inv.breakdown:
        lines.append(f"Status           : {inv.breakdown.status} (INSUFFICIENT DATA)")
        lines.append(f"Tool Summary     : {inv.breakdown.summary}")
    else:
        lines.append("Status           : Step failed or was skipped")

    lines.append("")

    # Step 2: Seasonality Analysis
    lines.append(f"--- STEP 2: Weekly Day-of-Week Seasonality Analysis ---")
    if inv.seasonality and inv.seasonality.status == "success":
        sn = inv.seasonality
        lines.append(f"Status           : {sn.status}")
        lines.append(f"Day of Week      : {sn.day_of_week_name} (Index: {sn.day_of_week})")
        lines.append(f"Target Value     : {sn.target_value}")
        lines.append(f"Same-DOW Mean    : {sn.same_dow_mean}")
        lines.append(f"Same-DOW StdDev  : {sn.same_dow_std}")
        lines.append(f"Same-DOW Z-Score : {sn.same_dow_zscore:+}")
        lines.append(f"Is Seasonal      : {sn.is_seasonal}")
        lines.append(f"Sample Size      : {sn.sample_size} weeks")
        lines.append(f"Tool Summary     : {sn.summary}")
    elif inv.seasonality:
        lines.append(f"Status           : {inv.seasonality.status} (INSUFFICIENT DATA)")
        lines.append(f"Tool Summary     : {inv.seasonality.summary}")
    else:
        lines.append("Status           : Step failed or was skipped")

    lines.append("")

    # Step 3: Trajectory Trend
    lines.append(f"--- STEP 3: Recent Trajectory Trend Analysis (14 Days) ---")
    if inv.recent_trend and inv.recent_trend.status == "success":
        tr = inv.recent_trend
        lines.append(f"Status           : {tr.status}")
        lines.append(f"Window Evaluated : {tr.window_days} days ({tr.observations_count} observations)")
        lines.append(f"Classification   : {tr.classification}")
        lines.append(f"Target Value     : {tr.target_value}")
        lines.append(f"Preceding Mean   : {tr.preceding_mean}")
        lines.append(f"Preceding StdDev : {tr.preceding_std}")
        lines.append(f"Trend Slope      : {tr.preceding_trend_slope:+}")
        lines.append(f"Single-Day Delta : {tr.single_day_delta:+}")
        if tr.single_day_pct_change is not None:
            lines.append(f"Single-Day Pct   : {tr.single_day_pct_change:+}%")
        lines.append(f"Tool Summary     : {tr.summary}")
    elif inv.recent_trend:
        lines.append(f"Status           : {inv.recent_trend.status} (INSUFFICIENT DATA)")
        lines.append(f"Tool Summary     : {inv.recent_trend.summary}")
    else:
        lines.append("Status           : Step failed or was skipped")

    lines.append("")
    lines.append("Based solely on this verified evidence, synthesize the structured investigation conclusion.")
    return "\n".join(lines)

"""
Generates the final incident report using LangChain LCEL + Groq.
Falls back to a template-based report if Groq is unavailable.
"""

import structlog
from config import GROQ_API_KEY, GROQ_MODEL
from pipeline.processor import AnalysisResult
from prompts import INCIDENT_REPORT_PROMPT

logger = structlog.get_logger(__name__)


class ReportGenerator:
    _llm: object | None = None

    def _get_llm(self):
        """Lazily load Groq LLM. Returns None if key not configured."""
        if ReportGenerator._llm is None and GROQ_API_KEY:
            from langchain_groq import ChatGroq

            ReportGenerator._llm = ChatGroq(
                model=GROQ_MODEL,
                api_key=GROQ_API_KEY,
                temperature=0.1,
                max_tokens=1000,
            )
        return ReportGenerator._llm

    def generate(self, result: AnalysisResult) -> str:
        """
        Generate incident report. Uses Groq if available, otherwise template fallback.
        """
        from langchain_core.output_parsers import StrOutputParser

        llm = self._get_llm()
        if llm is None:
            return self._template_fallback(result)

        chain = (
            INCIDENT_REPORT_PROMPT
            | llm.with_config(run_name="incident_report_generation", tags=["loglens"])
            | StrOutputParser()
        )

        formatted_input = self._format_analysis_for_prompt(result)
        try:
            return chain.invoke(formatted_input)
        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            return self._template_fallback(result)

    def _template_fallback(self, result: AnalysisResult) -> str:
        """Structured report without LLM — same sections as the LLM prompt."""
        tr = result.time_range
        tr_s = f"{tr[0]} → {tr[1]}" if tr[0] or tr[1] else "unknown"

        rc_lines = []
        for r in result.root_causes:
            rc_lines.append(
                f"- **{r.category}** ({r.confidence}): {r.hypothesis}\n"
                f"  - Evidence: {', '.join(r.evidence[:3])}"
            )

        an_lines = []
        for a in result.anomalies[:15]:
            an_lines.append(
                f"- [{a.severity}] {a.anomaly_type} @ {a.timestamp}: {a.description}"
            )

        cl_lines = []
        for c in result.error_clusters[:15]:
            cl_lines.append(
                f"- ({c.count}x) {c.representative_message[:200]} "
                f"[{c.first_seen} – {c.last_seen}]"
            )

        tl_lines = []
        for t in result.timeline[:25]:
            tl_lines.append(
                f"- {t.timestamp} | {t.event_type} | {t.description[:200]}"
            )

        actions: list[str] = []
        for r in result.root_causes:
            actions.extend(r.recommended_actions[:2])

        body = f"""## Incident Summary
Automated analysis of **{result.total_lines}** log lines ({result.log_source.value}), **{result.parsed_lines}** structured entries. Error rate **{result.error_rate:.1%}**, warnings **{result.warning_rate:.1%}**, critical events **{result.critical_count}**. Time range: **{tr_s}**.

## Timeline
{chr(10).join(tl_lines) if tl_lines else "- No significant timeline events extracted."}

## Root Cause Analysis
{chr(10).join(rc_lines) if rc_lines else "- No root-cause hypothesis generated."}

## Impact Assessment
Top error signatures: {", ".join(m[:80] for m in result.top_error_messages) or "none"}.
Pipeline processing took **{result.processing_time_ms:.0f} ms** (parser version {result.pipeline_version}).

## Recommended Actions
{chr(10).join(f"- {a}" for a in actions[:6]) if actions else "- Gather metrics and narrow the failing component."}

## Prevention
- Add alerting on error-rate SLOs and dependency health.
- Ensure structured logging with correlation IDs for faster future triage.
- Track deployments against incident windows.
"""
        return body

    def _format_analysis_for_prompt(self, result: AnalysisResult) -> dict:
        tr = result.time_range
        tr_s = f"{tr[0]} → {tr[1]}" if tr[0] or tr[1] else "unknown"

        def rc_block() -> str:
            parts = []
            for r in result.root_causes:
                parts.append(
                    f"[{r.category}|{r.confidence}] {r.hypothesis} "
                    f"(evidence: {'; '.join(r.evidence[:5])})"
                )
            return "\n".join(parts) or "none"

        def an_block() -> str:
            parts = []
            for a in result.anomalies:
                parts.append(
                    f"{a.anomaly_type} ({a.severity}) z={a.z_score:.2f}: {a.description}"
                )
            return "\n".join(parts) or "none detected"

        def cl_block() -> str:
            parts = []
            for c in result.error_clusters:
                parts.append(
                    f"{c.count}x {c.representative_message[:300]} "
                    f"services={c.affected_services}"
                )
            return "\n".join(parts) or "none"

        def tl_block() -> str:
            parts = []
            for t in result.timeline:
                parts.append(f"{t.timestamp} {t.event_type}: {t.description[:400]}")
            return "\n".join(parts) or "none"

        return {
            "log_source": result.log_source.value,
            "time_range": tr_s,
            "total_lines": result.total_lines,
            "error_rate": result.error_rate,
            "root_causes": rc_block(),
            "anomalies": an_block(),
            "error_clusters": cl_block(),
            "timeline": tl_block(),
        }

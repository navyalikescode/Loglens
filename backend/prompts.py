"""Versioned prompts for LogLens report generation."""

from langchain_core.prompts import ChatPromptTemplate

VERSION = "v1.0"

INCIDENT_REPORT_SYSTEM = """You are a senior Site Reliability Engineer writing an incident report.
You receive structured analysis data from an automated log analysis system.
Your job is to write a clear, actionable incident report.

Rules:
- Write for a technical audience (engineers, on-call responders)
- Be specific — reference actual error messages, timestamps, and counts from the data
- Do not invent information not present in the data
- Use clear severity language: P1 (Critical), P2 (High), P3 (Medium), P4 (Low)
- Keep the report under 500 words
- Format as clean Markdown with headers"""

INCIDENT_REPORT_HUMAN = """Write an incident report based on this analysis:

LOG SOURCE: {log_source}
TIME RANGE: {time_range}
TOTAL LINES ANALYSED: {total_lines}
ERROR RATE: {error_rate:.1%}

ROOT CAUSE HYPOTHESES:
{root_causes}

KEY ANOMALIES DETECTED:
{anomalies}

ERROR CLUSTERS (grouped similar errors):
{error_clusters}

TIMELINE OF SIGNIFICANT EVENTS:
{timeline}

Write the incident report with these sections:
## Incident Summary
## Timeline
## Root Cause Analysis
## Impact Assessment
## Recommended Actions
## Prevention"""

INCIDENT_REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", INCIDENT_REPORT_SYSTEM),
        ("human", INCIDENT_REPORT_HUMAN),
    ]
)

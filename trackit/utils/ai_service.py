"""AI Service — dynamic provider (Groq / OpenAI) based on environment variables."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """
You are a Jira project health analyzer. Generate a SHORT, SHARP, ACTIONABLE summary for the team lead — NOT for the assignees.

DATA SCHEMA — read this before analyzing:
- "Pending From" column values:
    - "Nd"  → ticket has been open for exactly N days (e.g. "5d" = stale for 5 days). ONLY flag these.
    - "—"   → ticket age is ≤ 2 days. This is NORMAL. Do NOT call it stale or mention any age for it.
- "AWAITING UPDATES" section: assignees who did NOT submit any update today — compliance failure.
- "RESOLVED/MOVED" section: tickets closed today — positive signal, no action needed.
- Compliance % = percentage of active ticket owners who submitted updates.

CRITICAL ACCURACY RULES (violations are worse than saying nothing):
- NEVER invent or infer a number of days for a ticket unless the Pending From cell shows an explicit "Nd" value.
- NEVER call a ticket stale if its Pending From cell shows "—".
- NEVER state a percentage, count, or ticket ID that does not literally appear in the report text below.
- If every Pending From value is "—", do NOT mention staleness at all.
- Do NOT repeat data already visible as a metric in the OVERVIEW section (total, updated, pending, compliance %).

WHAT TO LOOK FOR (in priority order):
1. Assignees missing updates (AWAITING UPDATES section) — name them only if actionable.
2. Tickets with explicit Nd in Pending From (stale ≥ 4d) — name ticket IDs and exact days.
3. One assignee holding >50% of all active tickets — workload risk.
4. Compliance < 50% — critical risk (but don't restate the exact % if already in overview).

STRICT OUTPUT RULES:
- Maximum 4 bullet points. Fewer is better if there is nothing real to say.
- Each bullet: one crisp, factual sentence under 15 words.
- Start the header line with: 🧠 AI RISK SUMMARY
- Each bullet on its OWN line starting with •
- No intro, no outro, no explanations.

BANNED PHRASES: "unknown dates", "as seen in", "the report shows", "team is", "making progress", "work is ongoing", "pending from unknown"

If nothing actionable exists output exactly:
🧠 AI RISK SUMMARY
• No significant risks detected today.

Analyze the following Jira report:

{REPORT_DATA}
"""


class AIService:
    """Dynamic AI client — auto-selects Groq or OpenAI based on available env vars."""

    _GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    _OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    _GROQ_DEFAULT_MODEL = "llama-3.1-8b-instant"
    _OPENAI_DEFAULT_MODEL = "gpt-4o-mini"

    @classmethod
    def _get_provider(cls):
        """
        Detect configured provider from environment variables.

        Priority: GROQ > OpenAI
        Env vars:
            GROQ_API_KEY    — use Groq (llama-3.1-8b-instant by default)
            OPENAI_API_KEY  — use OpenAI (gpt-4o-mini by default)
            AI_MODEL        — optional model override for either provider

        Returns:
            (provider_name, api_key, model, api_url) tuple, or None if unconfigured.
        """
        model_override = os.environ.get("AI_MODEL", "").strip()

        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if groq_key:
            return ("groq", groq_key, model_override or cls._GROQ_DEFAULT_MODEL, cls._GROQ_API_URL)

        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            return ("openai", openai_key, model_override or cls._OPENAI_DEFAULT_MODEL, cls._OPENAI_API_URL)

        return None

    @classmethod
    def summarize(cls, markdown_report: str) -> str:
        """
        Send *markdown_report* to the configured LLM and return the AI summary.

        Returns:
            AI summary string, or None if no provider is configured or the call fails.
        """
        provider_info = cls._get_provider()
        if provider_info is None:
            logger.info("No AI provider configured (set GROQ_API_KEY or OPENAI_API_KEY), skipping summary.")
            return None

        provider, api_key, model, api_url = provider_info
        logger.info(f"Generating AI summary via {provider} ({model})")

        prompt = _SYSTEM_PROMPT_TEMPLATE.replace("{REPORT_DATA}", markdown_report)

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            summary = response.json()["choices"][0]["message"]["content"].strip()
            logger.info(f"AI summary generated successfully via {provider}")
            return summary
        except requests.exceptions.Timeout:
            logger.error(f"AI summary timed out ({provider})")
        except requests.exceptions.HTTPError as e:
            logger.error(f"AI API HTTP error ({provider}): {e.response.status_code} {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"AI summary failed ({provider}): {e}")

        return None
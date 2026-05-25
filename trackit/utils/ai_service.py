"""AI Service — dynamic provider (Groq / OpenAI) based on environment variables."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """
You are a Jira project health analyzer. Generate a SHORT, SHARP, ACTIONABLE summary for the team lead.

You will receive the OVERVIEW and section summaries only — NOT the full ticket table.

DATA AVAILABLE:
- OVERVIEW: total tickets, updates given, no-update count, new/resolved counts, compliance %
- AWAITING UPDATES: assignees who did NOT submit any update today
- RESOLVED/MOVED: tickets closed or moved out today

WHAT TO ANALYSE:
1. Assignees with no update (AWAITING UPDATES) — flag if many or key people missing
2. Compliance % — flag if below 50%
3. Workload imbalance — if one assignee has significantly more tickets than others
4. High new-ticket volume — if new today count is unusually high

DO NOT mention staleness, Pending From, or ticket ages — that data is not in the input.
DO NOT invent numbers. Only use counts that appear in the report.
DO NOT repeat the overview metrics verbatim.

STRICT OUTPUT RULES:
- Maximum 4 bullet points. Fewer is better.
- Each bullet: one crisp sentence under 20 words.
- Start with header: 🧠 AI RISK SUMMARY
- Each bullet on its own line starting with •
- No intro, no outro.

If nothing actionable exists output exactly:
🧠 AI RISK SUMMARY
• No significant risks detected today.

Analyze the following report:

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
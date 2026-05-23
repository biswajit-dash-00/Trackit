"""AI Service — dynamic provider (Groq / OpenAI) based on environment variables."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """
You are a Jira project health analyzer. Generate a SHORT, SHARP, ACTIONABLE summary for the team lead — NOT for the assignees.

DATA SCHEMA — read this before analyzing:
- "Pending From" column: each cell is either "Nd" (e.g. "3d", "7d") or "—".
  - "—" means age ≤ 2 days. NORMAL. Do not mention.
  - "2d" = 2 days old. NORMAL. Do not mention.
  - Only flag "Nd" where N ≥ 3. These are genuinely stale.
- "AWAITING UPDATES" section: assignees who did NOT submit any update today.
- Compliance % = percentage of active ticket owners who submitted updates.

STALENESS RULES — read carefully before writing anything about age:
- Scan the Pending From column. Collect ONLY the distinct values where N ≥ 3.
- If NO cell has N ≥ 3, do NOT write any staleness bullet at all.
- If stale tickets exist, write EXACTLY ONE bullet. Count how many tickets share each Nd value from the table and state it (e.g. "12 tickets at 3d, 5 at 7d").
- NEVER write a day-count that does not literally appear in the Pending From column of the report below.
- NEVER invent, estimate, or extrapolate any number of days.

OTHER ACCURACY RULES:
- NEVER state any count, percentage, or ticket ID that does not literally appear in the report below.
- Do NOT repeat data already in the OVERVIEW section.

STRICT OUTPUT RULES:
- Maximum 5 bullet points. Fewer is better.
- Each bullet: one crisp sentence under 20 words.
- Start header with: 🧠 AI RISK SUMMARY
- Each bullet on its own line starting with •
- No intro, no outro, no explanations.

BANNED: listing ticket IDs, one bullet per ticket, day values not in the table, multiple staleness bullets.

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
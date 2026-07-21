import logging

from mistralai import Mistral

from app.config import MISTRAL_API_KEY

logger = logging.getLogger("govt_monitor.summarizer")

SYSTEM_PROMPT = """You are a news-desk assistant for a government/regulatory monitoring tool.
You will be given a list of newly published item titles from a government website
(circulars, notifications, announcements, exposure drafts, etc).

For EACH item, write ONE short plain-English sentence (max 25 words) explaining
what it likely means for someone tracking regulatory/compliance updates.
Do not invent facts not implied by the title. If a title is already self-explanatory,
you can lightly rephrase it for clarity rather than inventing new information.

Respond with exactly one line per item, in the same order as given, with no numbering,
no markdown, and no extra commentary.
"""


def summarize_new_items(site_name: str, items: list) -> list:
    """
    Given a list of {"title": ..., "url": ...} new items, returns a list of
    one-line plain-English blurbs, same length and order as `items`.
    Falls back to using the raw title if no Mistral API key is configured
    or if the API call fails.
    """
    if not items:
        return []

    if not MISTRAL_API_KEY:
        return [it["title"] for it in items]

    titles_block = "\n".join(f"{idx + 1}. {it['title']}" for idx, it in enumerate(items))

    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Site: {site_name}\n\nNew item titles:\n{titles_block}"},
            ],
            temperature=0.3,
        )
        lines = [
            line.strip("-• \t")
            for line in response.choices[0].message.content.strip().split("\n")
            if line.strip()
        ]

        if len(lines) == len(items):
            return lines

        logger.warning(
            f"[{site_name}] Mistral returned {len(lines)} lines for {len(items)} items - "
            "falling back to raw titles for safety."
        )
        return [it["title"] for it in items]

    except Exception as e:
        logger.error(f"[{site_name}] Mistral summarization failed: {e}")
        return [it["title"] for it in items]

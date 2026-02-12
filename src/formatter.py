"""Format the bot reply (who, when, summary, link)."""
from datetime import datetime


def format_reply(
    answerer_name: str,
    answer_time: datetime | str,
    answer_summary: str,
    thread_link: str,
) -> str:
    """Build the bot reply text as specified in the MVP."""
    if isinstance(answer_time, str):
        date_str = answer_time
    else:
        date_str = answer_time.strftime("%b %d")  # e.g. Jan 12
    lines = [
        f"This question was answered before by **{answerer_name}** on {date_str}.",
        "",
        "Here's the summary:",
        "———",
        f"_{answer_summary}_",
        "———",
        f"View original thread ↗",
    ]
    # Lark text messages: link can be in same line or separate. We output plain text;
    # if we switch to interactive card we can add url for "View original thread".
    if thread_link:
        lines[-1] = f"View original thread ↗ {thread_link}"
    return "\n".join(lines)

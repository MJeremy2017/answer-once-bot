"""Format the bot reply (who, when, summary, link)."""
from datetime import datetime


def _date_str(answer_time: datetime | str) -> str:
    if isinstance(answer_time, str):
        return answer_time
    return answer_time.strftime("%b %d")


def format_reply(
    answerer_name: str,
    answer_time: datetime | str,
    answer_summary: str,
    thread_link: str,
    *,
    source_links: list[str] | None = None,
) -> str:
    """Build the bot reply as plain text (fallback when post not used)."""
    date_str = _date_str(answer_time)
    lines = [
        f"This question was answered before by {answerer_name} on {date_str}.",
        "",
        "Here's the summary:",
        answer_summary,
        f"View original thread: {thread_link}" if thread_link else "View original thread",
    ]
    if source_links:
        lines.append("")
        lines.append("Sources: " + ", ".join(source_links))
    return "\n".join(lines)


def build_post_content(
    answer_time: datetime | str,
    answer_summary: str,
    thread_link: str,
    answerer_open_id: str | None,
    *,
    source_links: list[str] | None = None,
) -> dict:
    """Build Lark post message content (rich text with @mention and link)."""
    date_str = _date_str(answer_time)
    line1 = [{"tag": "text", "text": "This question was answered before by "}]
    if answerer_open_id:
        line1.append({"tag": "at", "user_id": answerer_open_id})
        line1.append({"tag": "text", "text": f" on {date_str}."})
    else:
        line1.append({"tag": "text", "text": f"someone on {date_str}."})
    content = [
        line1,
        [{"tag": "text", "text": ""}],
        [{"tag": "text", "text": "Here's the summary:"}],
        [{"tag": "text", "text": answer_summary}],
    ]
    if thread_link:
        content.append([{"tag": "a", "text": "View original thread", "href": thread_link}])
    if source_links:
        source_line = [{"tag": "text", "text": "Sources: "}]
        for i, href in enumerate(source_links, 1):
            if i > 1:
                source_line.append({"tag": "text", "text": ", "})
            source_line.append({"tag": "a", "text": f"Thread {i}", "href": href})
        content.append([{"tag": "text", "text": ""}])
        content.append(source_line)
    return {"zh_cn": {"content": content, "title": ""}, "en_us": {"content": content, "title": ""}}

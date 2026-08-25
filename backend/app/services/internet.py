import asyncio
import html
import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
STACK_EXCHANGE_API = "https://api.stackexchange.com/2.3"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"
LEVER_API = "https://api.lever.co/v0/postings"


def _json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "JobFlowAI/1.0 (+local portfolio project)"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def plain_text(value: str) -> str:
    value = html.unescape(html.unescape(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


async def discover_jobs(skills: list[str], roles: list[str], pages: int = 2) -> list[dict]:
    payloads = await asyncio.gather(*[
        asyncio.to_thread(_json, f"{ARBEITNOW_API}?{urlencode({'page': page})}")
        for page in range(1, pages + 1)
    ])
    terms = [term.lower() for term in [*skills, *roles] if len(term.strip()) > 1]
    ranked = []
    for payload in payloads:
        for item in payload.get("data", []):
            description = plain_text(item.get("description", ""))
            haystack = " ".join([
                item.get("title", ""), description, " ".join(item.get("tags") or []),
            ]).lower()
            matched = [term for term in terms if term in haystack]
            if matched:
                ranked.append((len(set(matched)), item, description))
    ranked.sort(key=lambda row: (row[0], row[1].get("created_at", 0)), reverse=True)
    seen = set()
    results = []
    for _, item, description in ranked:
        slug = str(item.get("slug", ""))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        results.append({**item, "description_text": description})
        if len(results) == 20:
            break
    return results


async def fetch_portal_job(value: str) -> dict:
    """Fetch a posting through a documented public Greenhouse or Lever API."""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        if len(parts) < 3 or parts[-2] != "jobs":
            raise ValueError("Greenhouse URL must identify a public job")
        board, job_id = parts[0], parts[-1]
        payload = await asyncio.to_thread(_json, f"{GREENHOUSE_API}/{board}/jobs/{job_id}?content=true")
        description = plain_text(payload.get("content", ""))
        return {
            "external_id": f"greenhouse:{board}:{job_id}",
            "title": payload.get("title") or "Untitled role",
            "company_name": board.replace("-", " ").title(),
            "location": (payload.get("location") or {}).get("name") or "Unspecified",
            "description_text": description,
            "application_url": payload.get("absolute_url") or value,
            "source": "Greenhouse public Job Board API",
            "posted_at": payload.get("updated_at"),
        }
    if host == "jobs.lever.co":
        if len(parts) < 2:
            raise ValueError("Lever URL must identify a public job")
        company, posting_id = parts[0], parts[1]
        payload = await asyncio.to_thread(_json, f"{LEVER_API}/{company}/{posting_id}")
        description = plain_text(payload.get("descriptionPlain") or payload.get("description", ""))
        return {
            "external_id": f"lever:{company}:{posting_id}",
            "title": payload.get("text") or "Untitled role",
            "company_name": company.replace("-", " ").title(),
            "location": (payload.get("categories") or {}).get("location") or "Unspecified",
            "description_text": description,
            # Open the actual form so the companion can fill it immediately.
            "application_url": payload.get("applyUrl") or payload.get("hostedUrl") or value,
            "source": "Lever public Postings API",
            "posted_at": payload.get("createdAt"),
        }
    raise ValueError("Only public Greenhouse and Lever posting URLs are supported")


async def sourced_interview_questions(skills: list[str], title: str) -> list[dict]:
    title_terms = [term for term in re.findall(r"[A-Za-z][A-Za-z+#.]{2,}", title) if term.lower() not in {"senior", "junior", "working", "student", "developer", "engineer"}]
    topics = list(dict.fromkeys(skills or title_terms))[:5]
    searches = await asyncio.gather(*[
        asyncio.to_thread(_json, f"{STACK_EXCHANGE_API}/search/advanced?" + urlencode({
            "site": "stackoverflow", "pagesize": 2, "order": "desc", "sort": "votes",
            "accepted": "True", "title": topic,
        }))
        for topic in topics
    ], return_exceptions=True)
    questions = []
    seen = set()
    for topic, search in zip(topics, searches, strict=True):
        if isinstance(search, Exception):
            continue
        for item in search.get("items", []):
            answer_id = item.get("accepted_answer_id")
            if answer_id and answer_id not in seen:
                seen.add(answer_id)
                questions.append((topic, item))
    if not questions:
        return []
    answer_ids = ";".join(str(item["accepted_answer_id"]) for _, item in questions[:8])
    answers = await asyncio.to_thread(_json, f"{STACK_EXCHANGE_API}/answers/{answer_ids}?" + urlencode({
        "site": "stackoverflow", "filter": "withbody",
    }))
    bodies = {item["answer_id"]: plain_text(item.get("body", "")) for item in answers.get("items", [])}
    output = []
    for topic, question in questions:
        answer = bodies.get(question["accepted_answer_id"], "")
        if not answer:
            continue
        output.append({
            "skill": topic,
            "question": plain_text(question.get("title", "")),
            "answer": answer[:1200] + ("…" if len(answer) > 1200 else ""),
            "source": "Stack Overflow (accepted community answer)",
            "source_url": question.get("link", ""),
        })
        if len(output) == 6:
            break
    return output

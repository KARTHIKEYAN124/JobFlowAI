import asyncio
import html
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"
REMOTE_OK_API = "https://remoteok.com/api"
STACK_EXCHANGE_API = "https://api.stackexchange.com/2.3"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"
LEVER_API = "https://api.lever.co/v0/postings"
ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board"
SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies"


def _json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "JobFlowAI/1.0 (+local portfolio project)"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def plain_text(value: str) -> str:
    value = html.unescape(html.unescape(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


async def discover_jobs(skills: list[str], roles: list[str], pages: int = 2) -> list[dict]:
    requests = [
        *(
            asyncio.to_thread(_json, f"{ARBEITNOW_API}?{urlencode({'page': page})}")
            for page in range(1, pages + 1)
        ),
        asyncio.to_thread(_json, f"{REMOTIVE_API}?limit=100"),
        asyncio.to_thread(_json, REMOTE_OK_API),
    ]
    payloads = await asyncio.gather(*requests, return_exceptions=True)
    terms = [term.lower() for term in [*skills, *roles] if len(term.strip()) > 1]
    ranked = []
    normalized = []
    for payload in payloads[:pages]:
        if isinstance(payload, Exception):
            continue
        normalized.extend({**item, "source": "Arbeitnow public API"} for item in payload.get("data", []))
    remotive = payloads[pages]
    if not isinstance(remotive, Exception):
        normalized.extend(
            {
                "slug": f"remotive-{item.get('id')}",
                "title": item.get("title"),
                "company_name": item.get("company_name"),
                "location": item.get("candidate_required_location"),
                "description": item.get("description"),
                "tags": item.get("tags") or [],
                "created_at": _timestamp(item.get("publication_date")),
                "remote": True,
                "url": item.get("url"),
                "job_types": [item.get("job_type") or "unspecified"],
                "source": "Remotive public API",
            }
            for item in remotive.get("jobs", [])
        )
    remote_ok = payloads[pages + 1]
    if not isinstance(remote_ok, Exception) and isinstance(remote_ok, list):
        normalized.extend(
            {
                "slug": f"remoteok-{item.get('id') or item.get('slug')}",
                "title": item.get("position"),
                "company_name": item.get("company"),
                "location": item.get("location") or "Remote",
                "description": item.get("description"),
                "tags": item.get("tags") or [],
                "created_at": _timestamp(item.get("date") or item.get("epoch")),
                "remote": True,
                "url": item.get("url"),
                "job_types": ["remote"],
                "source": "Remote OK public API",
            }
            for item in remote_ok
            if isinstance(item, dict) and item.get("position")
        )
    for item in normalized:
        description = plain_text(item.get("description", ""))
        haystack = " ".join(
            [
                item.get("title", ""),
                description,
                " ".join(item.get("tags") or []),
            ]
        ).lower()
        matched = [term for term in terms if term in haystack]
        if matched:
            ranked.append((len(set(matched)), item, description))
    ranked.sort(key=lambda row: (row[0], row[1].get("created_at", 0)), reverse=True)
    by_source: dict[str, list[tuple[int, dict, str]]] = {}
    for row in ranked:
        by_source.setdefault(row[1].get("source") or "Public job feed", []).append(row)
    seen = set()
    results = []
    while by_source and len(results) < 20:
        for source in list(by_source):
            if not by_source[source]:
                del by_source[source]
                continue
            _, item, description = by_source[source].pop(0)
            slug = str(item.get("slug", ""))
            if slug and slug not in seen:
                seen.add(slug)
                results.append({**item, "description_text": description})
                if len(results) == 20:
                    break
    return results


def _timestamp(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value / 1000 if value > 10_000_000_000 else value)
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value).timestamp())
        except ValueError:
            return 0
    return 0


async def fetch_portal_job(value: str) -> dict:
    """Fetch a posting through a supported public applicant-tracking API."""
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
            "application_url": f"https://job-boards.greenhouse.io/{board}/jobs/{job_id}",
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
    if host == "jobs.ashbyhq.com":
        if len(parts) < 2:
            raise ValueError("Ashby URL must identify a public job")
        board, job_id = parts[0], parts[1]
        payload = await asyncio.to_thread(_json, f"{ASHBY_API}/{board}")
        posting = next((item for item in payload.get("jobs", []) if str(item.get("id")) == job_id), None)
        if not posting:
            raise ValueError("Ashby job was not found on the public board")
        return {
            "external_id": f"ashby:{board}:{job_id}",
            "title": posting.get("title") or "Untitled role",
            "company_name": board.replace("-", " ").title(),
            "location": posting.get("location") or "Unspecified",
            "description_text": plain_text(
                posting.get("descriptionHtml") or posting.get("descriptionPlain", "")
            ),
            "application_url": posting.get("applyUrl") or posting.get("jobUrl") or value,
            "source": "Ashby public Job Board API",
            "posted_at": posting.get("publishedAt"),
        }
    if host == "jobs.smartrecruiters.com":
        if len(parts) < 2:
            raise ValueError("SmartRecruiters URL must identify a public job")
        company, posting_id = parts[0], parts[1].split("-", 1)[0]
        payload = await asyncio.to_thread(_json, f"{SMARTRECRUITERS_API}/{company}/postings/{posting_id}")
        sections = ((payload.get("jobAd") or {}).get("sections") or {}).values()
        description = plain_text(" ".join((section or {}).get("text", "") for section in sections))
        return {
            "external_id": f"smartrecruiters:{company}:{posting_id}",
            "title": payload.get("name") or "Untitled role",
            "company_name": (payload.get("company") or {}).get("name") or company.replace("-", " ").title(),
            "location": (payload.get("location") or {}).get("fullLocation") or "Unspecified",
            "description_text": description,
            "application_url": value,
            "source": "SmartRecruiters public Posting API",
            "posted_at": payload.get("releasedDate"),
        }
    raise ValueError("Supported public portals: Greenhouse, Lever, Ashby, and SmartRecruiters")


async def fetch_application_questions(external_id: str) -> dict:
    """Return only questions exposed by a supported ATS public application schema."""
    if not external_id.startswith("greenhouse:"):
        return {
            "questions": [],
            "source": "employer portal at launch",
            "note": "This ATS does not expose application questions publicly. The companion will read the real rendered form and ask them before filling.",
        }
    _, board, job_id = external_id.split(":", 2)
    payload = await asyncio.to_thread(
        _json, f"{GREENHOUSE_API}/{board}/jobs/{job_id}?content=true&questions=true"
    )
    standard = re.compile(
        r"first.?name|last.?name|full.?name|email|phone|resume|cover.?letter", re.IGNORECASE
    )
    questions = []
    for question_index, question in enumerate(payload.get("questions") or []):
        label = plain_text(question.get("label") or f"Application question {question_index + 1}")
        for field_index, field in enumerate(question.get("fields") or [{}]):
            name = str(field.get("name") or f"question_{question_index + 1}_{field_index + 1}")
            if standard.search(f"{name} {label}"):
                continue
            values = field.get("values") or []
            options = [
                plain_text(str(value.get("label") or value.get("name") or value.get("value") or ""))
                if isinstance(value, dict)
                else plain_text(str(value))
                for value in values
            ]
            questions.append(
                {
                    "key": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:150],
                    "label": label,
                    "required": bool(question.get("required")),
                    "type": str(field.get("type") or "input_text"),
                    "options": [option for option in options if option],
                }
            )
    return {
        "questions": questions,
        "source": "Greenhouse public application schema",
        "note": "These questions came from the employer's current Greenhouse application configuration.",
    }


async def sourced_interview_questions(skills: list[str], title: str) -> list[dict]:
    title_terms = [
        term
        for term in re.findall(r"[A-Za-z][A-Za-z+#.]{2,}", title)
        if term.lower() not in {"senior", "junior", "working", "student", "developer", "engineer"}
    ]
    topics = list(dict.fromkeys(skills or title_terms))[:5]
    searches = await asyncio.gather(
        *[
            asyncio.to_thread(
                _json,
                f"{STACK_EXCHANGE_API}/search/advanced?"
                + urlencode(
                    {
                        "site": "stackoverflow",
                        "pagesize": 2,
                        "order": "desc",
                        "sort": "votes",
                        "accepted": "True",
                        "title": topic,
                    }
                ),
            )
            for topic in topics
        ],
        return_exceptions=True,
    )
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
    answers = await asyncio.to_thread(
        _json,
        f"{STACK_EXCHANGE_API}/answers/{answer_ids}?"
        + urlencode(
            {
                "site": "stackoverflow",
                "filter": "withbody",
            }
        ),
    )
    bodies = {item["answer_id"]: plain_text(item.get("body", "")) for item in answers.get("items", [])}
    output = []
    for topic, question in questions:
        answer = bodies.get(question["accepted_answer_id"], "")
        if not answer:
            continue
        output.append(
            {
                "skill": topic,
                "question": plain_text(question.get("title", "")),
                "answer": answer[:1200] + ("…" if len(answer) > 1200 else ""),
                "source": "Stack Overflow (accepted community answer)",
                "source_url": question.get("link", ""),
            }
        )
        if len(output) == 6:
            break
    return output

import pytest

from app.services import internet
from app.services.internet import discover_jobs, fetch_application_questions, fetch_portal_job, plain_text


def test_plain_text_decodes_and_removes_job_feed_markup():
    assert plain_text("&lt;p&gt;Python &amp;amp; FastAPI&lt;/p&gt;") == "Python & FastAPI"


@pytest.mark.asyncio
async def test_fetch_greenhouse_job_uses_public_api(monkeypatch):
    monkeypatch.setattr(internet,"_json",lambda url:{"title":"Backend Engineer","content":"<p>Python and FastAPI</p>","location":{"name":"Berlin"},"absolute_url":"https://job-boards.greenhouse.io/acme/jobs/123","updated_at":"2026-08-25T10:00:00Z"})
    result=await fetch_portal_job("https://job-boards.greenhouse.io/acme/jobs/123")
    assert result["source"]=="Greenhouse public Job Board API"
    assert result["description_text"]=="Python and FastAPI"
    assert result["application_url"]=="https://job-boards.greenhouse.io/acme/jobs/123"


@pytest.mark.asyncio
async def test_fetch_lever_job_uses_public_api(monkeypatch):
    monkeypatch.setattr(internet,"_json",lambda url:{"text":"AI Engineer","descriptionPlain":"Build Python systems","categories":{"location":"Remote"},"hostedUrl":"https://jobs.lever.co/acme/abc","createdAt":1787652000000})
    result=await fetch_portal_job("https://jobs.lever.co/acme/abc")
    assert result["source"]=="Lever public Postings API"
    assert result["location"]=="Remote"


@pytest.mark.asyncio
async def test_fetch_ashby_job_uses_public_api(monkeypatch):
    monkeypatch.setattr(internet,"_json",lambda url:{"jobs":[{"id":"job-123","title":"Platform Engineer","descriptionHtml":"<p>Python infrastructure</p>","location":"Berlin","applyUrl":"https://jobs.ashbyhq.com/acme/job-123/application","publishedAt":"2026-08-25T10:00:00Z"}]})
    result=await fetch_portal_job("https://jobs.ashbyhq.com/acme/job-123")
    assert result["source"]=="Ashby public Job Board API"
    assert result["description_text"]=="Python infrastructure"


@pytest.mark.asyncio
async def test_fetch_smartrecruiters_job_uses_public_api(monkeypatch):
    monkeypatch.setattr(internet,"_json",lambda url:{"id":"123","name":"AI Engineer","company":{"name":"Acme"},"location":{"fullLocation":"Remote"},"releasedDate":"2026-08-25T10:00:00Z","jobAd":{"sections":{"description":{"text":"<p>Python and FastAPI</p>"}}}})
    result=await fetch_portal_job("https://jobs.smartrecruiters.com/Acme/123-ai-engineer")
    assert result["source"]=="SmartRecruiters public Posting API"
    assert result["company_name"]=="Acme"


@pytest.mark.asyncio
async def test_discover_jobs_aggregates_multiple_public_feeds(monkeypatch):
    def fake_json(url):
        if "arbeitnow" in url: return {"data":[{"slug":"arbeit-1","title":"Python Engineer","description":"Python APIs","created_at":100,"url":"https://example.com/a"}]}
        if "remotive" in url: return {"jobs":[{"id":2,"title":"Remote Python Engineer","description":"Python backend","publication_date":"2026-08-25T10:00:00Z","url":"https://example.com/b"}]}
        return [{"id":"3","position":"Python Developer","description":"Python services","date":"2026-08-25T10:00:00Z","url":"https://example.com/c"}]
    monkeypatch.setattr(internet,"_json",fake_json)
    results=await discover_jobs(["Python"],[],pages=1)
    assert {item["source"] for item in results}=={"Arbeitnow public API","Remotive public API","Remote OK public API"}


@pytest.mark.asyncio
async def test_fetch_portal_job_rejects_unknown_hosts():
    with pytest.raises(ValueError,match="Supported public portals"):
        await fetch_portal_job("https://example.com/jobs/123")


@pytest.mark.asyncio
async def test_greenhouse_application_questions_come_from_public_schema(monkeypatch):
    monkeypatch.setattr(internet,"_json",lambda url:{"questions":[
        {"label":"Email","required":True,"fields":[{"name":"email","type":"input_text","values":[]}]},
        {"label":"Will you need sponsorship?","required":True,"fields":[{"name":"question_1","type":"multi_value_single_select","values":[{"label":"Yes"},{"label":"No"}]}]},
    ]})
    result=await fetch_application_questions("greenhouse:acme:123")
    assert result["source"]=="Greenhouse public application schema"
    assert result["questions"]==[{"key":"question_1","label":"Will you need sponsorship?","required":True,"type":"multi_value_single_select","options":["Yes","No"]}]


@pytest.mark.asyncio
async def test_non_public_question_schema_defers_to_live_portal():
    result=await fetch_application_questions("lever:acme:123")
    assert result["questions"]==[]
    assert result["source"]=="employer portal at launch"

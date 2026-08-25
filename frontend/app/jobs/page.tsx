"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link2, LoaderCircle, RefreshCw, Search } from "lucide-react";
import { JobRow, type Job as JobView } from "@/components/job-row";
import { PageHeading } from "@/components/page-heading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

type ApiJob = { id: string; title: string; company_name: string; location: string; remote_type: string; category: string; posted_at: string; required_skills: string[]; preferred_skills: string[] };
type Match = { job_id: string; overall_score: number; matched_skills: string[]; missing_skills: string[] };
type Scan = { source: string; found: number; imported: number; matched: number };

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [query, setQuery] = useState("");
  const [minimum, setMinimum] = useState(0);
  const [location, setLocation] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [portalUrl, setPortalUrl] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [records, matches] = await Promise.all([api<ApiJob[]>("/jobs?limit=100"), api<Match[]>("/matches")]);
      const matchByJob = new Map(matches.map(match => [match.job_id, match]));
      setJobs(records.map(record => {
        const match = matchByJob.get(record.id);
        return { id: record.id, title: record.title, company: record.company_name, location: `${record.location} · ${record.remote_type}`, score: Math.round(match?.overall_score ?? 0), skills: match?.matched_skills.length ? match.matched_skills : record.required_skills, missing: match?.missing_skills ?? [], posted: new Date(record.posted_at).toLocaleDateString(), category: record.category };
      }));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load jobs."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { setQuery(new URLSearchParams(window.location.search).get("q") ?? ""); void load(); }, [load]);

  async function scan() {
    setScanning(true); setError(""); setMessage("");
    try {
      const result = await api<Scan>("/jobs/scan", { method: "POST" });
      setMessage(`Scanned ${result.source}: ${result.found} skill-related jobs found, ${result.imported} newly imported.`);
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not scan public job feeds."); }
    finally { setScanning(false); }
  }

  async function importPortalJob() {
    if (!portalUrl.trim()) return;
    setImporting(true); setError(""); setMessage("");
    try {
      const imported = await api<ApiJob>("/jobs/import-url", { method: "POST", body: JSON.stringify({ url: portalUrl.trim() }) });
      setMessage(`Imported ${imported.title} from its public job portal and calculated your match.`);
      setPortalUrl(""); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not import this portal job."); }
    finally { setImporting(false); }
  }

  const filtered = useMemo(() => jobs.filter(job => job.score >= minimum && (!location || job.location.toLowerCase().includes(location)) && (!category || job.category === category) && `${job.title} ${job.company} ${job.skills.join(" ")}`.toLowerCase().includes(query.toLowerCase())), [jobs, query, minimum, location, category]);
  return <>
    <PageHeading title="Jobs" description="Fresh, deduplicated opportunities from approved public sources." actions={<Button variant="outline" onClick={scan} disabled={scanning}>{scanning ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}{scanning ? "Scanning internet…" : "Scan public jobs"}</Button>} />
    {error ? <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p> : null}
    {message ? <p className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status">{message}</p> : null}
    <Card className="mb-6"><CardHeader><CardTitle>Import a real portal job</CardTitle></CardHeader><CardContent><div className="flex flex-col gap-3 md:flex-row"><Input type="url" value={portalUrl} onChange={event => setPortalUrl(event.target.value)} placeholder="Paste a public Greenhouse or Lever job URL" aria-label="Public job portal URL" /><Button type="button" onClick={importPortalJob} disabled={importing || !portalUrl.trim()}>{importing ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Link2 data-icon="inline-start" />}{importing ? "Importing…" : "Fetch job details"}</Button></div><p className="mt-3 text-xs text-muted-foreground">JobFlow uses documented public Greenhouse and Lever APIs and keeps the employer&apos;s original application URL.</p></CardContent></Card>
    <Card><CardHeader><CardTitle>{loading ? "Loading opportunities…" : `${filtered.length} opportunities`}</CardTitle><div className="mt-4 grid gap-3 md:grid-cols-[1fr_repeat(3,180px)]"><div className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input className="pl-9" placeholder="Role, company, technology…" value={query} onChange={event => setQuery(event.target.value)} /></div><select className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Location" value={location} onChange={event => setLocation(event.target.value)}><option value="">All locations</option><option value="berlin">Berlin</option><option value="remote">Remote</option></select><select className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Role" value={category} onChange={event => setCategory(event.target.value)}><option value="">All roles</option><option value="BACKEND">Backend</option><option value="AI">AI</option><option value="CLOUD">Cloud</option><option value="FULLSTACK">Full stack</option></select><select className="h-10 rounded-md border bg-background px-3 text-sm" aria-label="Minimum match" value={minimum} onChange={event => setMinimum(Number(event.target.value))}><option value="0">Any match</option><option value="65">65% and above</option><option value="80">80% and above</option></select></div></CardHeader><CardContent>{loading ? <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading jobs…</div> : filtered.length ? filtered.map(job => <JobRow key={job.id} job={job} />) : <p className="py-10 text-center text-sm text-muted-foreground">No jobs match these filters. Upload your resume or run a public job scan.</p>}</CardContent></Card>
  </>;
}

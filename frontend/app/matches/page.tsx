"use client";

import { useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { JobRow, type Job as JobView } from "@/components/job-row";
import { PageHeading } from "@/components/page-heading";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type ApiJob = { id: string; title: string; company_name: string; location: string; remote_type: string; category: string; posted_at: string; required_skills: string[] };
type Match = { job_id: string; overall_score: number; matched_skills: string[]; missing_skills: string[] };

export default function MatchesPage() {
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<ApiJob[]>("/jobs?limit=100"), api<Match[]>("/matches")])
      .then(([records, matches]) => {
        const byJob = new Map(records.map(job => [job.id, job]));
        setJobs(matches.flatMap(match => {
          const job = byJob.get(match.job_id);
          return job ? [{ id: job.id, title: job.title, company: job.company_name, location: `${job.location} · ${job.remote_type}`, score: Math.round(match.overall_score), skills: match.matched_skills.length ? match.matched_skills : job.required_skills, missing: match.missing_skills, posted: new Date(job.posted_at).toLocaleDateString(), category: job.category }] : [];
        }));
      })
      .catch(caught => setError(caught instanceof Error ? caught.message : "Could not load matches."))
      .finally(() => setLoading(false));
  }, []);

  return <><PageHeading title="Matches" description="Explainable rankings based on your current profile and live jobs."/><Card><CardHeader><CardTitle>Ranked matches</CardTitle><CardDescription>Scores are calculated from stored profile and job data.</CardDescription></CardHeader><CardContent>{error ? <p className="py-8 text-sm text-destructive" role="alert">{error}</p> : loading ? <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin"/>Loading matches…</p> : jobs.length ? jobs.map(job => <JobRow key={job.id} job={job}/>) : <p className="py-8 text-sm text-muted-foreground">No current matches. Upload a resume and scan public jobs.</p>}</CardContent></Card></>;
}

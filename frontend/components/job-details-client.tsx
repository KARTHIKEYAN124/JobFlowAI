"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Check, ExternalLink, LoaderCircle, X } from "lucide-react";
import { PrepareApplicationButton } from "@/components/prepare-application-button";
import { PrepareInterviewButton } from "@/components/prepare-interview-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type Job = { id: string; title: string; company_name: string; location: string; remote_type: string; category: string; posted_at: string; description: string; application_url: string; source: string; required_skills: string[]; preferred_skills: string[] };
type Match = { job_id: string; overall_score: number; matched_skills: string[]; missing_skills: string[]; explanation: string };

export function JobDetailsClient({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    void Promise.all([api<Job>(`/jobs/${jobId}`), api<Match[]>("/matches")]).then(([record, matches]) => { setJob(record); setMatch(matches.find(item => item.job_id === jobId) ?? null); }).catch(caught => setError(caught instanceof Error ? caught.message : "Could not load this job."));
  }, [jobId]);
  if (error) return <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive" role="alert">{error}</p>;
  if (!job) return <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading job details…</div>;
  const matched = match?.matched_skills ?? job.required_skills;
  const missing = match?.missing_skills ?? [];
  const isDemo = job.source === "JobFlow demo";
  return <>
    <Button asChild variant="ghost" className="mb-6"><Link href="/jobs"><ArrowLeft data-icon="inline-start" />Back to jobs</Link></Button>
    <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]"><div className="flex flex-col gap-6"><Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-4"><div><Badge variant="outline">{job.category}</Badge>{isDemo ? <Badge className="ml-2" variant="warning">Portfolio demo</Badge> : null}<CardTitle className="mt-3 text-2xl">{job.title}</CardTitle><CardDescription className="mt-2">{job.company_name} · {job.location} · {job.remote_type}</CardDescription></div>{isDemo ? <Button variant="outline" disabled>No employer posting</Button> : <Button asChild variant="outline"><a href={job.application_url} target="_blank" rel="noreferrer"><ExternalLink data-icon="inline-start" />Original posting</a></Button>}</div></CardHeader><CardContent>{isDemo ? <p className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">This is sample portfolio data, not a real vacancy. Scan the public feeds or import a supported employer URL from the Jobs page.</p> : null}<h2 className="mb-3 font-display text-lg font-semibold">Job description</h2><p className="whitespace-pre-line leading-7 text-muted-foreground">{job.description}</p><h2 className="mb-3 mt-8 font-display text-lg font-semibold">Required skills</h2><div className="flex flex-wrap gap-2">{[...job.required_skills, ...job.preferred_skills].map(skill => <Badge key={skill} variant="secondary">{skill}</Badge>)}</div></CardContent></Card><PrepareInterviewButton jobId={job.id} /></div>
      <div className="flex flex-col gap-6"><Card><CardHeader><CardTitle>Match score</CardTitle><CardDescription>Resume and job-description overlap</CardDescription></CardHeader><CardContent><span className="font-display text-5xl font-bold text-primary">{Math.round(match?.overall_score ?? 0)}%</span><p className="mt-4 text-sm leading-6 text-muted-foreground">{match?.explanation ?? "Upload your resume and scan jobs to calculate this match."}</p></CardContent></Card><Card><CardHeader><CardTitle>Skill analysis</CardTitle></CardHeader><CardContent><p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Matched</p><div className="flex flex-col gap-2">{matched.map(skill => <div key={skill} className="flex items-center gap-2 text-sm"><Check className="size-4 text-emerald-600" />{skill}</div>)}</div><p className="mb-3 mt-6 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Missing</p>{missing.length ? missing.map(skill => <div key={skill} className="flex items-center gap-2 text-sm"><X className="size-4 text-amber-600" />{skill}</div>) : <p className="text-sm text-muted-foreground">No identified skill gaps.</p>}<div className="mt-6"><PrepareApplicationButton jobId={job.id} fullWidth disabled={isDemo} /></div></CardContent></Card></div>
    </div>
  </>;
}

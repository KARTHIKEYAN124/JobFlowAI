"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, BriefcaseBusiness, CalendarCheck, CircleCheckBig, Files, LoaderCircle, TrendingUp } from "lucide-react";
import { JobRow, type Job as JobView } from "@/components/job-row";
import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";

const PIPELINE_ORDER = ["DISCOVERED", "SAVED", "PREPARING", "READY", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN", "EXPIRED"] as const;

type DashboardData = {
  total_jobs: number; new_jobs: number; high_matches: number; scored_jobs: number;
  applications: number; ready: number; interviews: number; offers: number;
  pipeline: Record<string, number>;
  priority_matches: Array<{ id: string; title: string; company_name: string; location: string; remote_type: string; category: string; posted_at: string; required_skills: string[]; overall_score: number; matched_skills: string[]; missing_skills: string[] }>;
  recent_applications: Array<{ id: string; job_id: string; title: string; company_name: string; status: string; updated_at: string }>;
  skill_gaps: Array<{ skill: string; count: number; percentage: number }>;
};

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await api<DashboardData>("/analytics/dashboard")); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load dashboard activity."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading your live dashboard…</div>;
  if (!data) return <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive" role="alert">{error || "Dashboard data is unavailable."}<Button className="ml-3" size="sm" variant="outline" onClick={load}>Retry</Button></div>;

  const metrics = [
    { label: "Jobs available", value: data.total_jobs, delta: `${data.new_jobs} added in the last 24 hours`, icon: BriefcaseBusiness },
    { label: "High matches", value: data.high_matches, delta: `${data.scored_jobs} jobs scored for your profile`, icon: TrendingUp },
    { label: "Applications", value: data.applications, delta: `${data.ready} ready for review`, icon: Files },
    { label: "Interviews", value: data.interviews, delta: `${data.offers} offers recorded`, icon: CalendarCheck },
  ];
  const priorityJobs: JobView[] = data.priority_matches.map(job => ({ id: job.id, title: job.title, company: job.company_name, location: `${job.location} · ${job.remote_type}`, score: Math.round(job.overall_score), skills: job.matched_skills.length ? job.matched_skills : job.required_skills, missing: job.missing_skills, posted: new Date(job.posted_at).toLocaleDateString(), category: job.category }));

  return <>
    <PageHeading title="Your live job-search dashboard" description="Every number below comes from your saved jobs, matches, and applications." actions={<Button asChild><Link href="/jobs">View all jobs <ArrowRight data-icon="inline-end" /></Link></Button>} />
    {error ? <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p> : null}
    <section className="grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-2 xl:grid-cols-4">{metrics.map(({ label, value, delta, icon: Icon }) => <div key={label} className="bg-card p-5"><div className="mb-6 flex items-center justify-between"><span className="text-sm font-medium text-muted-foreground">{label}</span><Icon className="size-4 text-muted-foreground" /></div><p className="font-display text-3xl font-bold tracking-tight">{value}</p><p className="mt-1 text-xs text-muted-foreground">{delta}</p></div>)}</section>
    <div className="mt-6 grid gap-6 xl:grid-cols-[1.65fr_1fr]">
      <Card><CardHeader className="flex-row items-start justify-between"><div><CardTitle>Priority matches</CardTitle><CardDescription>Your highest current resume-to-JD scores</CardDescription></div><Badge variant="success">Live</Badge></CardHeader><CardContent>{priorityJobs.length ? priorityJobs.map(job => <JobRow key={job.id} job={job} compact />) : <EmptyState text="Upload a resume and scan jobs to calculate priority matches." />}</CardContent></Card>
      <Card><CardHeader><CardTitle>Application pipeline</CardTitle><CardDescription>All {data.applications} applications, including closed outcomes</CardDescription></CardHeader><CardContent><div className="grid grid-cols-2 gap-2">{PIPELINE_ORDER.map(status => <div key={status} className="flex items-center justify-between rounded-lg border bg-muted/25 px-3 py-2"><span className="text-xs font-medium text-muted-foreground">{status.replaceAll("_", " ")}</span><strong className="text-sm">{data.pipeline[status] ?? 0}</strong></div>)}</div></CardContent></Card>
    </div>
    <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.15fr]">
      <Card><CardHeader><CardTitle>Skills to build</CardTitle><CardDescription>Verified gaps across your scored jobs</CardDescription></CardHeader><CardContent className="flex flex-col gap-5">{data.skill_gaps.length ? data.skill_gaps.map(item => <div key={item.skill}><div className="mb-2 flex justify-between text-sm"><span className="font-medium">{item.skill}</span><span className="text-muted-foreground">{item.count} jobs · {item.percentage}%</span></div><Progress value={item.percentage} /></div>) : <EmptyState text="No skill gaps have been identified yet." />}</CardContent></Card>
      <Card><CardHeader><CardTitle>Recent application activity</CardTitle><CardDescription>Latest updates from your application tracker</CardDescription></CardHeader><CardContent className="flex flex-col gap-5">{data.recent_applications.length ? data.recent_applications.map(item => <Link key={item.id} href="/applications" className="flex items-start gap-3 rounded-md p-1 transition-colors hover:bg-muted/50"><CircleCheckBig className="mt-0.5 size-4 text-emerald-600"/><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{item.title}</p><p className="text-xs text-muted-foreground">{item.company_name} · {new Date(item.updated_at).toLocaleString()}</p></div><Badge variant="outline">{item.status}</Badge></Link>) : <EmptyState text="No applications yet. Prepare one from the Jobs page." />}</CardContent></Card>
    </div>
  </>;
}

function EmptyState({ text }: { text: string }) { return <p className="py-8 text-center text-sm text-muted-foreground">{text}</p>; }

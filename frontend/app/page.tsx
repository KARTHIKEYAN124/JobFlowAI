import Link from "next/link";
import { ArrowRight, BriefcaseBusiness, CalendarCheck, CircleCheckBig, Files, TrendingUp } from "lucide-react";
import { JobRow } from "@/components/job-row";
import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { applications, jobs } from "@/lib/data";

const metrics = [
  { label: "New Jobs", value: "137", delta: "+18 today", icon: BriefcaseBusiness },
  { label: "High Matches", value: "22", delta: "16% of new jobs", icon: TrendingUp },
  { label: "Applications", value: "18", delta: "4 need review", icon: Files },
  { label: "Interviews", value: "3", delta: "Next on Friday", icon: CalendarCheck },
];
const pipeline = [{ label: "Saved", count: 7 }, { label: "Preparing", count: 4 }, { label: "Ready", count: 3 }, { label: "Applied", count: 5 }, { label: "Interview", count: 3 }, { label: "Offer", count: 1 }];

export default function Dashboard() { return <>
  <PageHeading title="Your job search, intelligently orchestrated" description="Good morning. JobFlow found 18 new roles that fit your profile since yesterday." actions={<Button asChild><Link href="/jobs">View all jobs <ArrowRight data-icon="inline-end" /></Link></Button>} />
  <section className="grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-2 xl:grid-cols-4">{metrics.map(({ label, value, delta, icon: Icon }) => <div key={label} className="bg-card p-5"><div className="mb-6 flex items-center justify-between"><span className="text-sm font-medium text-muted-foreground">{label}</span><Icon className="size-4 text-muted-foreground" /></div><p className="font-display text-3xl font-bold tracking-tight">{value}</p><p className="mt-1 text-xs text-muted-foreground">{delta}</p></div>)}</section>
  <div className="mt-6 grid gap-6 xl:grid-cols-[1.65fr_1fr]">
    <Card><CardHeader className="flex-row items-start justify-between"><div><CardTitle>Priority matches</CardTitle><CardDescription>Ranked with deterministic and semantic scoring</CardDescription></div><Badge variant="success">Live</Badge></CardHeader><CardContent>{jobs.slice(0,3).map(job => <JobRow key={job.id} job={job} compact />)}</CardContent></Card>
    <Card><CardHeader><CardTitle>Application pipeline</CardTitle><CardDescription>One approval is waiting for your review</CardDescription></CardHeader><CardContent><div className="flex h-52 items-end gap-3">{pipeline.map((item, index) => <div key={item.label} className="flex flex-1 flex-col items-center gap-2"><strong className="text-sm">{item.count}</strong><div className="w-full rounded-t-md bg-primary/15" style={{ height: `${36 + index * 18}px` }}><div className="h-full w-full rounded-t-md bg-primary" style={{ opacity: 0.35 + index * 0.1 }} /></div><span className="origin-center -rotate-45 whitespace-nowrap text-[10px] text-muted-foreground sm:rotate-0">{item.label}</span></div>)}</div></CardContent></Card>
  </div>
  <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.15fr]">
    <Card><CardHeader><CardTitle>Skills to build</CardTitle><CardDescription>Most common gaps in your high-match jobs</CardDescription></CardHeader><CardContent className="flex flex-col gap-5">{[["Kafka",34],["Terraform",27],["Kubernetes",24],["German B2",22]].map(([skill,value]) => <div key={skill}><div className="mb-2 flex justify-between text-sm"><span className="font-medium">{skill}</span><span className="text-muted-foreground">{value}%</span></div><Progress value={Number(value)} /></div>)}</CardContent></Card>
    <Card><CardHeader><CardTitle>Recent activity</CardTitle><CardDescription>Applications and automation events</CardDescription></CardHeader><CardContent className="flex flex-col gap-5">{applications.slice(0,3).map(item => <div key={item.company} className="flex items-start gap-3"><CircleCheckBig className="mt-0.5 size-4 text-emerald-600"/><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{item.role}</p><p className="text-xs text-muted-foreground">{item.company} · {item.date}</p></div><Badge variant="outline">{item.status}</Badge></div>)}</CardContent></Card>
  </div>
</>; }

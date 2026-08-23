import Link from "next/link";
import { MapPin } from "lucide-react";
import { PrepareApplicationButton } from "@/components/prepare-application-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export type Job = { id: string; title: string; company: string; location: string; score: number; skills: string[]; missing: string[]; posted: string; category: string };

export function JobRow({ job, compact = false }: { job: Job; compact?: boolean }) {
  return <article className="group border-b py-5 last:border-b-0"><div className="flex flex-col gap-4 xl:flex-row xl:items-center"><div className="min-w-0 flex-1"><div className="mb-1 flex flex-wrap items-center gap-2"><h3 className="truncate font-display text-base font-semibold">{job.title}</h3><Badge variant="outline">{job.category}</Badge></div><p className="text-sm font-medium text-muted-foreground">{job.company}</p><p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="size-3" />{job.location} · {job.posted}</p></div><div className="w-full xl:w-40"><div className="mb-2 flex items-center justify-between text-xs"><span className="text-muted-foreground">Match</span><strong className="text-primary">{job.score}%</strong></div><Progress value={job.score}/></div>{!compact && <div className="flex min-w-0 flex-1 flex-wrap gap-1.5">{job.skills.slice(0, 4).map(skill => <Badge key={skill} variant="secondary">{skill}</Badge>)}{job.missing[0] ? <Badge variant="warning">Missing: {job.missing[0]}</Badge> : null}</div>}<div className="flex gap-2"><Button asChild variant="outline" size="sm"><Link href={`/jobs/${job.id}`}>Details</Link></Button><PrepareApplicationButton jobId={job.id} /></div></div></article>;
}

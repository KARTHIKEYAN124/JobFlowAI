"use client";

import { useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";

type SkillAnalytics = { skills: { skill: string; demand: number; percentage: number; gaps: number }[]; top_gaps: { skill: string; count: number; percentage: number }[]; strengths: string[]; jobs_analyzed: number };

export default function SkillsPage() {
  const [data, setData] = useState<SkillAnalytics | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void api<SkillAnalytics>("/analytics/skills").then(setData).catch(caught => setError(caught instanceof Error ? caught.message : "Could not load skill analytics.")); }, []);
  return <><PageHeading title="Skills intelligence" description="Demand and gaps calculated from jobs currently matching your profile."/>{error ? <p className="mb-4 text-sm text-destructive" role="alert">{error}</p> : null}{!data ? <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin"/>Loading market data…</p> : <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]"><Card><CardHeader><CardTitle>Most requested</CardTitle><CardDescription>{data.jobs_analyzed} current matching jobs analyzed</CardDescription></CardHeader><CardContent className="flex flex-col gap-6">{data.skills.length ? data.skills.map(item => <div key={item.skill}><div className="mb-2 flex justify-between text-sm"><span className="font-semibold">{item.skill}</span><span className="text-muted-foreground">{item.demand} jobs · {item.percentage}%</span></div><Progress value={item.percentage}/></div>) : <p className="text-sm text-muted-foreground">Scan jobs to build demand statistics.</p>}</CardContent></Card><div className="flex flex-col gap-6"><Card><CardHeader><CardTitle>Your gaps</CardTitle><CardDescription>Prioritized by frequency in your matches</CardDescription></CardHeader><CardContent className="flex flex-wrap gap-2">{data.top_gaps.length ? data.top_gaps.map((item, index) => <Badge key={item.skill} variant={index < 2 ? "warning" : "secondary"}>{item.skill} · {item.percentage}%</Badge>) : <span className="text-sm text-muted-foreground">No identified gaps yet.</span>}</CardContent></Card><Card><CardHeader><CardTitle>Your verified strengths</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-2">{data.strengths.map(skill => <Badge key={skill} variant="success">{skill}</Badge>)}</CardContent></Card></div></div>}</>;
}

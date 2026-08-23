import { JobRow } from "@/components/job-row";
import { PageHeading } from "@/components/page-heading";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { jobs } from "@/lib/data";
export default function MatchesPage(){return <><PageHeading title="Matches" description="Explainable rankings based on skills, role, experience, education, location, language, freshness, and employment type."/><Card><CardHeader><CardTitle>Ranked matches</CardTitle><CardDescription>Scores are computed—not invented by an LLM.</CardDescription></CardHeader><CardContent>{jobs.map(job=><JobRow key={job.id} job={job}/>)}</CardContent></Card></>}


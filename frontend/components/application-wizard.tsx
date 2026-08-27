"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, ExternalLink, LoaderCircle, Save } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

type Profile = { full_name: string; headline: string; expected_salary: string; remote_preference: string };
type Job = { id: string; title: string; company_name: string; location: string; employment_type: string; remote_type: string; source: string; application_url: string };
type Application = { id: string };
type Pack = { resume_suggestions: string; cover_letter: string; recruiter_message: string; application_answer: string; requires_human_approval: boolean };
type PortalLaunch = { portal_url: string; expires_at: string; requires_extension: boolean; requires_human_confirmation: boolean };
type SavedAnswers = { answers: Record<string, string>; questions: Record<string, string> };
type PortalQuestion = { key: string; label: string; required: boolean; type: string; options: string[] };
type PortalQuestions = { questions: PortalQuestion[]; source: string; note: string };

export function ApplicationWizard({ jobId }: { jobId: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [saved, setSaved] = useState<SavedAnswers>({ answers: {}, questions: {} });
  const [portalQuestions, setPortalQuestions] = useState<PortalQuestions>({ questions: [], source: "", note: "" });
  const [pack, setPack] = useState<Pack | null>(null);
  const [applicationId, setApplicationId] = useState("");
  const [submittedDetails, setSubmittedDetails] = useState<Record<string, FormDataEntryValue>>({});
  const [pending, setPending] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([api<Profile>("/profile"), api<Job>(`/jobs/${jobId}`), api<SavedAnswers>("/application-answers"), api<PortalQuestions>(`/jobs/${jobId}/application-questions`)]).then(([profileRecord, jobRecord, savedRecord, questionRecord]) => { setProfile(profileRecord); setJob(jobRecord); setSaved(savedRecord); setPortalQuestions(questionRecord); }).catch(caught => setError(caught instanceof Error ? caught.message : "Could not load the application form."));
  }, [jobId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    const values = new FormData(event.currentTarget);
    const details = Object.fromEntries(values.entries());
    details._question_labels = JSON.stringify(Object.fromEntries(portalQuestions.questions.map(question => [question.key, question.label])));
    setSubmittedDetails(details);
    try {
      const application = await api<Application>("/applications", { method: "POST", body: JSON.stringify({ job_id: jobId, notes: JSON.stringify(details) }) });
      setApplicationId(application.id);
      setPack(await api<Pack>("/ai/application", { method: "POST", body: JSON.stringify({ application_id: application.id }) }));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not prepare the application."); }
    finally { setPending(false); }
  }

  async function launchPortal() {
    if (!applicationId) return;
    setLaunching(true); setError("");
    try {
      const launch = await api<PortalLaunch>(`/applications/${applicationId}/portal-session`, { method: "POST" });
      const bridge = new URL("/portal-launch", window.location.origin);
      bridge.hash = new URLSearchParams({ target: launch.portal_url }).toString();
      window.open(bridge.toString(), "_blank", "noopener,noreferrer");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not open the employer portal."); }
    finally { setLaunching(false); }
  }

  async function regenerate() {
    if (!applicationId) return;
    setPending(true); setError("");
    try { setPack(await api<Pack>("/ai/application", { method: "POST", body: JSON.stringify({ application_id: applicationId }) })); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not generate another version."); }
    finally { setPending(false); }
  }

  if (!profile || !job) return <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading application form…{error ? <span className="text-destructive">{error}</span> : null}</div>;
  if (pack) return <><PageHeading title="Application ready for review" description={`${job.title} at ${job.company_name}`} actions={<div className="flex flex-wrap gap-2"><Button variant="outline" onClick={regenerate} disabled={pending}>{pending ? <LoaderCircle className="animate-spin" data-icon="inline-start"/> : null}{pending ? "Generating…" : "Generate another version"}</Button><Button variant="outline" asChild><Link href="/applications"><CheckCircle2 data-icon="inline-start" />Open tracker</Link></Button><Button onClick={launchPortal} disabled={launching || job.source === "JobFlow demo"}>{launching ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <ExternalLink data-icon="inline-start" />}{job.source === "JobFlow demo" ? "Demo listing — no portal" : launching ? "Opening portal…" : "Fill on job portal"}</Button></div>} />{error ? <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p> : null}<Card className="mb-6"><CardHeader><CardTitle>Your application details</CardTitle><CardDescription>Confirm these details before approving the draft. Every regeneration is stored as a new document version.</CardDescription></CardHeader><CardContent className="grid gap-4 md:grid-cols-2">{Object.entries(submittedDetails).map(([key, value]) => <div key={key}><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{key.replaceAll("_", " ")}</p><p className="mt-1 text-sm">{String(value)}</p></div>)}</CardContent></Card><div className="grid gap-6 lg:grid-cols-2"><ReviewCard title="Cover letter" content={pack.cover_letter} /><ReviewCard title="Recruiter message" content={pack.recruiter_message} /><ReviewCard title="Resume suggestions" content={pack.resume_suggestions} /><ReviewCard title="Application answer" content={pack.application_answer} /></div><p className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">{job.source === "JobFlow demo" ? "This portfolio demo has no employer portal. Open Jobs, scan the public feeds or import a real supported posting, then prepare that application." : "Install the JobFlow Companion from the repository before opening the portal. It fills Greenhouse, Lever, Ashby, and SmartRecruiters forms, attaches the verified tailored PDF, and asks you every visible portal-specific question it cannot safely prefill. Review is required before submission; CAPTCHA and MFA remain manual."}</p></>;

  return <>
    <Button asChild variant="ghost" className="mb-6"><Link href={`/jobs/${jobId}`}><ArrowLeft data-icon="inline-start" />Back to job</Link></Button>
    <PageHeading title="Complete application details" description={`${job.title} at ${job.company_name} · ${job.location}`} />
    {error ? <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p> : null}
    <form onSubmit={submit} className="space-y-6">
      <Section title="Contact details" description="Information normally requested by an employer."><div className="grid gap-4 md:grid-cols-2"><Field name="full_name" label="Legal full name" defaultValue={saved.answers.full_name || profile.full_name} required /><Field name="email" label="Email address" type="email" defaultValue={saved.answers.email} required /><Field name="phone" label="Phone number" type="tel" defaultValue={saved.answers.phone} required /><Field name="address" label="Current city and country" defaultValue={saved.answers.address} required /><Field name="linkedin" label="LinkedIn URL" type="url" defaultValue={saved.answers.linkedin} /><Field name="portfolio" label="Portfolio or GitHub URL" type="url" defaultValue={saved.answers.portfolio} /></div></Section>
      <Section title="Eligibility and availability" description="Answer these accurately; saved answers can be reused on your next application."><div className="grid gap-4 md:grid-cols-2"><Select name="work_authorization" label="Authorized to work in this job’s country?" options={["Yes", "No"]} defaultValue={saved.answers.work_authorization} /><Select name="sponsorship" label="Will you require visa sponsorship?" options={["No", "Yes"]} defaultValue={saved.answers.sponsorship} /><Field name="available_from" label="Available start date" type="date" defaultValue={saved.answers.available_from} required /><Field name="notice_period" label="Notice period" placeholder="For example: 2 weeks" defaultValue={saved.answers.notice_period} required /><Select name="relocation" label="Willing to relocate?" options={["Yes", "No", "Not applicable"]} defaultValue={saved.answers.relocation} /><Select name="remote_preference" label="Workplace preference" options={[profile.remote_preference || "Hybrid", "Remote", "On-site", "Hybrid"]} defaultValue={saved.answers.remote_preference} /></div></Section>
      <Section title="Role preferences" description="Confirm the terms you want associated with this application."><div className="grid gap-4 md:grid-cols-2"><Field name="expected_salary" label="Expected salary or hourly rate" defaultValue={saved.answers.expected_salary || profile.expected_salary} required /><Field name="hours_per_week" label="Available hours per week" type="number" placeholder="20" defaultValue={saved.answers.hours_per_week} required /><Select name="employment_type" label="Employment type" options={[job.employment_type, "Full time", "Part time", "Working student", "Internship"]} defaultValue={saved.answers.employment_type} /><Field name="preferred_interview_times" label="Preferred interview times" placeholder="Weekdays after 14:00" defaultValue={saved.answers.preferred_interview_times} /></div></Section>
      <Section title="Job-specific writing" description="These answers tailor the application to this job description without inventing experience."><TextField name="motivation" label={`Why do you want to join ${job.company_name}?`} defaultValue={saved.answers.motivation} required /><TextField name="relevant_experience" label="Describe your most relevant experience or project" defaultValue={saved.answers.relevant_experience} required /><TextField name="achievement" label="Describe one measurable achievement" defaultValue={saved.answers.achievement} required /><TextField name="additional_information" label="Additional information for the employer" defaultValue={saved.answers.additional_information} /></Section>
      <Section title="Employer portal questions" description={portalQuestions.note || "Questions exposed by the employer's current application portal."}>{portalQuestions.questions.length ? <div className="grid gap-4 md:grid-cols-2">{portalQuestions.questions.map(question => <EmployerQuestion key={question.key} question={question} defaultValue={saved.answers[question.key]} />)}</div> : <p className="text-sm text-muted-foreground">No additional questions are publicly exposed. The companion will read the real rendered form and ask you any remaining questions before it fills or submits anything.</p>}<p className="text-xs text-muted-foreground">Source: {portalQuestions.source || "employer portal"}</p></Section>
      <Card><CardContent className="space-y-4 p-5"><label className="flex items-start gap-3 text-sm"><input className="mt-1 size-4" type="checkbox" name="truth_confirmation" required /><span>I confirm that these details are accurate and that generated content must not add experience or claims I do not have.</span></label><label className="flex items-start gap-3 text-sm"><input className="mt-1 size-4" type="checkbox" name="review_confirmation" required /><span>I understand JobFlow will prepare and fill a draft, but submission requires my explicit confirmation on the employer portal.</span></label></CardContent></Card>
      <Card><CardContent className="p-5"><label className="flex items-start gap-3 text-sm"><input className="mt-1 size-4" type="checkbox" name="save_for_future" defaultChecked /><span><strong>Save these answers for future applications.</strong> JobFlow will prefill matching fields next time; you can still edit every answer before use.</span></label></CardContent></Card>
      <div className="flex justify-end"><Button type="submit" size="lg" disabled={pending}>{pending ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Save data-icon="inline-start" />}{pending ? "Generating application…" : "Save details and generate application"}</Button></div>
    </form>
  </>;
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) { return <Card><CardHeader><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent className="space-y-4">{children}</CardContent></Card>; }
function Field({ name, label, type = "text", defaultValue, placeholder, required }: { name: string; label: string; type?: string; defaultValue?: string; placeholder?: string; required?: boolean }) { return <label className="flex flex-col gap-2 text-sm font-medium">{label}<Input name={name} type={type} defaultValue={defaultValue} placeholder={placeholder} required={required} /></label>; }
function Select({ name, label, options, defaultValue }: { name: string; label: string; options: string[]; defaultValue?: string }) { const choices=[...new Set([defaultValue || "",...options].filter(Boolean))]; return <label className="flex flex-col gap-2 text-sm font-medium">{label}<select name={name} required defaultValue={defaultValue || choices[0]} className="h-10 rounded-md border bg-background px-3 text-sm">{choices.map(option => <option key={option}>{option}</option>)}</select></label>; }
function TextField({ name, label, required, defaultValue }: { name: string; label: string; required?: boolean; defaultValue?: string }) { return <label className="flex flex-col gap-2 text-sm font-medium">{label}<textarea name={name} required={required} defaultValue={defaultValue} rows={4} className="rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2" /></label>; }
function EmployerQuestion({ question, defaultValue }: { question: PortalQuestion; defaultValue?: string }) { if (question.options.length || question.type.includes("checkbox")) return <Select name={question.key} label={question.label} options={question.options.length ? question.options : ["Yes", "No"]} defaultValue={defaultValue} />; if (question.type.includes("textarea")) return <TextField name={question.key} label={question.label} required={question.required} defaultValue={defaultValue} />; return <Field name={question.key} label={question.label} type={question.type.includes("number") ? "number" : question.type.includes("date") ? "date" : "text"} defaultValue={defaultValue} required={question.required} />; }
function ReviewCard({ title, content }: { title: string; content: string }) { return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent><p className="whitespace-pre-line text-sm leading-6 text-muted-foreground">{content}</p></CardContent></Card>; }

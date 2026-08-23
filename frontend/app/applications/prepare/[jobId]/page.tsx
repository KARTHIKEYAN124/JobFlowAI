import { ApplicationWizard } from "@/components/application-wizard";

export default async function PrepareApplicationPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <ApplicationWizard jobId={jobId} />;
}

import { JobDetailsClient } from "@/components/job-details-client";

export default async function JobDetails({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobDetailsClient jobId={id} />;
}

"use client";

import { useParams } from "next/navigation";

import { JobProgress } from "@/components/job-progress";

export function JobView() {
  const { id } = useParams<{ id: string }>();
  return <JobProgress jobId={id} />;
}

"use client";

import { useParams } from "next/navigation";

export function JobView() {
  const { id } = useParams<{ id: string }>();
  return <p className="text-muted-foreground">Job {id}</p>;
}

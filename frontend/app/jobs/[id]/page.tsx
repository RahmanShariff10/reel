import { Suspense } from "react";

import { JobView } from "./job-view";

export default function JobPage() {
  return (
    <Suspense>
      <JobView />
    </Suspense>
  );
}

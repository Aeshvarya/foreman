import { useEffect, useState } from "react";
import { api, type Project } from "./api";

let cache: Project | null = null;

/** Fetch the project graph once, cache it across tools. */
export function useProject() {
  const [project, setProject] = useState<Project | null>(cache);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (cache) return;
    api.project().then((p) => { cache = p; setProject(p); }).catch((e) => setError(String(e)));
  }, []);
  return { project, error };
}

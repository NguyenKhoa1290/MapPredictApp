import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { getProjects, getSiteContent } from '../shared/api/client';
import type { Project, SiteContent } from '../shared/api/types';

interface PublicState {
  content: SiteContent | null;
  projects: Project[];
  loading: boolean;
  error: string | null;
  retry: () => void;
}
const PublicContext = createContext<PublicState | null>(null);

export function PublicDataProvider({ children }: { children: ReactNode }) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<Omit<PublicState, 'retry'>>({ content: null, projects: [], loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setState({ content: null, projects: [], loading: true, error: null });
    Promise.all([getSiteContent(controller.signal), getProjects(controller.signal)])
      .then(([content, projects]) => {
        if (!controller.signal.aborted) setState({ content, projects, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ content: null, projects: [], loading: false,
          error: error instanceof Error ? error.message : 'Không tải được nội dung.' });
      });
    return () => controller.abort();
  }, [attempt]);
  return <PublicContext.Provider value={{ ...state, retry: () => setAttempt(value => value + 1) }}>{children}</PublicContext.Provider>;
}

export function usePublicData() {
  const state = useContext(PublicContext);
  if (!state) throw new Error('PublicDataProvider is required');
  return state;
}

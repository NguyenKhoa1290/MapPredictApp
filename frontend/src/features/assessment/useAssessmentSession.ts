import { useEffect, useRef, useState } from 'react';
import { AssessmentStorage, emptyAssessment } from './persistence';
import type { AssessmentState } from './persistence';

export function useAssessmentSession() {
  const [state, setState] = useState<AssessmentState>(emptyAssessment);
  const [ready, setReady] = useState(false);
  const [saveStatus, setSaveStatus] = useState('Đang mở phiên đã lưu');
  const [saveError, setSaveError] = useState(false);
  const persisted = useRef(state);
  const pending = useRef<AssessmentState | null>(null);
  const saving = useRef<Promise<void> | null>(null);
  const blocked = useRef(false), mounted = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flush = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    let cancelled = false;
    let current: AssessmentStorage | null = null;
    mounted.current = true; blocked.current = false;
    flush.current = () => {
      if (timer.current) clearTimeout(timer.current);
      if (saving.current) return saving.current;
      if (!current || blocked.current || !pending.current) return Promise.resolve();
      saving.current = (async () => {
        while (pending.current && !blocked.current) {
          const next = pending.current; pending.current = null;
          if (mounted.current) setSaveStatus('Đang tự lưu');
          try {
            await current!.write(next); persisted.current = next;
            if (mounted.current) { setSaveStatus('Đã tự lưu trên trình duyệt'); setSaveError(false); }
          } catch (error) {
            if (!pending.current) pending.current = next;
            if (error instanceof Error && error.name === 'WorkspaceConflictError') blocked.current = true;
            if (mounted.current) {
              setSaveError(true);
              setSaveStatus(blocked.current ? 'Tab khác đã lưu phiên mới, tải lại trang để tiếp tục'
                : 'Chưa lưu được thay đổi, bản lưu trước đó vẫn được giữ');
            }
            break;
          }
        }
      })().finally(() => { saving.current = null; });
      return saving.current;
    };
    async function restore() {
      try {
        current = new AssessmentStorage();
        const restored = await current.read();
        if (cancelled) return;
        if (restored) { persisted.current = restored; setState(restored); }
        setSaveStatus(restored ? 'Đã khôi phục phiên đã lưu' : 'Tự động lưu thao tác trên trình duyệt');
      } catch {
        if (cancelled) return;
        blocked.current = true; setSaveError(true);
        setSaveStatus('Chưa mở được bộ nhớ trình duyệt, bản lưu cũ được giữ và thao tác mới chưa được tự lưu');
      } finally {
        if (cancelled) current?.close();
        else setReady(true);
      }
    }
    const hide = () => { void flush.current(); };
    const visibility = () => { if (document.hidden) hide(); };
    window.addEventListener('pagehide', hide); document.addEventListener('visibilitychange', visibility);
    void restore();
    return () => {
      cancelled = true; mounted.current = false;
      window.removeEventListener('pagehide', hide); document.removeEventListener('visibilitychange', visibility);
      if (timer.current) clearTimeout(timer.current);
      void flush.current().finally(() => current?.close());
    };
  }, []);

  useEffect(() => {
    if (!ready || blocked.current || state === persisted.current) return;
    pending.current = state;
    setSaveStatus('Đang chờ tự lưu');
    timer.current = setTimeout(() => { void flush.current(); }, 180);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [state, ready]);
  return { state, setState, ready, saveStatus, saveError };
}

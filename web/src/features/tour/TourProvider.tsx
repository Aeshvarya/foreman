import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

/** On-screen rectangle of a highlighted element, in viewport coordinates. */
export type Rect = { x: number; y: number; width: number; height: number };

/** One coach-mark: which registered target to spotlight + what to say. */
export type TourStep = {
  /** Matches the `name` prop of a <TourTarget> on screen. */
  target: string;
  title: string;
  body: string;
};

const STORAGE_KEY = "foreman:seenTours";

function loadSeen(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}
function saveSeen(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    /* localStorage unavailable — tours just won't persist across reloads */
  }
}

type TourState = {
  setRect: (name: string, rect: Rect) => void;
  clearRect: (name: string) => void;
  /** Start a tour once — no-op if already seen (persisted) or another tour is active. */
  start: (tourId: string, steps: TourStep[]) => void;
  /** Force-run a tour right now, ignoring the seen/active guards. For "replay tutorial". */
  restart: (tourId: string, steps: TourStep[]) => void;
  steps: TourStep[] | null;
  index: number;
  next: () => void;
  finish: () => void;
  rects: Record<string, Rect>;
};

const Ctx = createContext<TourState | null>(null);

export function useTour(): TourState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTour must be used inside <TourProvider>");
  return ctx;
}

export function TourProvider({ children }: PropsWithChildren) {
  const seen = useRef<string[]>(loadSeen());
  const [rects, setRects] = useState<Record<string, Rect>>({});
  const [steps, setSteps] = useState<TourStep[] | null>(null);
  const [index, setIndex] = useState(0);
  const activeId = useRef<string | null>(null);

  const setRect = useCallback((name: string, rect: Rect) => {
    setRects((prev) => {
      const cur = prev[name];
      if (cur && cur.x === rect.x && cur.y === rect.y && cur.width === rect.width && cur.height === rect.height) {
        return prev; // no change — avoid re-render churn
      }
      return { ...prev, [name]: rect };
    });
  }, []);

  const clearRect = useCallback((name: string) => {
    setRects((prev) => {
      if (!(name in prev)) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const run = useCallback((tourId: string, tourSteps: TourStep[]) => {
    activeId.current = tourId;
    setSteps(tourSteps);
    setIndex(0);
  }, []);

  const start = useCallback(
    (tourId: string, tourSteps: TourStep[]) => {
      if (seen.current.includes(tourId)) return;
      if (activeId.current) return; // one tour at a time
      run(tourId, tourSteps);
    },
    [run],
  );

  const restart = useCallback(
    (tourId: string, tourSteps: TourStep[]) => {
      run(tourId, tourSteps);
    },
    [run],
  );

  const finish = useCallback(() => {
    const id = activeId.current;
    if (id && !seen.current.includes(id)) {
      seen.current = [...seen.current, id];
      saveSeen(seen.current);
    }
    activeId.current = null;
    setSteps(null);
    setIndex(0);
  }, []);

  const next = useCallback(() => {
    setIndex((i) => {
      if (!steps) return i;
      if (i + 1 >= steps.length) {
        finish();
        return 0;
      }
      return i + 1;
    });
  }, [steps, finish]);

  const value = useMemo<TourState>(
    () => ({ setRect, clearRect, start, restart, steps, index, next, finish, rects }),
    [setRect, clearRect, start, restart, steps, index, next, finish, rects],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

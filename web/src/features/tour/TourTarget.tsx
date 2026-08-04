import type React from "react";
import { useCallback, useEffect, useRef, type PropsWithChildren } from "react";
import { useTour } from "./TourProvider";

/**
 * Wraps a real on-screen element so the spotlight tour can highlight it.
 * Measures its viewport rect on layout/resize/scroll (and re-measures when the
 * tour advances, since content above it can shift the page) and registers it
 * under `name`. Purely a measuring wrapper — renders its children unchanged.
 */
export function TourTarget({
  name,
  className,
  as: As = "div",
  children,
}: PropsWithChildren<{ name: string; className?: string; as?: "div" | "nav" }>) {
  const { setRect, clearRect, steps, index } = useTour();
  const ref = useRef<HTMLElement>(null);

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      setRect(name, { x: r.left, y: r.top, width: r.width, height: r.height });
    }
  }, [name, setRect]);

  useEffect(() => {
    measure();
    const t = setTimeout(measure, 60); // catch late layout (fonts, images, data)
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
    // re-measure whenever the active step changes — the target may have moved
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measure, steps, index]);

  useEffect(() => () => clearRect(name), [name, clearRect]);

  return (
    // `As` is polymorphic ("div" | "nav") so TS can't narrow the ref to one
    // concrete element type; both are HTMLElement at runtime, which is all the
    // measuring above needs. The cast is the standard accommodation for a
    // polymorphic `as` prop, not a papered-over bug.
    <As ref={ref as React.Ref<HTMLDivElement>} className={className}>
      {children}
    </As>
  );
}

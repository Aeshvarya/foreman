import { AnimatePresence, motion } from "framer-motion";
import { GlassCard, Kicker } from "../../components/primitives";
import { useTour } from "./TourProvider";

const PAD = 8; // breathing room around the spotlit element
const DIM = "rgba(6,7,9,0.74)";

/** Renders nothing unless a tour is active. Mount ONCE near the app root. */
export function TourOverlay() {
  const { steps, index, rects, next, finish } = useTour();
  const step = steps ? steps[index] : null;
  const target = step ? rects[step.target] : undefined;

  if (!step) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;

  const hole = target
    ? { top: target.y - PAD, left: target.x - PAD, width: target.width + PAD * 2, height: target.height + PAD * 2 }
    : { top: vh / 2, left: vw / 2, width: 0, height: 0 };
  const holeBottom = hole.top + hole.height;
  const holeRight = hole.left + hole.width;

  // Place the tooltip in whichever open space (above or below the target)
  // actually has room for it — never on top of the spotlit element itself.
  const roomAbove = hole.top;
  const roomBelow = vh - holeBottom;
  const placeBelow = roomBelow >= roomAbove;
  // Clamped both ends: an oversized or off-screen target (a target taller than
  // the viewport, or scrolled partly out of it) must never push the tooltip
  // itself out of reach — it always has to land somewhere clickable.
  const tipTop = placeBelow ? Math.min(Math.max(16, holeBottom + 16), vh - 220) : undefined;
  const tipBottom = !placeBelow ? Math.min(Math.max(16, vh - hole.top + 16), vh - 200) : undefined;

  const last = index + 1 >= steps!.length;

  return (
    <div className="fixed inset-0 z-[200]" aria-live="polite">
      {/* Four dim panels forming a cutout around the target — no SVG masking
          needed. Clicking the dim advances the tour; clicking the hole falls
          through to the real element beneath if the user wants to try it. */}
      {target ? (
        <>
          <Panel style={{ top: 0, left: 0, right: 0, height: Math.max(0, hole.top) }} onClick={next} />
          <Panel style={{ top: holeBottom, left: 0, right: 0, bottom: 0 }} onClick={next} />
          <Panel style={{ top: hole.top, left: 0, width: Math.max(0, hole.left), height: hole.height }} onClick={next} />
          <Panel style={{ top: hole.top, left: holeRight, right: 0, height: hole.height }} onClick={next} />
        </>
      ) : (
        <Panel style={{ inset: 0 }} onClick={next} />
      )}

      {/* Glowing amber outline on the spotlit element */}
      {target && (
        <motion.div
          className="pointer-events-none absolute rounded-2xl border-2"
          style={{ borderColor: "var(--amber)", boxShadow: "0 0 0 4px rgba(245,166,35,0.12), 0 0 24px rgba(245,166,35,0.35)" }}
          animate={{ top: hole.top, left: hole.left, width: hole.width, height: hole.height }}
          transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
        />
      )}

      <div className="pointer-events-none absolute left-0 right-0 px-4 sm:px-0" style={{ top: tipTop, bottom: tipBottom }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={index}
            initial={{ opacity: 0, y: placeBelow ? -8 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-auto mx-auto max-w-[420px]"
          >
            <GlassCard className="border-amber/25 p-5">
              <Kicker className="text-amber/80">
                STEP {index + 1} OF {steps!.length}
              </Kicker>
              <div className="mt-2 font-display text-lg font-bold">{step.title}</div>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{step.body}</p>
              <div className="mt-4 flex items-center gap-4">
                {!last && (
                  <button onClick={finish} className="text-xs text-faint transition hover:text-text">
                    Skip
                  </button>
                )}
                <div className="flex flex-1 justify-center gap-1.5">
                  {steps!.map((_, i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full transition-colors"
                      style={{ background: i === index ? "var(--amber)" : "var(--border-strong)" }}
                    />
                  ))}
                </div>
                <button
                  onClick={next}
                  className="rounded-lg bg-amber px-4 py-1.5 text-sm font-medium text-black transition hover:bg-amber-bright"
                >
                  {last ? "Got it" : "Next"}
                </button>
              </div>
            </GlassCard>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function Panel({ style, onClick }: { style: React.CSSProperties; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="absolute cursor-pointer transition-opacity"
      style={{ background: DIM, ...style }}
    />
  );
}

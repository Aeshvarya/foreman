import { motion } from "framer-motion";

/* The differentiation anchor: a live supply-chain schematic. Three columns
   (suppliers → materials → activities → handover). Most of the graph sits
   dim and steel; ONE chain — the critical path — draws itself in amber and
   pulses, exactly the "watch the brain light up what breaks" idea. */

type P = { x: number; y: number };
const SUP: P[] = [{ x: 40, y: 70 }, { x: 40, y: 150 }, { x: 40, y: 230 }, { x: 40, y: 310 }, { x: 40, y: 390 }];
const MAT: P[] = [{ x: 210, y: 60 }, { x: 210, y: 140 }, { x: 210, y: 220 }, { x: 210, y: 300 }, { x: 210, y: 380 }];
const ACT: P[] = [{ x: 380, y: 90 }, { x: 380, y: 170 }, { x: 380, y: 250 }, { x: 380, y: 330 }];
const HANDOVER: P = { x: 380, y: 250 };

// dim structural edges
const DIM: [P, P][] = [
  [SUP[0], MAT[0]], [SUP[1], MAT[1]], [SUP[2], MAT[3]], [SUP[3], MAT[4]], [SUP[4], MAT[2]],
  [MAT[0], ACT[0]], [MAT[1], ACT[1]], [MAT[3], ACT[3]], [MAT[4], ACT[3]],
  [ACT[0], ACT[1]], [ACT[3], ACT[2]],
];
// the amber critical path
const CRIT: [P, P][] = [[SUP[2], MAT[2]], [MAT[2], ACT[1]], [ACT[1], ACT[2]]];
const CRIT_NODES: P[] = [SUP[2], MAT[2], ACT[1], HANDOVER];

const path = (a: P, b: P) => `M${a.x},${a.y} C${(a.x + b.x) / 2},${a.y} ${(a.x + b.x) / 2},${b.y} ${b.x},${b.y}`;

export default function HeroGraph() {
  return (
    <svg viewBox="0 0 430 460" className="h-full w-full" aria-hidden>
      <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {DIM.map(([a, b], i) => (
        <path key={`d${i}`} d={path(a, b)} stroke="rgba(255,255,255,0.10)" strokeWidth="1" fill="none" />
      ))}
      {[...SUP, ...MAT, ...ACT].map((n, i) => (
        <circle key={`n${i}`} cx={n.x} cy={n.y} r="4" fill="var(--steel)" opacity="0.5" />
      ))}

      {CRIT.map(([a, b], i) => (
        <motion.path
          key={`c${i}`} d={path(a, b)} stroke="var(--amber)" strokeWidth="2" fill="none"
          filter="url(#glow)"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 0.9, delay: 0.4 + i * 0.5, ease: "easeInOut" }}
        />
      ))}
      {CRIT_NODES.map((n, i) => (
        <motion.circle
          key={`cn${i}`} cx={n.x} cy={n.y} r={i === CRIT_NODES.length - 1 ? 7 : 5}
          fill="var(--amber)" filter="url(#glow)"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.4 + i * 0.5, type: "spring", stiffness: 200 }}
        >
          <animate attributeName="opacity" values="1;0.55;1" dur="2.4s" repeatCount="indefinite" />
        </motion.circle>
      ))}
      <text x={HANDOVER.x + 14} y={HANDOVER.y + 4} className="font-mono"
        fontSize="9" fill="var(--amber)" letterSpacing="1">HANDOVER</text>
    </svg>
  );
}

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle, PhoneCall, Eye, ShieldCheck, ChevronRight, CalendarCheck2, IndianRupee,
} from "lucide-react";
import { api, type Brief, type BriefItem } from "../lib/api";
import { GlassCard, Kicker, Badge } from "../components/primitives";
import { cn } from "../lib/cn";

/* The page that answers "is today a normal day?" without being asked.
 *
 * Every other tool waits to be driven — pick a material, choose a number of
 * days, read a graph. This one does the asking on the user's behalf and hands
 * back sentences. A site manager should be able to read it in fifteen seconds
 * and know whether to pick up the phone. */

const STATUS = {
  "needs you today": { icon: AlertTriangle, tone: "red", label: "needs you today" },
  "worth a call": { icon: PhoneCall, tone: "amber", label: "worth a call" },
  "keep an eye on it": { icon: Eye, tone: "amber", label: "keep an eye on it" },
  "fine": { icon: ShieldCheck, tone: "green", label: "fine" },
} as const;

const TONE_TEXT = { red: "text-red", amber: "text-amber", green: "text-green" } as const;
const TONE_BORDER = { red: "border-red/40", amber: "border-amber/30", green: "border-line" } as const;
const TONE_BG = { red: "bg-red/10", amber: "bg-amber/10", green: "bg-green/10" } as const;

export default function Today() {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [failed, setFailed] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let live = true;
    api.today()
      .then((b) => live && setBrief(b))
      .catch(() => live && setFailed(true));
    return () => { live = false; };
  }, []);

  if (failed) return (
    <GlassCard className="p-6 text-sm text-muted">
      Could not read the project just now. Try refreshing — nothing is lost.
    </GlassCard>
  );

  if (!brief) return (
    <div className="flex flex-col gap-4">
      <GlassCard className="h-32 animate-pulse p-6 text-sm text-muted">
        looking over the whole project…
      </GlassCard>
    </div>
  );

  const quiet = brief.tone === "calm";
  const shown = showAll ? brief.items : brief.items.filter((i) => i.status !== "fine");
  const hidden = brief.items.length - shown.length;

  return (
    <div className="flex flex-col gap-6">
      {/* the one line that matters */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
        <GlassCard className={cn("p-6", brief.tone === "urgent" ? "border-red/40"
          : brief.tone === "watch" ? "border-amber/25" : "border-green/30")}>
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="min-w-0">
              <Kicker>{brief.project}</Kicker>
              <h2 className={cn("mt-1.5 font-display text-3xl font-bold",
                brief.tone === "urgent" ? "text-red" : quiet ? "text-green" : "text-text")}>
                {brief.headline}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">{brief.subhead}</p>
            </div>

            <div className="flex shrink-0 gap-8">
              {brief.handover && (
                <div>
                  <div className="flex items-center gap-1.5 text-faint"><CalendarCheck2 size={13} />
                    <span className="kicker">handover</span></div>
                  <div className="mt-1 font-mono text-lg">{brief.handover}</div>
                </div>
              )}
              <div>
                <div className="flex items-center gap-1.5 text-faint"><IndianRupee size={13} />
                  <span className="kicker">at stake</span></div>
                <div className="mt-1 font-display text-lg font-bold">{brief.at_stake_label}</div>
                <div className="text-xs text-faint">if every supplier ran a week late</div>
              </div>
            </div>
          </div>
        </GlassCard>
      </motion.div>

      {/* the list */}
      <div className="flex flex-col gap-3">
        {shown.map((item, i) => <ItemCard key={item.id} item={item} delay={i * 0.05} />)}

        {shown.length === 0 && (
          <GlassCard className="border-green/30 p-6 text-sm text-muted">
            Every material has room to slip without moving the handover date. Nothing needs you.
          </GlassCard>
        )}

        {hidden > 0 && (
          <button onClick={() => setShowAll(true)}
            className="self-start text-sm text-faint transition hover:text-amber">
            show the {hidden} that {hidden === 1 ? "is" : "are"} fine too
          </button>
        )}
      </div>
    </div>
  );
}

function ItemCard({ item, delay }: { item: BriefItem; delay: number }) {
  const nav = useNavigate();
  const meta = STATUS[item.status as keyof typeof STATUS] ?? STATUS.fine;
  const Icon = meta.icon;
  const tone = meta.tone;

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: [0.16, 1, 0.3, 1] }}>
      <GlassCard className={cn("p-5", TONE_BORDER[tone])}>
        <div className="flex flex-wrap items-start gap-4">
          <div className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl",
            TONE_BG[tone], TONE_TEXT[tone])}>
            <Icon size={18} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-medium">{item.name}</h3>
              <Badge tone={tone}>{meta.label}</Badge>
              <span className="text-xs text-faint">from {item.supplier}</span>
            </div>

            <p className="mt-1.5 text-sm text-muted">
              <span className={TONE_TEXT[tone]}>{item.slack_text}</span>
              {" · "}status is <b className="text-text">{item.how_sure}</b>
              <span className="text-faint" title={item.based_on}> (based on {item.based_on})</span>
            </p>

            <p className="mt-1 text-sm text-muted">{item.risk_text}</p>

            {item.action !== "Nothing to do." && (
              <p className={cn("mt-2.5 text-sm font-medium", TONE_TEXT[tone])}>→ {item.action}</p>
            )}
          </div>

          <button
            onClick={() => nav(`/dashboard/cascade?slip=${item.id}`)}
            className="flex shrink-0 items-center gap-1 self-center rounded-lg border border-line-strong
              px-3 py-2 text-sm text-text transition hover:border-amber/50 hover:text-amber">
            Try it <ChevronRight size={14} />
          </button>
        </div>
      </GlassCard>
    </motion.div>
  );
}

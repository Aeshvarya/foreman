import {
  FileStack, MessageSquareText, Zap, Activity, Route, Radar,
  ArrowRight, ArrowUpRight,
} from "lucide-react";
import Nav from "../components/Nav";
import HeroGraph from "../components/landing/HeroGraph";
import { Reveal } from "../components/motion";
import { Button, Kicker, GlassCard, Badge } from "../components/primitives";
import { cn } from "../lib/cn";

const CAPS = [
  { icon: FileStack, title: "Builds its own brain from documents",
    body: "Reads the messy POs, supplier emails, GPS feeds and GRNs a real project generates — scores every fact by source reliability and flags conflicts when documents disagree.",
    tag: "Knowledge graph" },
  { icon: MessageSquareText, title: "Ask it anything, in English",
    body: "Writes read-only Cypher against the graph, self-corrects, and answers with citations — and shows every step of its reasoning.",
    tag: "NL → graph" },
  { icon: Zap, title: "Cascade reasoning — the star",
    body: "Real critical-path math. A material slips → it computes which activities break, whether the handover survives, and the cheapest fix. The LLM only narrates; it can't fake a number.",
    tag: "CPM engine", star: true },
  { icon: Activity, title: "Probabilistic schedule risk",
    body: "Models each material's arrival as a distribution scaled by our uncertainty, runs 3,000 futures, and reports the probability the handover slips — and what's driving it.",
    tag: "Monte-Carlo" },
  { icon: Route, title: "Alternate suppliers on disruption",
    body: "Ranks market alternates by capability fit and checks each lead time against the deadline — surfacing the realistic bridge that still hits the required-on-job date.",
    tag: "Recovery" },
  { icon: Radar, title: "Proactive risk radar",
    body: "Finds each material's breaking point — the minimum slip that kills the handover — and crosses it with confidence, so you chase the right vendor today.",
    tag: "Early warning" },
];

const STEPS = [
  { n: "01", t: "Ingest", d: "Documents → a confidence-scored knowledge graph in Neo4j." },
  { n: "02", t: "Reason", d: "LangGraph agents traverse the graph and run CPM cascade math." },
  { n: "03", t: "Answer", d: "Grounded verdicts — what breaks, how sure, what to do — with citations." },
];

const PAPERS = [
  "KG + LLM iterative reasoning (2507.17273)",
  "Helicase — uncertainty-guided KG construction (2605.26835)",
  "Bayesian–Monte-Carlo schedule updating (2605.17608)",
  "GNN supply-network risk (Kosasih & Brintrup)",
];

export default function Landing() {
  return (
    <div className="min-h-screen overflow-clip">
      <Nav />

      {/* ---------------------------------------------------------- HERO */}
      <section className="mx-auto grid max-w-[1200px] grid-cols-1 items-center gap-8 px-6 pb-28 pt-40 lg:grid-cols-[1.05fr_0.95fr] lg:pt-48">
        <div>
          <Kicker className="mb-6">Kaya AI Hackathon · Track: Supply Chain · Team Gozers</Kicker>
          <h1 className="font-display text-[3.4rem] font-bold leading-[0.94] tracking-tight sm:text-7xl">
            The reasoning brain<br />for construction<br />
            <span className="text-amber">supply chains.</span>
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-relaxed text-muted">
            Everyone predicts <em className="text-text not-italic font-medium">if</em> a material
            is late. Foreman predicts <em className="text-text not-italic font-medium">what it
            breaks</em> — which activities slip, whether the handover survives, how sure it is,
            and how to save the date.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Button to="/dashboard">Launch the dashboard <ArrowRight size={16} /></Button>
            <Button href="#brain" variant="ghost">See what it does</Button>
          </div>
          <div className="mt-12 flex flex-wrap gap-x-8 gap-y-3">
            {[["~79%", "avg megaproject overrun"], ["3,000", "futures simulated"], ["100%", "grounded in CPM math"]].map(
              ([v, l]) => (
                <div key={l}>
                  <div className="font-display text-2xl font-bold text-amber">{v}</div>
                  <div className="kicker mt-1">{l}</div>
                </div>
              ))}
          </div>
        </div>
        <div className="relative h-[380px] lg:h-[480px]">
          <div className="absolute inset-0 rounded-2xl" style={{
            background: "radial-gradient(circle at 60% 45%, rgba(245,166,35,0.08), transparent 60%)" }} />
          <HeroGraph />
        </div>
      </section>

      {/* ------------------------------------------------------- PROBLEM */}
      <Section id="problem">
        <Reveal>
          <Kicker className="mb-4">The problem</Kicker>
          <h2 className="max-w-3xl font-display text-3xl font-bold leading-tight sm:text-5xl">
            The moment materials are ordered,<br />
            <span className="text-muted">visibility collapses.</span>
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
            What's approved? What's being fabricated? What's delayed? Answers live in emails,
            calls and disconnected systems — so slippage is caught too late. One late item
            cascades: late steel blocks concrete, which blocks MEP, which moves the handover.
            A dashboard is a warning light. It can't tell you <em className="text-text not-italic">why</em>,
            what else breaks, or how sure it is.
          </p>
        </Reveal>
      </Section>

      {/* --------------------------------------------------------- BRAIN */}
      <Section id="brain">
        <Reveal>
          <Kicker className="mb-4">The reasoning brain</Kicker>
          <h2 className="max-w-3xl font-display text-3xl font-bold leading-tight sm:text-5xl">
            Six capabilities. One grounded system.
          </h2>
        </Reveal>
        <div className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {CAPS.map((c, i) => (
            <Reveal key={c.title} delay={(i % 3) * 0.08}>
              <GlassCard hover className={cn("h-full p-6", c.star && "border-amber/25")}>
                <div className="flex items-center justify-between">
                  <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg border",
                    c.star ? "border-amber/40 bg-amber/10 text-amber" : "border-line bg-white/5 text-steel-bright")}>
                    <c.icon size={19} />
                  </div>
                  <Badge tone={c.star ? "amber" : "steel"}>{c.tag}</Badge>
                </div>
                <h3 className="mt-5 font-display text-lg font-bold leading-snug">{c.title}</h3>
                <p className="mt-2.5 text-sm leading-relaxed text-muted">{c.body}</p>
              </GlassCard>
            </Reveal>
          ))}
        </div>
      </Section>

      {/* ----------------------------------------------------------- HOW */}
      <Section id="how">
        <Reveal>
          <Kicker className="mb-4">How it works</Kicker>
          <h2 className="max-w-3xl font-display text-3xl font-bold leading-tight sm:text-5xl">
            From documents to a decision.
          </h2>
        </Reveal>
        <div className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 0.1}>
              <GlassCard className="h-full p-6">
                <div className="font-mono text-sm text-amber">{s.n}</div>
                <h3 className="mt-3 font-display text-xl font-bold">{s.t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{s.d}</p>
              </GlassCard>
            </Reveal>
          ))}
        </div>
        <Reveal delay={0.2}>
          <div className="mt-4 flex flex-wrap gap-2">
            {PAPERS.map((p) => (
              <span key={p} className="rounded-full border border-line bg-white/[0.02] px-3 py-1 font-mono text-[0.7rem] text-faint">
                {p}
              </span>
            ))}
          </div>
        </Reveal>
      </Section>

      {/* ---------------------------------------------------------- KAYA */}
      <Section id="kaya">
        <Reveal>
          <GlassCard className="relative overflow-hidden p-8 sm:p-12">
            <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full"
              style={{ background: "radial-gradient(circle, rgba(245,166,35,0.12), transparent 70%)" }} />
            <Kicker className="mb-4">Extends Kaya's Amber</Kicker>
            <p className="max-w-3xl font-display text-2xl font-bold leading-snug sm:text-3xl">
              Kaya's Amber tells you <span className="text-muted">where your material is.</span><br />
              Foreman tells you <span className="text-amber">what breaks if it's late</span> — and how to save the date.
            </p>
          </GlassCard>
        </Reveal>
      </Section>

      {/* ---------------------------------------------------------- TEAM */}
      <Section id="team">
        <Reveal>
          <Kicker className="mb-4">Team Gozers · IIT Jodhpur</Kicker>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {[["Aeshvarya Awasthi", "Engine · full-stack + AI"], ["Varunika Rai", "Product · UI + research"]].map(
              ([name, role]) => (
                <GlassCard key={name} className="flex items-center gap-4 p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-amber/30 bg-amber/10 font-display text-lg font-bold text-amber">
                    {name.split(" ").map((w) => w[0]).join("")}
                  </div>
                  <div>
                    <div className="font-display font-bold">{name}</div>
                    <div className="kicker mt-1">{role}</div>
                  </div>
                </GlassCard>
              ))}
          </div>
        </Reveal>
      </Section>

      {/* -------------------------------------------------------- FOOTER */}
      <footer className="mx-auto max-w-[1200px] px-6 pb-16 pt-24">
        <Reveal>
          <div className="rounded-2xl border border-line bg-gradient-to-b from-white/[0.04] to-transparent p-10 text-center sm:p-16">
            <h2 className="font-display text-3xl font-bold sm:text-5xl">See the brain reason.</h2>
            <p className="mx-auto mt-4 max-w-md text-muted">
              Run a delay through the graph and watch the critical path light up.
            </p>
            <div className="mt-8 flex justify-center">
              <Button to="/dashboard">Launch the dashboard <ArrowUpRight size={16} /></Button>
            </div>
          </div>
          <div className="mt-10 flex flex-col items-center justify-between gap-3 text-sm text-faint sm:flex-row">
            <span className="font-mono">FOREMAN · Kaya AI Hackathon 2026</span>
            <span>Aeshvarya Awasthi · Varunika Rai · IIT Jodhpur</span>
          </div>
        </Reveal>
      </footer>
    </div>
  );
}

function Section({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-[1200px] scroll-mt-24 px-6 py-20 sm:py-28">
      {children}
    </section>
  );
}

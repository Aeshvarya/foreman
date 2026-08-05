# Foreman — Judge Q&A

Prepared answers for the questions a judge is most likely to ask, written for
**Round 2 (prototype vs proposal)** and the **Round 3 live final**.

Two rules for every answer here:

1. **Never bluff.** Every judge on the panel builds systems for a living. A
   confident wrong answer is worse than "we didn't build that, here's why."
2. **Lead with the honest sentence, then the reasoning.** If something wasn't
   built, say so in the first five words.

Architecture detail lives in [ARCHITECTURE.md](ARCHITECTURE.md). This file is
only for what to *say*.

---

## The two questions we know we're exposed on

### Q: "You promised integration with a real Kaya data feed. Where is it?"

> We didn't get platform access. We asked for it on 24 July, right after the
> shortlist, and we never received credentials — so we built Foreman to run
> standalone on a synthetic data-center project instead. That was the right call
> either way: nothing in the system assumes a Kaya-shaped input. It reads
> suppliers, materials, dates and a schedule. Point it at a real Amber feed and
> the same brain runs — the ingestion layer already handles messy documents and
> spreadsheets, which is a harder input than a clean API.

**Do not** imply access was promised and withheld. State the date, state what
you built instead, move to the strength.

### Q: "Your proposal said supplier confirmation ranks above the tracking feed. Your code does the opposite."

> Correct, and we changed it deliberately. A GPS ping is harder evidence than a
> supplier telling you what you want to hear. So the hierarchy runs goods-received
> note, then tracking, then supplier confirmation, then a progress report, then
> anything inferred. If a vendor's email conflicts with the carrier's tracking,
> we trust the tracking and we show you both, with the one we rejected.

This is a strength, not an error — but only if you say "deliberately" and can
name the order. **Learn the order.** GRN → tracking/GPS → supplier confirmation →
progress report → PO → verbal → under review → inferred.

---

## On the claims in the proposal

### Q: "You cited a 41%→82% accuracy jump for iterative sub-questions. Did you actually build that?"

> Yes. A question gets classified first — a simple lookup answers straight from
> one Cypher query, but a diagnostic question goes through decomposition: the
> agent breaks it into sub-questions, queries the graph for each, then writes the
> answer from the combined evidence, then self-checks that answer against the
> original question and revises once if something's missing. You can watch all of
> it in the reasoning trace — it's on screen, not hidden.

Demo it live on: *"Why is the handover at risk and which supplier is most
responsible?"* — it decomposes into two sub-questions and the trace shows the
self-check.

### Q: "You cite GNN supply-chain risk research. Is there a GNN in here?"

> No, and we say so in the code. The alternate-supplier recommender is an
> explainable embedding model — capability vectors scored by cosine similarity
> against an ideal profile, with a hard feasibility check on whether the vendor
> can physically make the date. We chose it over a GNN because a link-prediction
> model we couldn't explain to a site manager would have been worse for this
> product, not better, and we had no supply-network training data that wasn't
> synthetic. The research line is the direction, not a claim about the build.

### Q: "Is the cascade real, or is it scripted?"

> It's a real Critical Path Method forward pass. Every activity's earliest start
> honours both its dependencies and its material arrival dates, and we diff the
> delay scenario against the baseline. The proof is that it gives *different*
> answers depending on float: steel slipping 5 days breaks the handover, but the
> switchgear slipping 15 days is absorbed completely. If it were scripted, it
> would break on everything.

### Q: "Where do your rupee figures come from? Did you invent them?"

> They're labelled assumptions and you can edit any of them in the app. Every
> figure says whether it's your number or ours, and each one carries the basis it
> came from — the late-handover penalty default is a typical liquidated-damages
> clause, about 0.5% of contract value per week. Type your real contract number
> in and the whole plan recalculates. And every "this fix buys you N days" is
> measured, not estimated: we apply the fix to the graph and re-run the schedule.

### Q: "How do you know the recovery options are actually cheaper?"

> Because we don't guess the days saved — we re-run CPM with the fix applied and
> take the difference in the handover date. Options that cost more than they save
> show a negative number and rank last. There's one in the demo: site overtime on
> a short delay costs more than the delay does. We show it anyway, because hiding
> it would make the tool a salesman.

---

## On the data

### Q: "Is this real project data?"

> No — it's synthetic, and the app says so on screen. It's modelled on a real
> mission-critical data-centre structure: six suppliers, eight materials, twelve
> schedule activities, with realistic lead times and a deliberate conflict baked
> into the documents so the graph builder has something real to resolve. We'd
> rather demo honest synthetic data than pretend.

### Q: "What happens if I put my own project in?"

> Describe it in a sentence, or upload the spreadsheet you already keep. It'll
> draft the suppliers, materials and the order of work, show you what it
> understood and what it had to assume, and save nothing until you confirm.

---

## On the limits (ask these of yourselves before they do)

- **It doesn't ingest live feeds yet.** Documents and spreadsheets, on demand.
- **Confidence is source-weighted, not learned.** No historical outcome data
  exists to calibrate against — that's the honest ceiling of a prototype.
- **Monte-Carlo uses assumed variance per material**, not fitted distributions.
- **Two people, no construction-industry employment between us.** The domain
  logic came from the research; a real QS would tighten the cost model.

Saying these first is worth more than being caught on them.

---

## Division for the live demo

- **Aeshvarya** — the brain: graph, CPM, cascade, money, agents. Take any
  question about *why a number is what it is*.
- **Varunika** — the product: the flow, the front end, the story, the market
  case. Take any question about *who uses this and why they'd pay*.

If a question lands on the other person's half, hand it over out loud. It reads
as a team that knows its own system, not as hesitation.

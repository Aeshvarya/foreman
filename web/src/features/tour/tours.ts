import type { TourStep } from "./TourProvider";

/** Maps a dashboard route slug -> its tour id, for the sidebar's replay button. */
export const TOOL_TOUR_ID: Record<string, string> = {
  cascade: "cascade",
  radar: "radar",
  ask: "ask",
  build: "build",
};

export const TOURS: Record<string, TourStep[]> = {
  "dashboard-shell": [
    {
      target: "shell-project",
      title: "This is your active project.",
      body: "Every tool below reasons about whichever project is selected here. Switch between projects, or start a brand new one from your own data — no files, no code.",
    },
    {
      target: "shell-tools",
      title: "Four tools, one reasoning brain.",
      body: "Cascade simulates delays, Risk Radar ranks what's most likely to break the handover, Ask Foreman answers in plain English, and Build from Docs turns raw documents into the graph itself.",
    },
    {
      target: "shell-kpis",
      title: "Live counts from the graph.",
      body: "Suppliers, materials, activities, and the dependency edges between them — this updates the moment the graph changes, from any tool.",
    },
  ],

  cascade: [
    {
      target: "cascade-controls",
      title: "Slip a material.",
      body: "Add any material and drag how many days late it runs. Stack several at once — a whole supplier's order slips together in real projects.",
    },
    {
      target: "cascade-graph",
      title: "Watch it propagate.",
      body: "This is the real dependency graph. Delayed materials light up amber, activities that break the handover turn red — you can also click a material here directly to toggle its delay.",
    },
    {
      target: "cascade-verdict",
      title: "The verdict.",
      body: "Does the combined delay actually break the handover date, or does schedule float quietly absorb it? Every number here comes from the CPM math, not a guess.",
    },
    {
      target: "cascade-details",
      title: "What breaks, and the fix.",
      body: "The exact activities that slip, a suggested mitigation, and — if the handover breaks — an alternate supplier that can still meet the required-on-job date.",
    },
  ],

  radar: [
    {
      target: "radar-mc",
      title: "3,000 simulated futures.",
      body: "Every material's arrival is modeled as a range, not a single date — wider when confidence is lower. This is the probability the handover slips across all of them.",
    },
    {
      target: "radar-ranking",
      title: "The silent-killer ranking.",
      body: "Sorted by how close each material is to breaking the handover, weighted by how sure Foreman actually is about its data. Low confidence + low margin = the thing that bites you.",
    },
  ],

  ask: [
    {
      target: "ask-examples",
      title: "Ask in plain English.",
      body: "Try one of these, or type your own — status questions, dependency questions, or a full what-if delay scenario.",
    },
    {
      target: "ask-input",
      title: "It writes its own queries.",
      body: "Ask a reasoning question and Foreman breaks it into smaller ones, checks its own answer against the evidence, and shows you every step in plain English. \"How Foreman worked this out\" sits under each answer — flip on the technical detail to see the actual graph queries it wrote.",
    },
  ],

  build: [
    {
      target: "build-dropzone",
      title: "Drop in a real document.",
      body: "A purchase order, a supplier email, a goods-received note — plain text for now. Foreman doesn't need clean structured data; it reads the messy version.",
    },
    {
      target: "build-doclist",
      title: "This is the corpus for the next build.",
      body: "The demo documents plus anything you add. Uploaded docs are clearly marked, and you can reset back to the demo corpus at any time without losing the originals.",
    },
    {
      target: "build-button",
      title: "Run the pipeline.",
      body: "It extracts facts, scores each one by how trustworthy its source is, and flags it when two documents disagree — lowering confidence instead of guessing. That's what makes the graph auditable, not a black box.",
    },
  ],
};

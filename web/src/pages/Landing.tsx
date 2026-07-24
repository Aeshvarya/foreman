import { Wordmark, Button, Kicker } from "../components/primitives";

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-5">
        <Wordmark />
        <Button to="/dashboard" variant="ghost">Open dashboard</Button>
      </header>
      <section className="mx-auto max-w-[1200px] px-6 pt-24 pb-40">
        <Kicker className="mb-6">Kaya AI Hackathon · Track: Supply Chain</Kicker>
        <h1 className="font-display text-6xl font-bold leading-[0.95] tracking-tight md:text-[5.5rem]">
          The reasoning brain<br />for construction<br />
          <span className="text-amber">supply chains.</span>
        </h1>
        <p className="mt-8 max-w-xl text-lg text-muted">
          Everyone predicts <em>if</em> a material is late. Foreman predicts what it breaks.
        </p>
      </section>
    </div>
  );
}

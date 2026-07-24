import { Wordmark } from "../components/primitives";

export default function Dashboard() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-5">
        <Wordmark />
      </header>
      <div className="mx-auto max-w-[1200px] px-6 py-20 text-muted">
        Dashboard — coming in the next phase.
      </div>
    </div>
  );
}

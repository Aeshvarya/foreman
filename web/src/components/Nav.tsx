import { useEffect, useState } from "react";
import { Wordmark, Button } from "./primitives";
import { cn } from "../lib/cn";

const LINKS = [
  { href: "#problem", label: "Problem" },
  { href: "#brain", label: "The brain" },
  { href: "#how", label: "How it works" },
  { href: "#team", label: "Team" },
];

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 12);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  return (
    <div className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4">
      <nav className={cn(
        "flex w-full max-w-[1560px] items-center justify-between rounded-xl px-5 py-3 transition-all duration-300",
        scrolled ? "glass shadow-panel" : "border border-transparent",
      )}>
        <Wordmark />
        <div className="hidden items-center gap-7 md:flex">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href}
              className="text-sm text-muted transition-colors hover:text-text">{l.label}</a>
          ))}
        </div>
        <Button to="/dashboard" className="!py-2 !px-4">Launch dashboard →</Button>
      </nav>
    </div>
  );
}

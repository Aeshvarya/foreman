import type { CascadeScene } from "./api";

export const SCENE_KEY = "foreman:cascadeScene";
const KEY = SCENE_KEY;

/**
 * Drop any scene left over from a previous page load.
 *
 * The Cascade tool clears its scene on unmount, but a hard navigation or a
 * reload tears the page down without running that cleanup — and sessionStorage
 * survives it. The scene would then still be sitting there on a fresh load of
 * a DIFFERENT tool, so Ask Foreman answered every question in "explain what's
 * on screen" mode and never ran its NL->Cypher pipeline at all. Clearing at
 * boot is safe: Cascade republishes as soon as it mounts.
 *
 * Called once at app startup, before any tool mounts.
 */
export function clearStaleScene(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* sessionStorage unavailable — nothing to clear */
  }
}

/** Read whatever the Cascade tool has published about its live on-screen
 * state, if any (present only while that tool is actually mounted). */
export function readScene(): CascadeScene | undefined {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : undefined;
  } catch {
    return undefined;
  }
}

import type { CascadeScene } from "./api";

export const SCENE_KEY = "foreman:cascadeScene";
const KEY = SCENE_KEY;

/** Read whatever the Cascade tool last published about its live on-screen
 * state, if any (it's cleared on unmount, so this is only ever present while
 * that tool is actually mounted). */
export function readScene(): CascadeScene | undefined {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : undefined;
  } catch {
    return undefined;
  }
}

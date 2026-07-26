# Foreman — working rules

## Git workflow (IMPORTANT — always follow)
- After finishing and verifying each change (a feature, a fix, a meaningful edit — not mid-edit/broken intermediate states), commit and push to `origin/main` immediately. Don't let work sit uncommitted.
- Every commit is co-authored with Varunika, never with Claude:
  ```
  Co-Authored-By: Varunika <b25ph1018@iitj.ac.in>
  ```
- Never add `Co-Authored-By: Claude` — this is Aeshvarya's GitHub, part of his portfolio.
- Stage specific files by path (not `git add -A`/`.`) and review `git status` before committing.
- Verify the change actually works (typecheck / run it / test it) before committing — don't push broken states.

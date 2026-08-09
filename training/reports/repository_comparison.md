# Repository recovery and local-copy comparison

## Formal clone

- Path: `C:/Users/PC/Documents/ChatGPT/Project_SHION/official-main`
- Origin: `https://github.com/gycffyzqpz6436-ctrl/Project_SHION.git`
- Branch: `main`
- HEAD: `d48f0799d530fe1fcbd00176770e908f7236e337`
- Working tree immediately after clone: clean
- Golden and database: present; 200 formal Golden records

## Previous local copy

- Path: `C:/Users/PC/Documents/Project_SHION/Project_SHION-main`
- Not a Git repository (`.git` is absent), so branch, HEAD, remote, divergence,
  staged/unstaged changes, and Git-defined untracked files cannot be determined.
- It contains 29 files versus 79 non-Git files in the formal clone.
- It has no file absent from the formal clone.
- The formal clone has 50 additional files, primarily the complete dataset,
  validator/tests, requirements, and dataset strategy.
- The 29 common paths have different raw SHA-256 values. This comparison treats
  even line-ending changes as different; because the old copy has no commit
  metadata, it cannot identify which differences were intentional local edits.

The old copy was not modified. No pull, reset, checkout, clean, or overwrite was
performed.


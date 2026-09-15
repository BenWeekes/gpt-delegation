# Working in this repo

Guidance for anyone — human or AI — contributing here.

## This repository is PUBLIC

Everything committed is world-readable, permanently, including git history. Before every
commit:

- **No credentials of any kind.** Not in code, not in examples, not in a test fixture. Use
  obvious placeholders (`sk-...OBFUSCATED...`).
- **No private infrastructure**: internal hostnames, internal endpoints, issue-tracker ids,
  private repository names or paths.
- **No unreleased product names or versions.**

A leaked credential must be treated as compromised and rotated — deleting the commit is not
enough, because the history and any fork or cache still hold it.

If you are working on this inside Agora, read `INTERNAL.md` first. It is a symlink to a
private note and is gitignored; never commit it and never copy from it into a public file.

## Scope

A recipe, not a product. Optimise for someone reading it once and reproducing it:

- Small and readable beats complete. Two MCP tools, not ten.
- No API keys required to run it. The weather API is keyless on purpose.
- Every claim in the README must be something you actually observed.

## Verifying

The whole point of the recipe is a claim that is easy to fake: *the conversation stays
responsive while a second model thinks*. That looks fine in a demo and fails in a real call,
so prove it:

- Assert on what was **said** and on the **artefact on disk**, never on "it started".
- A test that still passes when you revert the fix it covers is worth nothing. Break the code
  deliberately and confirm the test fails.
- If something is unverified, say so in the README rather than implying it works.

## Conventions

- Python 3.10+, standard library first.
- Conventional commit subjects (`feat:`, `fix:`, `docs:`).
- Keep `trips/` and any generated output out of git.

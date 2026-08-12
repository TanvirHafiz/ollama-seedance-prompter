# Seedance Prompt Compiler — Project Context

This file is for Claude Code. Read it before making changes so you understand
the architecture, what already exists, and what's left to build.

## What this project is

A local pipeline that turns character/scene reference images + a scene brief
into a Seedance 2.0 video generation prompt, using Ollama models running on
the user's own machine (RTX 3090, 24GB VRAM). No cloud calls, no API keys,
everything local.

The prompt format itself follows a strict rule set (the "Seedance skill") —
section order, shot-count math, timestamp formatting, a mandatory LOGIC RULE
section preventing continuity errors. That rule set is not something to
reinterpret or simplify — treat `references/seedance_guide.md` as the source
of truth and change it only if the user explicitly asks.

## Current state (already built)

```
seedance-ollama/
├── seedance_ollama.py      # two-stage pipeline: vision model describes
│                            # images, writer model applies the guide
├── validate.py              # automated structural checks (non-LLM)
├── references/
│   └── seedance_guide.md    # full prompting rules, loaded verbatim as
│                            # the writer model's system prompt
└── README.md
```

**Pipeline today (two-stage):**
1. `describe_image()` — vision model (`qwen2.5vl:7b` by default) looks at
   each reference image, returns a structured cinematographer-style
   description (age/build/hair/wardrobe, or environment/lighting for
   location shots).
2. `generate_prompt()` — writer model (`qwen3-coder` by default) takes those
   descriptions + the full guide + the user's brief, outputs the final
   Seedance-formatted prompt.

**Known alternative:** single-model setups (`qwen2.5vl:32b`, or the newly
released `muse-glimmer:30b`, which has native vision via a dedicated
perception encoder and is tuned for tool-use/long-context agentic tasks) can
do both stages in one call. Worth supporting as a mode, not a replacement —
quality tradeoffs between one-call and two-call are still being evaluated by
the user, so don't rip out the two-stage path.

## What's next (in rough priority order)

### 1. Model-swappable CLI
Add `--vision-model`, `--writer-model`, and `--single-model` flags to
`seedance_ollama.py`. `--single-model` should skip stage 1 and send images +
guide + brief directly to one model in a single `ollama.chat()` call, so the
user can A/B test `muse-glimmer:30b` against the two-stage `qwen2.5vl` +
`qwen3-coder` setup without editing source.

### 2. Eval harness
Build `eval.py`: takes a folder of past (images, brief, hand-approved gold
prompt) triples, runs the pipeline, scores output two ways:
- Structural: reuse `validate.py`'s checks
- Semantic: a rubric-based LLM-judge call (does SUBJECT match the reference
  image, is shot count within the duration table, does LOGIC RULE actually
  address the specific continuity risks in this scene) — score against the
  gold prompt, not against the guide in the abstract

Store results as CSV or JSON so model swaps can be compared over time, not
just eyeballed.

### 3. Retry/repair loop
When `validate.py` fails, don't regenerate from scratch. Feed the specific
failures back to the writer model with an instruction to apply the guide's
own ITERATION RULES (minimal changes, fix only the broken section). This
mirrors how the user already iterates on prompts by hand — reuse that
pattern instead of inventing a new one.

### 4. Character description caching
Hash each reference image (e.g. sha256 of file bytes). Cache the stage-1
vision description keyed by that hash in a local SQLite or JSON file. Skip
re-running the vision model when the same character image reappears across
scenes — saves compute and keeps descriptions consistent scene to scene,
which matters for the LOGIC RULE section.

### 5. FastAPI wrapper
Wrap the pipeline as a local HTTP endpoint (`POST /generate` accepting
images + brief + duration) so it can be called from other tools instead of
only the CLI. Keep it local-only (bind to 127.0.0.1), no auth needed for a
single-user local tool.

## Conventions to follow

- **No em dashes anywhere** — not in code comments, not in generated prompt
  text, not in this file's own edits. Use commas, periods, or parentheses
  instead.
- Output of the pipeline itself must stay **plain text, no markdown** — that
  rule comes from the Seedance guide and is non-negotiable regardless of
  what changes elsewhere in the codebase.
- Keep `seedance_guide.md` untouched unless the user explicitly asks to
  change prompting rules. It's the spec, not implementation detail.
- Prefer small, testable functions over one large pipeline function —
  `describe_image()` and `generate_prompt()` are already split this way,
  keep extending in that style so `eval.py` can call pieces independently.
- All models run via local Ollama (`ollama.chat()`), no external API calls,
  no API keys anywhere in this codebase.

## Testing

There's no formal test suite yet. Minimum bar for any change: run
`validate.py` against at least one generated prompt before considering a
change done. When you build `eval.py`, that becomes the real regression
check — wire it in as the thing to run before/after model or prompt changes.

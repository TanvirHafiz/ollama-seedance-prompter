# Seedance Prompt Compiler

Turns character/scene reference images + a scene brief into a Seedance 2.0
video generation prompt, using Ollama models running on your own machine.
No cloud calls, no API keys.

## Setup

```bash
pip install ollama pillow
```

Ollama itself must be installed and running, with at least one vision
model (default `qwen2.5vl:7b`) and one writer model (default
`muse-glimmer:latest`) pulled. Any capable local text model works for
the writer stage, it just needs to follow a long, strict formatting
spec well, `qwen2.5vl` also works fine for text-only writing:

```bash
ollama pull qwen2.5vl:7b
ollama pull muse-glimmer
```

Or use a single vision+text model in single-model mode (e.g.
`muse-glimmer:latest`, `qwen2.5vl:32b`).

## GUI

```bash
python gui.py
```

1. Add reference images in the order they should be tagged (`@image_1`,
   `@image_2`, ...).
2. Write the scene brief and set the duration.
3. Pick models, or check "Single-model mode" to send everything to one
   model in a single call.
4. Click Generate. Validate, copy, or save the result.

## CLI

Two-stage (default):

```bash
python seedance_ollama.py --images ref1.jpg ref2.jpg --brief "Two friends meet at a bus stop at dusk." --duration 15 --validate
```

Single-model mode:

```bash
python seedance_ollama.py --images ref1.jpg --brief "..." --duration 10 --single-model muse-glimmer:30b
```

Flags: `--vision-model`, `--writer-model`, `--single-model`, `--output`,
`--brief-file` (read the brief from a file instead of `--brief`).

## Validation

`validate.py` runs non-LLM structural checks (required sections, FORMAT
line, timestamp format, shot contiguity/duration math, no markdown bold,
no `/` separators in shot lines, no "pitch black" language) against a
generated prompt:

```bash
python validate.py output.txt --duration 15
```

## Project layout

```
seedance-ollama/
├── seedance_ollama.py      # two-stage pipeline + CLI
├── validate.py              # structural checks (non-LLM)
├── gui.py                   # Tkinter desktop GUI
├── references/
│   └── seedance_guide.md    # full prompting rules (source of truth)
└── README.md
```

## What's not built yet

- Eval harness (`eval.py`) scoring against hand-approved gold prompts
- Retry/repair loop feeding validate.py failures back to the writer model
- Character description caching (hash reference images, skip re-describing)
- FastAPI wrapper for calling the pipeline from other tools

See the project brief (`seedance prompt compiler.md`, one level up) for
details on each.

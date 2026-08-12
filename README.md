# Ollama Seedance Prompter

A fully local pipeline (and desktop GUI) that turns character/scene
reference images plus a plain-English scene brief into a properly
formatted **Seedance 2.0** video-generation prompt, powered entirely by
[Ollama](https://ollama.com) models running on your own machine.

No cloud calls, no API keys, no accounts. Everything, vision description
and prompt writing, happens on your GPU.

## Why

Seedance 2.0 prompts follow a strict, fairly involved format (section
order, shot-count-to-duration math, timestamp formatting, a mandatory
"LOGIC RULE" section that prevents continuity errors like duplicated
characters or wardrobe drift). Writing that by hand for every scene is
tedious and easy to get subtly wrong. This project automates it: point
it at reference images and describe the scene, and it produces a
prompt that already follows the spec, then checks its own output
against a structural validator.

## How it works

**Two-stage pipeline (default):**

1. **Vision stage** — a vision-capable model (`qwen2.5vl:7b` by
   default) looks at each reference image and writes a structured,
   cinematographer-style description: age/build/hair/wardrobe for
   people, or lighting/mood/sensory detail for locations.
2. **Writer stage** — a text model (`muse-glimmer:latest` by default)
   takes those descriptions, the full Seedance prompting guide, and
   your scene brief, and writes the final prompt, section by section,
   in the exact format Seedance expects.

**Single-model mode** skips stage 1 and sends the reference images,
the guide, and the brief to one vision+text model in a single call
(useful for A/B testing model quality vs. the two-stage setup, e.g.
`muse-glimmer:30b` or `qwen2.5vl:32b`).

Every generated prompt can then be run through `validate.py`, a
non-LLM structural checker that catches the mechanical failure modes
the guide calls out: missing sections, malformed FORMAT lines,
decimal timestamps, markdown creeping into the output, `/` separators
in shot lines, "pitch black" language, non-contiguous shots, and shot
durations that don't add up to the stated total.

## What's in this repo

```
.
├── seedance prompt compiler.md   # original project brief / build spec
└── seedance-ollama/
    ├── seedance_ollama.py         # two-stage pipeline + CLI
    ├── validate.py                 # structural checks (non-LLM)
    ├── gui.py                      # Tkinter desktop GUI
    ├── run_gui.bat                 # Windows launcher (auto-creates venv)
    ├── requirements.txt
    ├── references/
    │   └── seedance_guide.md       # the full Seedance 2.0 prompting rules
    └── README.md                   # detailed usage docs
```

## Quick start (Windows)

1. Install [Ollama](https://ollama.com) and pull the models you want to
   use, e.g.:
   ```bash
   ollama pull qwen2.5vl:7b
   ollama pull muse-glimmer
   ```
2. Double-click [`seedance-ollama/run_gui.bat`](seedance-ollama/run_gui.bat).
   First run creates a `venv`, installs dependencies, and launches the
   GUI. Later runs just launch it.
3. In the GUI: add reference images in the order they should be
   tagged (`@image_1`, `@image_2`, ...), write the scene brief, set
   the duration, pick models (or enable single-model mode), click
   **Generate**. Validate, copy, or save the result.

## Quick start (CLI, any OS)

```bash
cd seedance-ollama
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt

python seedance_ollama.py \
  --images ref1.jpg ref2.jpg \
  --brief "Two friends meet at a bus stop at dusk." \
  --duration 15 \
  --validate
```

See [`seedance-ollama/README.md`](seedance-ollama/README.md) for the
full flag reference, single-model mode, and validator details.

## Status

Built: two-stage pipeline, model-swappable CLI, structural validator,
Tkinter GUI, Windows launcher.

Not yet built (see the project brief for details on each): an eval
harness scoring output against hand-approved gold prompts, a
retry/repair loop that feeds validator failures back to the writer
model, reference-image description caching, and a FastAPI wrapper for
calling the pipeline from other tools.

## License / credit

The Seedance 2.0 prompting rule set in
[`seedance-ollama/references/seedance_guide.md`](seedance-ollama/references/seedance_guide.md)
is © Dan Kieft, used here as the source-of-truth spec the pipeline
targets. All code in this repo is otherwise free to use and modify.

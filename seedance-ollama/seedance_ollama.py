"""Seedance Prompt Compiler, turns reference images + a scene brief into a
Seedance 2.0 video generation prompt using local Ollama models.

Two-stage pipeline (default):
    1. describe_image() - a vision model looks at each reference image and
       returns a structured cinematographer-style description.
    2. generate_prompt() - a writer model takes those descriptions + the
       Seedance guide + the user's brief and writes the final prompt.

Single-model mode (--single-model) skips stage 1 and sends the images,
guide, and brief to one model in a single call.
"""

import argparse
import os
import sys

import ollama

DEFAULT_VISION_MODEL = "qwen2.5vl:7b"
DEFAULT_WRITER_MODEL = "muse-glimmer:latest"
GUIDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "references", "seedance_guide.md")

VISION_SYSTEM_PROMPT = (
    "You are a cinematographer's assistant describing a reference image for "
    "a video generation prompt. Look closely at the image and write a "
    "structured, factual description.\n\n"
    "If the image shows a person: describe approximate age, build, hair "
    "(color, length, style), face and distinguishing features, wardrobe "
    "(specific items, colors, accessories), and overall energy/personality "
    "conveyed by pose and expression.\n\n"
    "If the image shows a location or environment: describe the setting, "
    "time of day, lighting, dominant colors, and any sensory detail that "
    "would matter for filming there.\n\n"
    "Be specific and concrete. Do not invent a backstory. Plain text only, "
    "no markdown."
)


def load_guide(guide_path=GUIDE_PATH):
    with open(guide_path, "r", encoding="utf-8") as f:
        return f.read()


def describe_image(image_path, vision_model=DEFAULT_VISION_MODEL):
    """Run the vision model on a single reference image, return its
    cinematographer-style description as plain text."""
    response = ollama.chat(
        model=vision_model,
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Describe this reference image.",
                "images": [image_path],
            },
        ],
    )
    return response["message"]["content"].strip()


def describe_images(image_paths, vision_model=DEFAULT_VISION_MODEL):
    """Describe each reference image in order, return a list of
    (image_path, description) pairs matching @image_N order."""
    return [(path, describe_image(path, vision_model)) for path in image_paths]


def _build_writer_user_message(descriptions, brief, duration):
    lines = []
    if descriptions:
        lines.append("REFERENCE IMAGE DESCRIPTIONS (in @image_N order):")
        for i, (path, desc) in enumerate(descriptions, start=1):
            lines.append(f"@image_{i} ({os.path.basename(path)}):\n{desc}")
        lines.append("")
    lines.append(f"DURATION: {duration} seconds")
    lines.append("")
    lines.append("SCENE BRIEF:")
    lines.append(brief)
    lines.append("")
    lines.append(
        "Write the full Seedance 2.0 prompt for this scene, following the "
        "guide exactly. Output plain text only, no markdown."
    )
    return "\n".join(lines)


def generate_prompt(descriptions, brief, duration, writer_model=DEFAULT_WRITER_MODEL,
                     guide_text=None):
    """Stage 2: writer model turns image descriptions + brief into the
    final Seedance-formatted prompt."""
    if guide_text is None:
        guide_text = load_guide()
    user_message = _build_writer_user_message(descriptions, brief, duration)
    response = ollama.chat(
        model=writer_model,
        messages=[
            {"role": "system", "content": guide_text},
            {"role": "user", "content": user_message},
        ],
    )
    return response["message"]["content"].strip()


def single_model_generate(image_paths, brief, duration, model, guide_text=None):
    """Single-call mode: one model sees the images, the guide, and the
    brief directly and writes the final prompt itself."""
    if guide_text is None:
        guide_text = load_guide()
    lines = [
        f"DURATION: {duration} seconds",
        "",
        "SCENE BRIEF:",
        brief,
        "",
    ]
    if image_paths:
        tag_lines = [f"@image_{i} is the attached reference image #{i}."
                      for i in range(1, len(image_paths) + 1)]
        lines.append("REFERENCE IMAGES:")
        lines.extend(tag_lines)
        lines.append("")
    lines.append(
        "Write the full Seedance 2.0 prompt for this scene, following the "
        "guide exactly. Output plain text only, no markdown."
    )
    user_message = "\n".join(lines)

    message = {"role": "user", "content": user_message}
    if image_paths:
        message["images"] = image_paths

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": guide_text},
            message,
        ],
    )
    return response["message"]["content"].strip()


def run_pipeline(image_paths, brief, duration, vision_model=DEFAULT_VISION_MODEL,
                  writer_model=DEFAULT_WRITER_MODEL, single_model=None,
                  guide_text=None):
    """Run the full pipeline and return the final prompt text. If
    single_model is set, runs single-call mode with that model."""
    if guide_text is None:
        guide_text = load_guide()

    if single_model:
        return single_model_generate(image_paths, brief, duration, single_model,
                                      guide_text=guide_text)

    descriptions = describe_images(image_paths, vision_model=vision_model)
    return generate_prompt(descriptions, brief, duration, writer_model=writer_model,
                            guide_text=guide_text)


def _read_brief(args):
    if args.brief_file:
        with open(args.brief_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    if args.brief:
        return args.brief
    print("Error: provide --brief or --brief-file", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Compile reference images + a scene brief into a Seedance 2.0 prompt."
    )
    parser.add_argument("--images", nargs="*", default=[],
                         help="Paths to reference images, in @image_N order.")
    parser.add_argument("--brief", help="Scene brief text.")
    parser.add_argument("--brief-file", help="Path to a file containing the scene brief.")
    parser.add_argument("--duration", type=int, required=True,
                         help="Target duration in seconds.")
    parser.add_argument("--vision-model", default=DEFAULT_VISION_MODEL,
                         help=f"Vision model for stage 1 (default: {DEFAULT_VISION_MODEL}).")
    parser.add_argument("--writer-model", default=DEFAULT_WRITER_MODEL,
                         help=f"Writer model for stage 2 (default: {DEFAULT_WRITER_MODEL}).")
    parser.add_argument("--single-model", default=None,
                         help="Skip the two-stage pipeline and use one model for "
                              "everything (images + guide + brief in one call).")
    parser.add_argument("--output", help="Write the prompt to this file instead of stdout.")
    parser.add_argument("--validate", action="store_true",
                         help="Run validate.py's structural checks on the result.")
    args = parser.parse_args()

    brief = _read_brief(args)

    prompt = run_pipeline(
        args.images, brief, args.duration,
        vision_model=args.vision_model,
        writer_model=args.writer_model,
        single_model=args.single_model,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"Wrote prompt to {args.output}")
    else:
        print(prompt)

    if args.validate:
        import validate as validate_module
        issues = validate_module.validate(prompt, args.duration)
        if issues:
            print("\n--- VALIDATION ISSUES ---", file=sys.stderr)
            for issue in issues:
                print(f"- {issue}", file=sys.stderr)
        else:
            print("\n--- VALIDATION: OK ---", file=sys.stderr)


if __name__ == "__main__":
    main()

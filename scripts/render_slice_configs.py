#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from jinja2 import Environment, FileSystemLoader

from fair5gctl.core.slicing import build_slice_specs, DEFAULT_SLICE_COUNT

TEMPLATES_DIR = REPO_ROOT / "configs" / "templates"
RUNTIME_DIR = REPO_ROOT / "configs" / "runtime"
COMPOSE_DIR = REPO_ROOT / "compose-files" / "network-slicing"
SEED_DIR = REPO_ROOT / "open5gs" / "seed"

SHARED_TEMPLATES = ["amf.yaml.j2", "nssf.yaml.j2", "gnb.yaml.j2", "prometheus.yml.j2"]
PER_SLICE_TEMPLATES = {"smf.yaml.j2": "smf{index}.yaml", "upf.yaml.j2": "upf{index}.yaml", "ue.yaml.j2": "ue{index}.yaml"}


def make_env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_all(count, runtime_dir=RUNTIME_DIR, compose_dir=COMPOSE_DIR, seed_dir=SEED_DIR):
    specs = build_slice_specs(count)
    env = make_env()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    written = []

    for template_name in SHARED_TEMPLATES:
        out_name = template_name[:-3]
        content = env.get_template(template_name).render(slices=specs)
        out_path = runtime_dir / out_name
        out_path.write_text(content)
        written.append(out_path)

    for template_name, out_pattern in PER_SLICE_TEMPLATES.items():
        template = env.get_template(template_name)
        for slice_spec in specs:
            content = template.render(slice=slice_spec)
            out_path = runtime_dir / out_pattern.format(index=slice_spec.index)
            out_path.write_text(content)
            written.append(out_path)

    compose_dir.mkdir(parents=True, exist_ok=True)
    compose_content = env.get_template("docker-compose.slices.yml.j2").render(slices=specs)
    compose_path = compose_dir / "docker-compose.slices.generated.yaml"
    compose_path.write_text(compose_content)
    written.append(compose_path)

    seed_dir.mkdir(parents=True, exist_ok=True)
    subscribers_content = env.get_template("subscribers.js.j2").render(slices=specs)
    subscribers_path = seed_dir / "subscribers.generated.js"
    subscribers_path.write_text(subscribers_content)
    written.append(subscribers_path)

    valid_names = {written_path.name for written_path in written if written_path.parent == runtime_dir}
    for out_pattern in PER_SLICE_TEMPLATES.values():
        prefix = out_pattern.split("{index}")[0]
        for stale in runtime_dir.glob(f"{prefix}*.yaml"):
            if stale.name not in valid_names:
                stale.unlink()

    return specs, written


def main():
    parser = argparse.ArgumentParser(description="Renderiza configs de N fatias a partir dos templates Jinja2")
    parser.add_argument(
        "--slices",
        type=int,
        default=int(os.getenv("FAIR5G_SLICE_COUNT", DEFAULT_SLICE_COUNT)),
        help="Quantidade de fatias a provisionar",
    )
    args = parser.parse_args()

    try:
        specs, written = render_all(args.slices)
    except ValueError as e:
        print(f"[ERRO] {e}")
        raise SystemExit(1)

    print(f"[render-slices] {len(specs)} fatia(s) renderizada(s):")
    for spec in specs:
        print(f"  slice {spec.index}: sd={spec.sd_hex} subnet={spec.upf_subnet} imsi={spec.imsi}")
    print(f"[render-slices] {len(written)} arquivo(s) escrito(s).")


if __name__ == "__main__":
    main()

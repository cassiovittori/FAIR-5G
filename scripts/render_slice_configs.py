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
PER_SLICE_TEMPLATES = {"smf.yaml.j2": "smf{index}.yaml", "upf.yaml.j2": "upf{index}.yaml"}
# ue.yaml deixou de ser por fatia: cada UE tem seu proprio arquivo, porque cada
# um precisa de SUPI/IMSI unico. Renderizado no laco dedicado em render_all().
PER_UE_TEMPLATE = ("ue.yaml.j2", "{name}.yaml")


def make_env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_all(count, ues_per_slice=None, runtime_dir=RUNTIME_DIR, compose_dir=COMPOSE_DIR, seed_dir=SEED_DIR):
    specs = build_slice_specs(count, ues_per_slice)
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

    # Um arquivo de configuracao por UE (cada um tem SUPI/IMSI proprio).
    ue_template = env.get_template(PER_UE_TEMPLATE[0])
    for slice_spec in specs:
        for ue in slice_spec.ues:
            content = ue_template.render(slice=slice_spec, ue=ue)
            out_path = runtime_dir / PER_UE_TEMPLATE[1].format(name=ue.name)
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

    # Remove artefatos de execucoes anteriores com outra quantidade de fatias ou
    # de UEs — senao um ue3_2.yaml antigo sobreviveria a uma rodada menor e
    # poderia ser carregado por engano.
    valid_names = {written_path.name for written_path in written if written_path.parent == runtime_dir}
    prefixos = [p.split("{index}")[0] for p in PER_SLICE_TEMPLATES.values()] + ["ue"]
    for prefix in prefixos:
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
    parser.add_argument(
        "--ues-per-slice",
        default=os.getenv("FAIR5G_UES_PER_SLICE") or None,
        help="UEs por fatia: um numero para todas (ex.: 3) ou por fatia (ex.: 3,1)",
    )
    args = parser.parse_args()

    try:
        specs, written = render_all(args.slices, args.ues_per_slice)
    except ValueError as e:
        print(f"[ERRO] {e}")
        raise SystemExit(1)

    print(f"[render-slices] {len(specs)} fatia(s) renderizada(s):")
    for spec in specs:
        ues = ", ".join(f"{u.name}({u.access_ip})" for u in spec.ues)
        print(f"  slice {spec.index}: sd={spec.sd_hex} subnet={spec.upf_subnet} "
              f"ambr={spec.ambr_down_mbps}Mbps(agregado) ues=[{ues}]")
    print(f"[render-slices] {len(written)} arquivo(s) escrito(s).")


if __name__ == "__main__":
    main()

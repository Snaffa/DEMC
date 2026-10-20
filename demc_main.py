"""Build and launch DEMC simulation sweeps.

Usage: python demc_main.py --cluster {bu,polmcad} RUN [RUN ...]
       RUN in: seed, bias, vbd, vbd_seed (executed one after the other, in the given order)
"""

import argparse
import os
import random as rnd
import sys

import numpy as np

from clusters import CLUSTERS
from demc_input_classes import DEMC_CONTINUE_input, DEMC_FF_input, DEMC_MC_input
from demc_launcher import Task, run_tasks

SERVER_DIR = "Projects/MC3D/DEMC"  # folder containing the device folders
DEVICE_DIR = "SPAD_FBK_v2/quasi_1D"

BIAS_CONTACT = "pcontact"
GROUND_CONTACT = "ncontact"
GROUND = "0.0"
POTENTIAL_TYPE = "NATIVE"  # or "WORKFUNCTION"


def build_simulation_template(sim_type: str, initial_file: str | None = None, injection_file: str = "inj_file_py.in"):
    """Return an empty input object of the given type and the base input file name."""
    if sim_type == "MC":
        sim = DEMC_MC_input()
        sim.IIOFFSPRING = 0
    elif sim_type == "CONTINUE":
        sim = DEMC_CONTINUE_input()
        sim.GENERATION_FILE = injection_file
        sim.IIOFFSPRING = 1
        sim.RLC_FILE = "rlc.in"
    elif sim_type == "FF":
        sim = DEMC_FF_input()
        sim.GENERATION_FILE = injection_file
        sim.IIOFFSPRING = 1
    else:
        raise ValueError(f"Unsupported simulation type: {sim_type}")
    if initial_file:
        sim.INITIAL_CONDITIONS = f"{sim_type} {initial_file}"
    return sim, f"demc_{sim_type}"


def configure_simulation_defaults(sim, simulation_dir: str, mesh: str) -> None:
    sim.SIMULATION = simulation_dir
    sim.MESH = mesh
    sim.MATERIAL_INPUT = "Material_fb.in"
    sim.DIMENSIONS = 3
    sim.LENGTH_UNIT = 1.0e-6
    sim.SUPERCHARGE = [-1.0, -1.0]
    sim.TIMER = [3e-10, "CONSTANT", 1e-15]
    sim.ELECTRON = 1_000_000
    sim.HOLE = 1_000_000
    sim.POISSON = ["EVENTS", 2]
    sim.RAMO = ["EVENTS", 8]
    sim.SUBHISTORY_FORMAT = "VTKANDTEXT"
    sim.SUBHISTORY = ["TOTAL", 2]
    sim.CONTACT_POTENTIAL = [f"{GROUND_CONTACT} 0.0 {POTENTIAL_TYPE}", f"{BIAS_CONTACT} 0.0 {POTENTIAL_TYPE}"]
    sim.SEED = 111
    sim.TUNNELING = 0
    sim.SELFFORCES = 0


def contact_potential(bias: float) -> list[str]:
    return [f"{BIAS_CONTACT} {bias:.2f} {POTENTIAL_TYPE}", f"{GROUND_CONTACT} {GROUND} {POTENTIAL_TYPE}"]


def configure_breakdown(sim, bias: float, load_dir: str, efield_index: str) -> None:
    """FF breakdown settings: start from the MC electric field at the same bias, fewer particles, finer dt."""
    sim.INITIAL_CONDITIONS = f"FF {load_dir}-{bias:.2f}V/ElectricField_{efield_index}.txt"
    sim.TIMER = [100e-12, "CONSTANT", 1e-16]  # dt small enough to catch impact ionization
    sim.ELECTRON = 100_000
    sim.HOLE = 100_000
    sim.CONTACT_POTENTIAL = contact_potential(bias)
    sim.SIMULATION += f"-{bias:.2f}V"


def seed_run() -> list[Task]:
    """FF at fixed bias, repeated with random seeds."""
    simulation_dir = "FF/breakdown--15.00V"
    initial_file = "MC/voltage_ramp--15.00V/ElectricField_2.txt"
    seeds = rnd.sample(range(0, 1000), 5)

    tasks = []
    for seed in seeds:
        sim, filename = build_simulation_template("FF", initial_file)
        configure_simulation_defaults(sim, simulation_dir, mesh="active_1")
        sim.SEED = seed
        sim.SIMULATION += f"-s{seed}"
        tasks.append(Task(sim, f"{filename}-s{seed}.in", f"log-s{seed}.txt"))
    return tasks


def bias_run() -> list[Task]:
    """MC bias sweep for each geometry."""
    geometries = [f"deep_implant_{x:.1f}" for x in np.arange(1.0, 1.4, 0.1)]  # folder name = mesh name
    vdc_list = np.linspace(-41, -45, 5).tolist()

    tasks = []
    for geo in geometries:
        for bias in vdc_list:
            sim, filename = build_simulation_template("MC")
            configure_simulation_defaults(sim, f"MC/{geo}/voltage_ramp", mesh=geo)
            sim.CONTACT_POTENTIAL = contact_potential(bias)
            sim.SIMULATION += f"-{bias:.2f}V"
            tasks.append(Task(sim, f"{filename}-{geo}-{bias:.2f}V.in", f"log-{geo}-{bias:.2f}.txt"))
    return tasks


def vbd_run() -> list[Task]:
    """FF bias sweep for breakdown, starting from the bias_run electric fields."""
    simulation_dir = "FF/active_1/breakdown"
    load_dir = "MC/active_1/voltage_ramp"
    vdc_list = [-36, -37]

    tasks = []
    for bias in vdc_list:
        sim, filename = build_simulation_template("FF")
        configure_simulation_defaults(sim, simulation_dir, mesh="active_1")
        configure_breakdown(sim, bias, load_dir, efield_index="2")
        sim.SUBHISTORY = ["PERIOD", 0, 100e-15]
        tasks.append(Task(sim, f"{filename}-{bias:.2f}V.in", f"log-{bias:.2f}.txt"))
    return tasks


def vbd_seed_run() -> list[Task]:
    """FF breakdown for each geometry and bias, repeated with random seeds."""
    geometries = [f"deep_implant_{x:.1f}" for x in np.arange(1.0, 1.4, 0.1)]  # folder name = mesh name
    vdc_list = np.linspace(-41, -45, 5).tolist()
    seeds = rnd.sample(range(0, 1000), 30)

    tasks = []
    for geo in geometries:
        for bias in vdc_list:
            for seed in seeds:
                sim, filename = build_simulation_template("FF", injection_file=f"inj_{geo}.in")
                configure_simulation_defaults(sim, f"FF/{geo}/breakdown", mesh=geo)
                configure_breakdown(sim, bias, f"MC/{geo}/voltage_ramp", efield_index="2")
                sim.SUBHISTORY = ["TOTAL", 2]
                sim.SEED = seed
                sim.SIMULATION += f"-s{seed}"
                tasks.append(Task(sim, f"{filename}-{geo}-{bias:.2f}V-s{seed}.in", f"log-{geo}-{bias:.2f}-s{seed}.txt"))
    return tasks


RUNS = {
    "seed": seed_run,
    "bias": bias_run,
    "vbd": vbd_run,
    "vbd_seed": vbd_seed_run,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cluster", choices=CLUSTERS, required=True)
    parser.add_argument("runs", nargs="+", choices=RUNS)
    args = parser.parse_args()

    cluster = CLUSTERS[args.cluster]
    project_dir = os.path.join(SERVER_DIR, DEVICE_DIR)
    try:
        for name in args.runs:
            print(f"=== {name} run on {args.cluster}")
            run_tasks(RUNS[name](), cluster, project_dir)
    except KeyboardInterrupt:
        sys.exit("Stopped")


if __name__ == "__main__":
    main()

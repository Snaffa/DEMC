from http import server
import subprocess
from tabnanny import check
from demc_input_classes import DEMC_MC_input, DEMC_CONTINUE_input, DEMC_FF_input
import os
from multiprocessing import Pool
import time
import random as rnd
import copy
import numpy as np
from threading import Semaphore
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

SERVERS = {
    'polmcad0': {
        "sem": Semaphore(4),
        "enabled": False,
        "numa_nodes": {
            0 : Semaphore(1),
            1 : Semaphore(1),
            2 : Semaphore(1),
            3 : Semaphore(1),
        }
    },
    'polmcad1': {
        "sem": Semaphore(2),
        "enabled": True,
        "numa_nodes": {
            0 : Semaphore(1),
            1 : Semaphore(1),
        }
    },
    'polmcad2': {
        "sem": Semaphore(1),
        "enabled": True,
        "numa_nodes": {
            0 : Semaphore(1),
        }
    },
    'polmcad6': {
        "sem": Semaphore(1),
        "enabled": True,
        "numa_nodes": {
            0 : Semaphore(1),
        }
    },
    'polmcad7': {
        "sem": Semaphore(1),
        "enabled": False,
        "numa_nodes": {
            0 : Semaphore(1),
        }
    },
    'polmcad8': {
        "sem": Semaphore(4),
        "enabled": True,
        "numa_nodes": {
            0 : Semaphore(1),
            1 : Semaphore(1),
            2 : Semaphore(1),
            3 : Semaphore(1),
        }
    },
}

def assign_job(task):
        # -------------------------------------------------------------------------------------------------- #
        #  function to check if a server is enabled and if a certain numanode is free (semaphore)            #
        # -------------------------------------------------------------------------------------------------- #
    while True:
        for host, s in SERVERS.items():
            if not s.get("enabled", True):
                continue

            server_sem = s["sem"]
            if server_sem.acquire(blocking=False):
                try:
                    for node_id, node_sem in s["numa_nodes"].items():
                        if node_sem.acquire(blocking=False):
                            try:
                                ssh_cmds(task,host,node_id)
                                return  # Task completed, exit the loop
                            finally:
                                    node_sem.release()
                finally:
                    server_sem.release()
        time.sleep(0.2)  # Wait before retrying if no server is available

def ssh_cmds(task,server,node_id):
        # -------------------------------------------------------------------------------------------------- #
        #  function to execute the command already prepared (task) and sent to the correct server - numanode #
        # -------------------------------------------------------------------------------------------------- #
        # Unpack task
        (sim, local_path, ssh_path, filename, log_file) = task
        # build path for input file
        write_path = os.path.join(local_path, filename)
        # build path for log file
        log_path = os.path.join(local_path, log_file)
        # write input file
        with open(write_path, "w") as f:
            f.write(str(sim))
            f.write("\n")
        print(f"Created input file: {write_path}\n")

        # Build remote command as a single string for clarity
        # Use -T to disable pseudo-tty (avoids banner/MOTD in some cases)
        # Redirect simulation output to log file ON THE REMOTE SIDE
        remote_cmd_with_log = (
            f'cd {ssh_path} && '
            f'numactl -N {node_id} -m {node_id} ./MC3D_release DEMC {filename} > {log_file} 2>&1 && '
            f'mv {filename} {log_file} {sim.SIMULATION}'
        )
        cmd = ['ssh', '-T', server, remote_cmd_with_log]
        # # build ssh command: cd to simulation path, run simulation on a numa node, move input and log file to simulation folder (activate mv only if simulation ran successfully)
        # # to better visualize activate "word wrap" (alt+z)
        # cmd = ['ssh', server, 'cd', ssh_path,'&&','numactl', '-N', str(node_id), '-m', str(node_id), './MC3D_release', 'DEMC', filename, '&&', 'mv', filename, log_file, sim.SIMULATION]
        print(f"Running the simulation {sim.SIMULATION} on {server}...\n")
        # # run simulation
        # try:
        #     with open(log_path, 'w') as f:
        #         result = subprocess.run(cmd, check=True, stdout=f, stderr=f)
        #     print(f"Exited with code {result.returncode}\n" )
        # except subprocess.CalledProcessError as e:
        #     # If the command failed, stderr has been written to the log file (if opened). Print a short message.
        #     print("An error occurred while trying to list files.")
        #     print(e)
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Exited with code {result.returncode}\n")
        except subprocess.CalledProcessError as e:
            print(f"Error running simulation: {e}")
            print(f"Remote stderr: {e.stderr}")
        print(f"Moved {filename} file to {sim.SIMULATION}\n")
def build_simulation_template(sim_type: str, txt: str | None) -> tuple[object, str]:
    if sim_type == "MC":
        sim = DEMC_MC_input()
        sim.IIOFFSPRING = 0
        filename = "demc_MC"
    elif sim_type == "CONTINUE":
        sim = DEMC_CONTINUE_input()
        sim.INITIAL_CONDITIONS = f"CONTINUE {txt}" if txt else sim.INITIAL_CONDITIONS
        sim.GENERATION_FILE = "inj_file_py.in"
        sim.IIOFFSPRING = 1
        sim.RLC_FILE = "rlc.in"
        filename = "demc_CONTINUE"
    elif sim_type == "FF":
        sim = DEMC_FF_input()
        sim.INITIAL_CONDITIONS = f"FF {txt}" if txt else sim.INITIAL_CONDITIONS
        sim.GENERATION_FILE = "inj_file_py.in"
        sim.IIOFFSPRING = 1
        filename = "demc_FF"
    else:
        raise ValueError(f"Unsupported simulation type: {sim_type}")
    return sim, filename

def configure_simulation_defaults(sim, simulation_dir: str) -> None:
    sim.SIMULATION = simulation_dir
    sim.THREADS = 9
    sim.MESH = "si1e17_epi1e13_di5e16"
    sim.MATERIAL_INPUT = "Material_fb.in"
    sim.DIMENSIONS = 3
    sim.LENGTH_UNIT = 1.0e-6
    sim.SUPERCHARGE = [-1.0, -1.0]
    sim.TIMER = [3e-10, "CONSTANT", 1e-14]
    sim.ELECTRON = 100_000
    sim.HOLE = 100_000
    sim.POISSON = ["EVENTS", 2]
    sim.RAMO = ["EVENTS", 8]
    sim.SUBHISTORY_FORMAT = "VTKANDTEXT"
    sim.SUBHISTORY = ["TOTAL", 2]
    sim.CONTACT_POTENTIAL = ["ncontact 0.0 NATIVE", "pcontact 0.0 NATIVE"]
    sim.SEED = 111
    sim.TUNNELING = 0
    sim.SELFFORCES = 0
    sim.RLC_FILE = ""

def get_max_concurrent_tasks():
    return sum(len(s["numa_nodes"]) for s in SERVERS.values() if s.get("enabled", True))

def main():
    base_dir = "/mnt/polmcad" # Base directory where server filesystem is mounted
    server_dir = "MonteCarlo/DEMC" # Folder containing device folders
    device_dir = "SPAD_FBK_v2/quasi_1D" # Device folder
    simulation_name = "voltage_ramp" # Name of the simulation

    # Electric field subhistory to load for FF simulations
    load_Efield_index = "2"
    # initial subhistory index for CONTINUE simulations
    load_subhistory_index = "10"

    seed_run = False
    bias_run = True
    vbd_run = False

    local_path = os.path.join(base_dir, server_dir, device_dir)
    ssh_path = os.path.join(server_dir, device_dir)

    if seed_run:
        # build class
        sim, filename = build_simulation_template("MC", None)
        # configure default parameters
        configure_simulation_defaults(sim, simulation_dir)

        seed_low = 0
        seed_high = 1000
        seed_n = 2
        seed_list = rnd.sample(range(seed_low, seed_high), seed_n)
        
        # Build task list (flat)
        all_tasks = []
        
        for seed in seed_list:
            sim_copy = copy.deepcopy(sim)
            sim_copy.SEED = seed
            sim_copy.SIMULATION = sim_copy.SIMULATION + f"-s{seed}"
            filename  = filename+f"-s{seed}.in"
            log_file = f'log-s{seed}.txt'
            task = (
                sim_copy,
                local_path,
                ssh_path,
                filename,
                log_file,
            )

        all_tasks.append(task)
            
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ThreadPoolExecutor(max_workers=get_max_concurrent_tasks()) as ex:
            results = list(ex.map(assign_job, all_tasks))

    if bias_run:
        # check simulation MC
        # build class
        # configure default parameters
        simulation_dir = f"MC/{simulation_name}" # Simulation folder
        # contacts name
        bias_contact = "pcontact"
        ground_contact = "ncontact"
        # bias values
        vdc_list = np.linspace(-35, -10, 26).tolist()  # from 0.5V to 2.0V with 5 points
        # vdc_list = [1.5] 
        ground = "0.0"

        # kind of potential
        bias_potential_type = "NATIVE"  # or "WORKFUNCTION"
        ground_potential_type = "NATIVE"  # or "WORKFUNCTION"
        all_tasks = []

        
        for bias in vdc_list:
            sim, filename = build_simulation_template("MC", None)
            configure_simulation_defaults(sim, simulation_dir)
            # sim_copy = copy.deepcopy(sim)
            sim.CONTACT_POTENTIAL = [f"{bias_contact} {bias:.2f} {bias_potential_type}", f"{ground_contact} {ground} {ground_potential_type}"] 
            sim.SIMULATION = sim.SIMULATION + f"-{bias:.2f}V"
            filename  = filename+f"-{bias:.2f}V.in"
            log_file = f'log-{bias:.2f}.txt'
            task = (
                sim,
                local_path,
                ssh_path,
                filename,
                log_file,
            )

            all_tasks.append(task)
            
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ThreadPoolExecutor(max_workers=get_max_concurrent_tasks()) as ex:
            results = list(ex.map(assign_job, all_tasks))

    if vbd_run:
        # build class
        sim, filename = build_simulation_template("FF", None)
        sim_type = "VBD"
        simulation_dir = f"FF/{simulation_name}" # Simulation folder
        load_dir = f"MC/voltage_ramp" # Load folder for CONTINUE or FF simulations
        # configure default parameters
        configure_simulation_defaults(sim, simulation_dir)
        # change dt to be able to catch impact ionization
        sim.TIMER = [100e-12, "CONSTANT", 1e-15]
        # fix number of particles since we are simulating breakdown
        sim.ELECTRON = 100_000
        sim.HOLE = 100_000
        # increase subhistory frequency
        sim.SUBHISTORY = ["PERIOD", 0, 10e-15]
        # contacts name
        bias_contact = "pcontact"
        ground_contact = "ncontact"
        # bias values
        vdc_list = [-15]  # from 0.5V to 2.0V with 5 points
        # vdc_list = [1.50,2.00,2.5,3.50,4.00]  # from 0.5V to 2.0V with 5 points
        ground = "0.0"

        # kind of potential
        bias_potential_type = "NATIVE"  # or "WORKFUNCTION"
        ground_potential_type = "NATIVE"  # or "WORKFUNCTION"
        all_tasks = []

        
        for bias in vdc_list:
            sim_copy = copy.deepcopy(sim)
            sim_copy.CONTACT_POTENTIAL = [f"{bias_contact} {bias:.2f} {bias_potential_type}", f"{ground_contact} {ground} {ground_potential_type}"] 
            sim_copy.SIMULATION = sim_copy.SIMULATION + f"-{bias:.2f}V"
            # initial condition for FF: load EField subhistory from previous MC sim
            sim_copy.INITIAL_CONDITIONS = "FF " + f"{load_dir}-{bias:.2f}V/ElectricField_{load_Efield_index}.txt"
            # simulation will be stored under FF directory
            filename  = filename+f"-{bias:.2f}V.in"
            log_file = f'log-{bias:.2f}.txt'
            task = (
                sim_copy,
                local_path,
                ssh_path,
                filename,
                log_file,
            )

            all_tasks.append(task)
            
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ThreadPoolExecutor(max_workers=get_max_concurrent_tasks()) as ex:
            results = list(ex.map(assign_job, all_tasks))
            


if __name__ == "__main__":
    main()
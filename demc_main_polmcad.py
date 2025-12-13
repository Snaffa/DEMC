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
        "enabled": False,
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

def assign_job(task,sim_type,init_subhistory=None):
    while True:
        for host, s in SERVERS.items():
            if not s.get("enabled", True):
                continue

            server_sem = s["sem"]
            if server_sem.acquire(blocking=False):
                try:
                    for node_id, node_sem in s["numa_nodes"].items():
                        if node_sem.acquire(blocking=False):
                            if sim_type == 'SEED':
                                try:
                                    seed_func(task,host,node_id)
                                    return
                                finally:
                                    node_sem.release()
                            elif sim_type == 'BIAS':
                                try:
                                    bias_func(task,host,node_id)
                                    return
                                finally:
                                    node_sem.release()
                            elif sim_type == 'VBD':
                                try:
                                    vbd_func(task,host,node_id)
                                    return
                                finally:
                                    node_sem.release()

                finally:
                    server_sem.release()
        time.sleep(0.2)  # Wait before retrying if no server is available
                    
def seed_func(sim,seed,input_path,filename, server ,node_id,):
        sim.SEED = seed 
        sim.SIMULATION = sim.SIMULATION + f"_seed{sim.SEED}"
        filename  = filename+f"_seed{sim.SEED}.in"
        input_path_write = os.path.join(input_path, filename)
        
        with open(input_path_write, "w") as f:
            f.write(str(sim))
            f.write("\n")
        print(f"Created input file: {input_path_write}\n")
        print(f"{str(sim)}\n") 

        # run_cmd = f"numactl -N {node_id} -m {node_id} ./MC3D_release DEMC {filename}"
        ssh_run_cmd = ['ssh',server,'cd',input_path,'&&','ssh',server,'numactl', '-N', str(node_id), '-m', str(node_id), './MC3D_release', 'DEMC', filename]
        print(f"Running {ssh_run_cmd}...\n")
        with open(log_file, 'w') as f:
            p = subprocess.Popen(ssh_run_cmd, stdout=f)
            p.wait()
        print(f"Exited with code {p.returncode}\n" )
        mv_cmd = f"mv {input_path_write} {sim.SIMULATION}"
        ssh_mv_cmd = f"ssh {server} '{mv_cmd}'"
        print(f"Moving input file to simulation directory with command...\n")
        p = subprocess.Popen(ssh_mv_cmd, stdout=subprocess.PIPE)
        p.wait()
        print(f"Moved input file to {sim.SIMULATION}\n")

def bias_func(task,server,node_id,log_file='log.txt'):
        (sim, bias_contact, bias, ground_contact, ground, bias_potential_type, ground_potential_type, local_path, ssh_path, filename) = task
        # sim.CONTACT_POTENTIAL = [f"{bias_contact} {bias} {bias_potential_type}", f"{ground_contact} {ground} {ground_potential_type}"] 
        # sim.SIMULATION = sim.SIMULATION + f"-{bias:.2f}V"
        # filename  = filename+f"-{bias:.2f}V.in"
        write_path = os.path.join(local_path, filename)
        
        with open(write_path, "w") as f:
            f.write(str(sim))
            f.write("\n")
        print(f"Created input file: {write_path}\n")
        # print(f"{str(sim)}\n")

        cmd = ['ssh', server, 'cd', ssh_path,'&&','numactl', '-N', str(node_id), '-m', str(node_id), './MC3D_release', 'DEMC', filename, '&&', 'mv', filename, sim.SIMULATION]
        print(f"Running the simulation {sim.SIMULATION} on {server}...\n")
        log_file=f'log{bias:.2f}.txt'
        try:
            log_path = os.path.join(local_path, log_file)
            with open(log_path, 'w') as f:
                result = subprocess.run(cmd, check=True, stdout=f, stderr=f)
            print(f"Exited with code {result.returncode}\n" )
        except subprocess.CalledProcessError as e:
            # If the command failed, stderr has been written to the log file (if opened). Print a short message.
            print("An error occurred while trying to list files.")
            print(e)
        print(f"Moved {filename} file to {sim.SIMULATION}\n")

def build_simulation_template(sim_type: str, txt: str | None) -> tuple[object, str]:
    if sim_type == "MC":
        sim = DEMC_MC_input()
        sim.IIOFFSPRING = 0
        filename = "demc_MC"
    elif sim_type == "CONTINUE":
        sim = DEMC_CONTINUE_input()
        sim.INITIAL_CONDITIONS = f"CONTINUE {txt}" if txt else sim.INITIAL_CONDITIONS
        sim.GENERATION_FILE = "inj_file_py"
        sim.IIOFFSPRING = 1
        sim.RLC_FILE = "rlc.in"
        filename = "demc_CONTINUE"
    elif sim_type == "FF":
        sim = DEMC_FF_input()
        sim.INITIAL_CONDITIONS = f"FF {txt}" if txt else sim.INITIAL_CONDITIONS
        sim.GENERATION_FILE = "inj_file_py"
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
    sim.SUPERCHARGE = [-1000.0, -1000.0]
    sim.TIMER = [500e-12, "CONSTANT", 1e-13]
    sim.ELECTRON = 1_000_000
    sim.HOLE = 1_000_000
    sim.POISSON = ["EVENTS", 2]
    sim.RAMO = ["EVENTS", 8]
    sim.SUBHISTORY_FORMAT = "VTKANDTEXT"
    sim.SUBHISTORY = ["TOTAL", 2]
    sim.CONTACT_POTENTIAL = ["ncontact 0.0 NATIVE", "pcontact 0.0 NATIVE"]
    sim.SEED = 111
    sim.TUNNELING = 0
    sim.SELFFORCES = 0
    sim.RLC_FILE = ""

def main():
    base_dir = "/mnt/polmcad" # Base directory where server filesystem is mounted
    server_dir = "MonteCarlo/DEMC" # Folder containing device folders
    device_dir = "SPAD_FBK_v2/3D" # Device folder
    simulation_dir = f"MC/voltage_ramp" # Simulation folder

    threads = 10
    seed_run = False
    bias_run = False
    vbd_run = True

    local_path = os.path.join(base_dir, server_dir, device_dir)
    ssh_path = os.path.join(server_dir, device_dir)

    if seed_run:
        sim_type = "SEED"
        # build class
        sim, filename = build_simulation_template("MC", None)
        # configure default parameters
        configure_simulation_defaults(sim, simulation_dir)

        seed_low = 0
        seed_high = 1000
        seed_n = 2
        seed_array = rnd.sample(range(seed_low, seed_high), seed_n)
        
        # Build task list (flat)
        all_tasks = []
        server_task_counts = {s: 0 for s in server_list}
        
        for i, seed in enumerate(seed_array):
            server = server_list[i % len(server_list)]
            sim_copy = copy.deepcopy(sim)
            
            # use per-server local index for NUMA node selection
            server_local_index = server_task_counts[server]
            server_task_counts[server] += 1
            
            task = (sim_copy, seed, local_path, filename, server, node_id)
            all_tasks.append((server, task))

        def _run_seed_with_semaphore(server, task_args):
            """Acquire server semaphore, run task, release semaphore"""
            sem = server_semaphores[server]
            sem.acquire()
            try:
                seed_func(*task_args)
            except Exception as e:
                print(f"Error running seed task on {server}: {e}")
            finally:
                sem.release()

        # Use a thread pool with total slots across all servers
        total_slots = sum(server_slots.values())
        print(f"Starting seed executor with {total_slots} max workers (total NUMA slots)")
        
        with ThreadPoolExecutor(max_workers=total_slots) as ex:
            futures = [ex.submit(_run_seed_with_semaphore, server, task) for server, task in all_tasks]
            for f in futures:
                f.result()

    if bias_run:
        # check simulation MC
        # build class
        sim, filename = build_simulation_template("MC", None)
        sim_type = "BIAS"
        # configure default parameters
        configure_simulation_defaults(sim, simulation_dir)
        # contacts name
        bias_contact = "pcontact"
        ground_contact = "ncontact"
        # bias values
        # vdc_list = np.linspace(-35, -15, 21).tolist()  # from 0.5V to 2.0V with 5 points
        vdc_list = [1]  # from 0.5V to 2.0V with 5 points
        ground = "0.0"

        # kind of potential
        bias_potential_type = "NATIVE"  # or "WORKFUNCTION"
        ground_potential_type = "NATIVE"  # or "WORKFUNCTION"
        all_tasks = []

        
        for i, bias in enumerate(vdc_list):
            sim_copy = copy.deepcopy(sim)
            sim_copy.CONTACT_POTENTIAL = [f"{bias_contact} {bias} {bias_potential_type}", f"{ground_contact} {ground} {ground_potential_type}"] 
            sim_copy.SIMULATION = sim_copy.SIMULATION + f"-{bias:.2f}V"
            filename  = filename+f"-{bias:.2f}V.in"
            task = (
                sim_copy,
                bias_contact,
                bias,
                ground_contact,
                ground,
                bias_potential_type,
                ground_potential_type,
                local_path,
                ssh_path,
                filename,
            )

            all_tasks.append(task)
            
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ThreadPoolExecutor(max_workers=21) as ex:
            results = list(ex.map(lambda task: assign_job(task, sim_type), all_tasks))

    if vbd_run:
        init_subhistory = "2"
        # build class
        sim, filename = build_simulation_template("FF", None)
        sim_type = "VBD"
        # configure default parameters
        configure_simulation_defaults(sim, simulation_dir)
        # contacts name
        bias_contact = "pcontact"
        ground_contact = "ncontact"
        # bias values
        vdc_list = np.linspace(-35, -15, 21).tolist()  # from 0.5V to 2.0V with 5 points
        # vdc_list = [1.50,2.00,2.5,3.50,4.00]  # from 0.5V to 2.0V with 5 points
        ground = "0.0"

        # kind of potential
        bias_potential_type = "NATIVE"  # or "WORKFUNCTION"
        ground_potential_type = "NATIVE"  # or "WORKFUNCTION"
        all_tasks = []

        
        for i, bias in enumerate(vdc_list):
            sim_copy = copy.deepcopy(sim)
            # sim
            task = (
                sim_copy,
                bias_contact,
                bias,
                ground_contact,
                ground,
                bias_potential_type,
                ground_potential_type,
                local_path,
                ssh_path,
                filename,
                init_subhistory,
            )

            all_tasks.append(task)
            
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ThreadPoolExecutor(max_workers=21) as ex:
            results = ex.map(assign_job, (all_tasks,sim_type))
            


if __name__ == "__main__":
    main()
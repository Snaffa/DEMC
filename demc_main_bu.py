import subprocess
from tabnanny import check
from demc_input_classes import DEMC_MC_input, DEMC_CONTINUE_input, DEMC_FF_input
import os
from multiprocessing import Pool
import time
import random as rnd
import copy
import numpy as np
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


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

def bias_func(task,log_file='log.txt'):
        (sim, bias_contact, bias, ground_contact, ground, bias_potential_type, ground_potential_type, local_path, ssh_path, filename, server,node_id) = task
        sim.CONTACT_POTENTIAL = [f"{bias_contact} {bias} {bias_potential_type}", f"{ground_contact} {ground} {ground_potential_type}"] 
        sim.SIMULATION = sim.SIMULATION + f"-{bias:.2f}V"
        filename  = filename+f"-{bias:.2f}V.in"
        write_path = os.path.join(local_path, filename)
        
        with open(write_path, "w") as f:
            f.write(str(sim))
            f.write("\n")
        print(f"Created input file: {write_path}\n")
        # print(f"{str(sim)}\n")

        cmd = ['ssh', server, 'cd', ssh_path,'&&','numactl', '-N', str(node_id), '-m', str(node_id), './MC3D_release', 'DEMC', filename, '&&', 'mv', filename, sim.SIMULATION]
        print(f"Running the simulation f{sim.SIMULATION} on {server}...\n")
        log_file=f'log{bias:.2f}.txt'
        try:
            log_path = os.path.join(local_path, log_file)
            with open(log_path, 'w') as f:
                result = subprocess.run(cmd, check=True, stdout=f, stderr=f)
            print(f"Exited with code {result.returncode}\n" )
        except subprocess.CalledProcessError as e:
            # If the command failed, stderr has been written to the log file (if opened). Print a short message.
            print("An error occurred while trying to list files. See ssh_ls_output.txt for details.")
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
    sim.THREADS = 20
    sim.MESH = "pn"
    sim.MATERIAL_INPUT = "Material_fb.in"
    sim.DIMENSIONS = 3
    sim.LENGTH_UNIT = 1.0e-6
    sim.SUPERCHARGE = [-10.0, -10.0]
    sim.TIMER = [200e-12, "CONSTANT", 1e-15]
    sim.ELECTRON = 1_000_000
    sim.HOLE = 1_000_000
    sim.POISSON = ["EVENTS", 2]
    sim.RAMO = ["EVENTS", 8]
    sim.SUBHISTORY_FORMAT = "VTKANDTEXT"
    sim.SUBHISTORY = ["TOTAL", 10]
    sim.CONTACT_POTENTIAL = ["ncontact 0.0 NATIVE", "pcontact 0.0 NATIVE"]
    sim.SEED = 111
    sim.TUNNELING = 0
    sim.SELFFORCES = 0

def main():
    base_dir = "/mnt/polmcad" # Base directory where server filesystem is mounted
    server_dir = "MonteCarlo/DEMC" # Folder containing device folders
    device_dir = "prove" # Device folder
    simulation_dir = f"IV-R2336" # Simulation folder

    threads = 10
    seed_run = False
    bias_run = True
    # build class
    sim, filename = build_simulation_template("MC", None)

    # configure default parameters
    configure_simulation_defaults(sim, simulation_dir)

    local_path = os.path.join(base_dir, server_dir, device_dir)
    ssh_path = os.path.join(server_dir, device_dir)

    # List servers manually; edit this list depending on available servers
    server_list = [f'ebncsmc{i}' for i in range(1,20)]  # Example server list

    if seed_run:
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
        # contacts name
        bias_contact = "pcontact"
        ground_contact = "ncontact"
        # bias values
        vdc_list = np.linspace(0, 5, 11).tolist()  # from 0.5V to 2.0V with 5 points
        ground = "0.0"
        # kind of potential

        bias_potential_type = "NATIVE"  # or "WORKFUNCTION"
        ground_potential_type = "NATIVE"  # or "WORKFUNCTION"
        
        # Build list of all available slots: (server, numa_node)
        # This flattens server_numa_map into individual slots
        all_slots = []
        
        print(f"Available slots: {all_slots}")
        print(f"Total slots: {len(all_slots)}")

        # Build flat task list with round-robin assignment to SLOTS (not servers)
        all_tasks = []
        flag = 0

        for i, bias in enumerate(vdc_list):
            # Round-robin over slots, not servers
            server = server_list[i% len(server_list)]
            sim_copy = copy.deepcopy(sim)
            
            if not flag:
                node_id = 0 
                flag = 1
            else:
                node_id = 1

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
                server,
                node_id,
            )

            all_tasks.append(task)

        # Total concurrent slots = sum of NUMA nodes across all servers
        total_slots = len(all_slots)
        print(f"Servers: {server_list}")
        print(f"Total concurrent slots: {total_slots}")
        print(f"Total tasks: {len(all_tasks)}")
        
        # Show task distribution
        # from collections import Counter
        # task_dist = Counter(server for server, _ in all_tasks)
        # print(f"Tasks per server: {dict(task_dist)}")
        
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ProcessPoolExecutor(19) as ex:
            ex.map(bias_func, all_tasks, buffersize = 2*len(server_list))
            


if __name__ == "__main__":
    main()
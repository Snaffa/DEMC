import subprocess
from demc_input_classes import DEMC_MC_input, DEMC_CONTINUE_input, DEMC_FF_input
import os
from multiprocessing import Pool
import time
import random as rnd
import copy
import numpy as np
import threading
from concurrent.futures import ThreadPoolExecutor

def choose_numa_node(server: str, task_index: int = 0, server_numa_map: dict | None = None) -> int:
    """
    Choose a NUMA node for a given server using a manual `server_numa_map`.

    The `server_numa_map` may contain either:
    - an integer: the number of nodes available on that server (0..n-1 will be used), or
    - a list/tuple of explicit node ids to allow skipping nodes (e.g. [0,2,4]).

    Selection policy:
    - If explicit list provided: return `nodes[task_index % len(nodes)]`.
    - If integer provided: return `task_index % count`.
    - If missing or invalid: return 0.
    """
    if not server_numa_map or server not in server_numa_map:
        return 0

    mapping = server_numa_map[server]
    # explicit list of node ids
    try:
        if isinstance(mapping, (list, tuple)) and len(mapping) > 0:
            nodes = [int(x) for x in mapping]
            return int(nodes[task_index % len(nodes)])
        # integer count
        numa_count = int(mapping)
        if numa_count < 1:
            return 0
        return int(task_index % numa_count)
    except Exception:
        return 0

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

def bias_func(sim, bias_contact, bias, ground_contact, ground, bias_potential_type, ground_potential_type, local_path, ssh_path, filename, server,node_id,log_file='log.txt'):
        sim.CONTACT_POTENTIAL = [f"{bias_contact} {bias} {bias_potential_type}", f"{ground_contact} {ground} {ground_potential_type}"] 
        sim.SIMULATION = sim.SIMULATION + f"-{bias:.2f}V"
        filename  = filename+f"-{bias:.2f}V.in"
        write_path = os.path.join(local_path, filename)
        
        with open(write_path, "w") as f:
            f.write(str(sim))
            f.write("\n")
        print(f"Created input file: {write_path}\n")
        # print(f"{str(sim)}\n")

        ssh_run_cmd = ['ssh', server, 'cd', ssh_path,'&&','numactl', '-N', str(node_id), '-m', str(node_id), './MC3D_release', 'DEMC', filename]
        print(f"Running {ssh_run_cmd} on {server}...\n")
        log_file=f'log{bias:.2f}.txt'
        try:
            log_path = os.path.join(local_path, log_file)
            with open(log_path, 'w') as f:
                p = subprocess.Popen(ssh_run_cmd, stdout=f, stderr=f)
                p.wait()
            print(f"Exited with code {p.returncode}\n" )
        except subprocess.CalledProcessError as e:
            # If the command failed, stderr has been written to the log file (if opened). Print a short message.
            print("An error occurred while trying to list files. See ssh_ls_output.txt for details.")
            print(e)

        ssh_mv_cmd = ['ssh', server, 'cd', ssh_path, '&&', 'mv', filename, sim.SIMULATION]
        print(f"Moving input file to simulation directory with command...\n")
        p = subprocess.Popen(ssh_mv_cmd, stdout=subprocess.PIPE)
        p.wait()
        print(f"Moved input file to {sim.SIMULATION}\n")

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
    sim.THREADS = 10
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
    # Example: server_list = ['polmcad0', 'polmcad1', 'polmcad2']
    server_list = ['polmcad1','polmcad2','polmcad6','polmcad8']
    # Manual NUMA map: set the number of NUMA nodes for each server here.
    # Edit these values to match your machines. If a server is missing, node 0 is used.
#     server_numa_map = {
#     'polmcad0': 4,            # usa nodes 0..3
#     'polmcad2': [0,2],        # usa solo node 0 e 2 (salta node 1)
#     'polmcad6': [1,3,5],      # usa i nodi 1,3,5
#     'polmcad7': 8,
#     'polmcad8': 4,
# }
    server_numa_map = {
        'polmcad0': [1,2,3],
        'polmcad1': [1],
        'polmcad2': [0],
        'polmcad6': [0],
        'polmcad7': 1,
        'polmcad8': [0,1,2,3],
    }
    if seed_run:
        seed_low = 0
        seed_high = 1000
        seed_n = 2
        seed_array = rnd.sample(range(seed_low, seed_high), seed_n)

        # Calculate how many concurrent slots each server can handle based on NUMA nodes
        server_slots = {}
        for s in server_list:
            mapping = server_numa_map.get(s, 1)
            if isinstance(mapping, (list, tuple)):
                server_slots[s] = len(mapping)
            else:
                server_slots[s] = int(mapping) if mapping > 0 else 1
        
        # Create semaphores to limit concurrent tasks per server
        server_semaphores = {s: threading.Semaphore(server_slots[s]) for s in server_list}
        
        # Build task list (flat)
        all_tasks = []
        server_task_counts = {s: 0 for s in server_list}
        
        for i, seed in enumerate(seed_array):
            server = server_list[i % len(server_list)]
            sim_copy = copy.deepcopy(sim)
            
            # use per-server local index for NUMA node selection
            server_local_index = server_task_counts[server]
            server_task_counts[server] += 1
            node_id = choose_numa_node(server, task_index=server_local_index, server_numa_map=server_numa_map)
            
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
        for s in server_list:
            mapping = server_numa_map.get(s, [0])
            if isinstance(mapping, (list, tuple)):
                for node in mapping:
                    all_slots.append((s, int(node)))
            else:
                for node in range(int(mapping)):
                    all_slots.append((s, node))
        
        print(f"Available slots: {all_slots}")
        print(f"Total slots: {len(all_slots)}")
        
        # Calculate server_slots for semaphores
        server_slots = {}
        for s in server_list:
            mapping = server_numa_map.get(s, 1)
            if isinstance(mapping, (list, tuple)):
                server_slots[s] = len(mapping)
            else:
                server_slots[s] = int(mapping) if mapping > 0 else 1
        
        # Create semaphores: each server can run up to server_slots[s] tasks in parallel
        server_semaphores = {s: threading.Semaphore(server_slots[s]) for s in server_list}
        
        # Build flat task list with round-robin assignment to SLOTS (not servers)
        all_tasks = []
        
        for i, bias in enumerate(vdc_list):
            # Round-robin over slots, not servers
            slot_idx = i % len(all_slots)
            server, node_id = all_slots[slot_idx]
            sim_copy = copy.deepcopy(sim)
            
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
            all_tasks.append((server, task))

        def _run_task_with_semaphore(server, task_args):
            """Acquire server semaphore (limits concurrency per server), run task, release."""
            sem = server_semaphores[server]
            sem.acquire()
            try:
                print(f"[{server}] Starting task on NUMA node {task_args[-1]}")
                bias_func(*task_args)
                print(f"[{server}] Finished task on NUMA node {task_args[-1]}")
            except Exception as e:
                print(f"[{server}] Error: {e}")
            finally:
                sem.release()

        # Total concurrent slots = sum of NUMA nodes across all servers
        total_slots = len(all_slots)
        print(f"Servers: {server_list}")
        print(f"Slots per server: {server_slots}")
        print(f"Total concurrent slots: {total_slots}")
        print(f"Total tasks: {len(all_tasks)}")
        
        # Show task distribution
        from collections import Counter
        task_dist = Counter(server for server, _ in all_tasks)
        print(f"Tasks per server: {dict(task_dist)}")
        
        # Launch all tasks; semaphores ensure each server runs at most N concurrent (N = its NUMA nodes)
        with ThreadPoolExecutor(max_workers=total_slots) as ex:
            futures = [ex.submit(_run_task_with_semaphore, server, task) for server, task in all_tasks]
            for f in futures:
                f.result()

        

if __name__ == "__main__":
    main()
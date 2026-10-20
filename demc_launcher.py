"""Run DEMC simulations in parallel over ssh, one per free (server, NUMA node) slot.

Ctrl+C cancels the queued simulations and kills the ones already running on the servers.
"""

import os
import queue
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from demc_input_classes import DEMCInput


@dataclass
class Task:
    sim: DEMCInput
    filename: str  # input file name
    log_file: str  # simulation stdout/stderr, moved into the simulation folder at the end


def kill_cmd(host: str, pgid: str) -> list[str]:
    return ["ssh", "-T", host, f"kill -TERM -- -{pgid}"]


class RemoteRuns:
    """Process groups of the simulations running on the servers, so that they can be killed on Ctrl+C."""

    def __init__(self):
        self._lock = threading.Lock()
        self._groups = set()  # (host, remote process group id)
        self.stopping = False

    def add(self, host: str, pgid: str) -> None:
        with self._lock:
            self._groups.add((host, pgid))
            stopping = self.stopping
        if stopping:  # started while kill_all was running
            subprocess.run(kill_cmd(host, pgid), start_new_session=True)

    def remove(self, host: str, pgid: str) -> None:
        with self._lock:
            self._groups.discard((host, pgid))

    def kill_all(self) -> None:
        with self._lock:
            self.stopping = True
            groups = list(self._groups)
        print(f"Killing {len(groups)} running simulations")
        kills = [subprocess.Popen(kill_cmd(host, pgid), start_new_session=True) for host, pgid in groups]
        for p in kills:
            p.wait()


def run_simulation(task: Task, host: str, node: int, threads: int, remote_path: str, executable: str, runs: RemoteRuns) -> None:
    """Write the input file, run it on `host` pinned to NUMA `node`, then move input and log into the simulation folder."""
    sim = task.sim
    tag = f"[{host}:{node}]"
    if runs.stopping:
        return
    sim.THREADS = threads  # depends on the server, known only now
    # the first line printed is the remote process group id, used to kill the run;
    # the input file is sent on stdin and written remotely by cat;
    # the mv only happens if the simulation exits successfully
    remote_cmd = (
        f"ps -o pgid= -p $$ && "
        f"cd {remote_path} && "
        f"cat > {task.filename} && "
        f"numactl -N {node} -m {node} {executable} DEMC {task.filename} > {task.log_file} 2>&1 && "
        f"mv {task.filename} {task.log_file} {sim.SIMULATION}"
    )
    print(f"{tag} Running {sim.SIMULATION}")
    # own session: Ctrl+C reaches only this script, which then kills the remote runs itself
    proc = subprocess.Popen(
        ["ssh", "-T", host, remote_cmd],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        proc.stdin.write(f"{sim}\n")
        proc.stdin.close()
    except BrokenPipeError:  # ssh already failed, the error is in stderr
        pass
    pgid = proc.stdout.readline().strip()
    if pgid.isdigit():
        runs.add(host, pgid)
    try:
        stderr = proc.stderr.read()
        proc.wait()
    finally:
        if pgid.isdigit():
            runs.remove(host, pgid)

    if proc.returncode == 0:
        print(f"{tag} Finished {sim.SIMULATION}")
    elif runs.stopping:
        print(f"{tag} Killed {sim.SIMULATION}")
    else:
        print(f"{tag} FAILED {sim.SIMULATION} (exit code {proc.returncode}), see {task.log_file}\n{stderr}")


def run_tasks(tasks: list[Task], cluster: dict, project_dir: str) -> None:
    """Run all tasks, at most one per NUMA node of the cluster at a time. Returns when all are done."""
    remote_path = os.path.join(cluster["remote_root"], project_dir)

    slots = queue.Queue()
    for host, nodes in cluster["servers"].items():
        for node in nodes:
            slots.put((host, node))
    n_slots = slots.qsize()
    if n_slots == 0:
        raise ValueError("No servers enabled in the cluster")

    runs = RemoteRuns()

    def worker(task: Task) -> None:
        host, node = slots.get()
        try:
            threads = cluster.get("threads_per_server", {}).get(host, cluster["threads"])
            run_simulation(task, host, node, threads, remote_path, cluster["executable"], runs)
        except Exception as e:
            print(f"[{host}:{node}] Error on {task.sim.SIMULATION}: {e}")
        finally:
            slots.put((host, node))

    print(f"Launching {len(tasks)} simulations on {n_slots} NUMA nodes")
    with ThreadPoolExecutor(max_workers=n_slots) as ex:
        futures = [ex.submit(worker, task) for task in tasks]
        try:
            for f in futures:
                f.result()
        except KeyboardInterrupt:
            print("\nCtrl+C: cancelling queued simulations and killing the running ones...")
            ex.shutdown(wait=False, cancel_futures=True)
            runs.kill_all()
            raise  # leaving the with block waits for the killed runs to end

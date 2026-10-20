"""Cluster definitions, selected with `python demc_main.py --cluster <name>`.

remote_root: directory on the servers containing SERVER_DIR (input files are written there over ssh)
executable:  DEMC binary, launched from the device directory
threads:     THREADS written in the input file (one simulation per NUMA node)
threads_per_server: optional host -> THREADS, overriding `threads` for those hosts
servers:     host -> NUMA nodes to use, one simulation per node. Comment out a host to disable it.
"""

CLUSTERS = {
    "bu": {
        "remote_root": "/mnt/csmhome2/amudano",
        "executable": "mc3d_d",
        "threads": 19,  # ebncsm1-14
        "threads_per_server": {
            "ebncsm19": 31,
            "ebncsm20": 31,
            "ebncsm21": 31,
        },
        "servers": {
            "ebncsm1": [0, 1],
            "ebncsm2": [0, 1],
            "ebncsm3": [0, 1],
            "ebncsm4": [0, 1],
            "ebncsm5": [0, 1],
            "ebncsm6": [0, 1],
            "ebncsm7": [0, 1],
            "ebncsm8": [0, 1],
            "ebncsm9": [0, 1],
            # "ebncsm10": [0, 1],
            # "ebncsm11": [1],
            # "ebncsm12": [0, 1],
            # "ebncsm13": [0, 1],
            "ebncsm14": [0, 1],
            "ebncsm19": [0, 1, 2, 3],
            "ebncsm20": [0, 1, 2, 3],
            "ebncsm21": [0, 1, 2, 3]
        },
    },
    "polmcad": {
        "remote_root": "~",
        "executable": "./MC3D_release",
        "threads": 10,
        "servers": {
            # "polmcad0": [1, 2, 3],
            "polmcad1": [1],
            "polmcad2": [0],
            "polmcad6": [0],
            # "polmcad7": [0],
            "polmcad8": [0, 1, 2, 3],
        },
    },
}

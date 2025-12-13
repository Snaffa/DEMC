class DEMC_MC_input:
    def __init__(self):
        self.SIMULATION = ""
        self.THREADS = 0
        self.INITIAL_CONDITIONS = "MC"
        self.MESH = ""
        self.MATERIAL_INPUT = ""
        self.DIMENSIONS = 0
        self.LENGTH_UNIT = 0.0
        self.SUPERCHARGE = []
        self.TIMER = {}
        self.ELECTRON = 0
        self.HOLE = 0
        self.POISSON = {}
        self.RAMO = {}
        self.SUBHISTORY_FORMAT = ""
        self.SUBHISTORY = {}
        self.CONTACT_POTENTIAL = []
        self.SEED = 0
        self.TUNNELING = 0
        self.IIOFFSPRING = 0
        self.SELFFORCES = 0

    def __str__(self):
        lines = []
        for k, v in self.__dict__.items():
            if isinstance(v, str) and v == "":
                continue
            if k.upper() == "CONTACT_POTENTIAL" and isinstance(v, list) and v:
                for item in v:
                    lines.append(f"CONTACT_POTENTIAL\t{item}")
                continue
            if isinstance(v, list) and v:
                lines.append(f"{k.upper()}\t{' '.join(str(x) for x in v)}")
                continue
            if isinstance(v, dict) and v:
                dict_str = ' '.join(f"{dk} {dv}" for dk, dv in v.items())
                lines.append(f"{k.upper()}\t{dict_str}")
                continue
            lines.append(f"{k.upper()}\t{v}")
        return "\n".join(lines)

class DEMC_CONTINUE_input:
    def __init__(self):
        self.SIMULATION = ""
        self.THREADS = 0
        self.INITIAL_CONDITIONS = ["CONTINUE", ""]
        self.MESH = ""
        self.MATERIAL_INPUT = ""
        self.DIMENSIONS = 0
        self.LENGTH_UNIT = 0.0
        self.SUPERCHARGE = []
        self.TIMER = {}
        self.ELECTRON = 0
        self.HOLE = 0
        self.POISSON = {}
        self.RAMO = {}
        self.SUBHISTORY_FORMAT = ""
        self.SUBHISTORY = {}
        self.CONTACT_POTENTIAL = []
        self.SEED = 0
        self.TUNNELING = 0
        self.IIOFFSPRING = 0
        self.SELFFORCES = 0
        self.GENERATION_FILE = ""
        self.RLC_FILE = ""
    def __str__(self):
        lines = []
        for k, v in self.__dict__.items():
            if isinstance(v, str) and v == "":
                continue
            if k.upper() == "CONTACT_POTENTIAL" and isinstance(v, list) and v:
                for item in v:
                    lines.append(f"CONTACT_POTENTIAL\t{item}")
                continue
            if isinstance(v, list) and v:
                lines.append(f"{k.upper()}\t{' '.join(str(x) for x in v)}")
                continue
            if isinstance(v, dict) and v:
                dict_str = ' '.join(f"{dk} {dv}" for dk, dv in v.items())
                lines.append(f"{k.upper()}\t{dict_str}")
                continue
            lines.append(f"{k.upper()}\t{v}")
        return "\n".join(lines)

class DEMC_FF_input:
    def __init__(self):
        self.SIMULATION = ""
        self.THREADS = 0
        self.INITIAL_CONDITIONS = ["FF", ""]
        self.MESH = ""
        self.MATERIAL_INPUT = ""
        self.DIMENSIONS = 0
        self.LENGTH_UNIT = 0.0
        self.SUPERCHARGE = []
        self.TIMER = {}
        self.ELECTRON = 0
        self.HOLE = 0
        self.POISSON = {}
        self.RAMO = {}
        self.SUBHISTORY_FORMAT = ""
        self.SUBHISTORY = {}
        self.CONTACT_POTENTIAL = []
        self.SEED = 0
        self.TUNNELING = 0
        self.IIOFFSPRING = 0
        self.SELFFORCES = 0
        self.GENERATION_FILE = ""
    def __str__(self):
        lines = []
        for k, v in self.__dict__.items():
            if isinstance(v, str) and v == "":
                continue
            if k.upper() == "CONTACT_POTENTIAL" and isinstance(v, list) and v:
                for item in v:
                    lines.append(f"CONTACT_POTENTIAL\t{item}")
                continue
            if isinstance(v, list) and v:
                lines.append(f"{k.upper()}\t{' '.join(str(x) for x in v)}")
                continue
            if isinstance(v, dict) and v:
                dict_str = ' '.join(f"{dk} {dv}" for dk, dv in v.items())
                lines.append(f"{k.upper()}\t{dict_str}")
                continue
            lines.append(f"{k.upper()}\t{v}")
        return "\n".join(lines)

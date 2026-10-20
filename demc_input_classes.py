class DEMCInput:
    """Fields common to every DEMC input file. Attribute order is the line order in the file."""

    def __init__(self, initial_conditions: str):
        self.SIMULATION = ""
        self.THREADS = 0
        self.INITIAL_CONDITIONS = initial_conditions
        self.MESH = ""
        self.MATERIAL_INPUT = ""
        self.DIMENSIONS = 0
        self.LENGTH_UNIT = 0.0
        self.SUPERCHARGE = []
        self.TIMER = []
        self.ELECTRON = 0
        self.HOLE = 0
        self.POISSON = []
        self.RAMO = []
        self.SUBHISTORY_FORMAT = ""
        self.SUBHISTORY = []
        self.CONTACT_POTENTIAL = []
        self.SEED = 0
        self.TUNNELING = 0
        self.IIOFFSPRING = 0
        self.SELFFORCES = 0

    def __str__(self):
        lines = []
        for key, value in self.__dict__.items():
            # unset fields are omitted
            if isinstance(value, (str, list)) and not value:
                continue
            if key == "CONTACT_POTENTIAL":
                # one line per contact
                lines += [f"CONTACT_POTENTIAL\t{item}" for item in value]
            elif isinstance(value, list):
                lines.append(f"{key}\t{' '.join(str(x) for x in value)}")
            else:
                lines.append(f"{key}\t{value}")
        return "\n".join(lines)


class DEMC_MC_input(DEMCInput):
    def __init__(self):
        super().__init__("MC")


class DEMC_CONTINUE_input(DEMCInput):
    def __init__(self):
        super().__init__("CONTINUE")
        self.GENERATION_FILE = ""
        self.RLC_FILE = ""


class DEMC_FF_input(DEMCInput):
    def __init__(self):
        super().__init__("FF")
        self.GENERATION_FILE = ""

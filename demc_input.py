import sys
from demc_input_classes import DEMC_MC_input, DEMC_CONTINUE_input, DEMC_FF_input

# Utility: serializza oggetto in formato testo
# (Qui uso __dict__ per semplicità, puoi personalizzare)
def serialize(obj):
    lines = []
    for k, v in obj.__dict__.items():
        # Stampa solo se non "vuoto"
        if isinstance(v, str) and v == "":
            continue
        if isinstance(v, (int, float)) and v == 0:
            continue
        if isinstance(v, (list, dict)) and not v:
            continue
        lines.append(f"{k} {v}")
    return '\n'.join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <sim_type> [key=value ...]")
        print("sim_type: MC, CONTINUE, FF")
        sys.exit(1)
    sim_type = sys.argv[1].upper()
    # Scegli la classe
    if sim_type == "MC":
        obj = DEMC_MC_input()
        fname = "demc_MC.in"
    elif sim_type == "CONTINUE":
        obj = DEMC_CONTINUE_input()
        fname = "demc_CONTINUE.in"
    elif sim_type == "FF":
        obj = DEMC_FF_input()
        fname = "demc_FF.in"
    else:
        print(f"Unknown simulation type: {sim_type}")
        sys.exit(2)
    # Aggiorna attributi da input key=value
    for arg in sys.argv[2:]:
        if '=' in arg:
            key, value = arg.split('=', 1)
            # Prova a convertire value in tipo giusto
            try:
                value = eval(value)
            except:
                pass
            if hasattr(obj, key):
                setattr(obj, key, value)
    # Serializza e scrivi su file
    with open(fname, 'w') as f:
        f.write(serialize(obj))
    print(f"Creato file: {fname}")
    print(serialize(obj))

if __name__ == "__main__":
    main()

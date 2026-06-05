from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from pipeline_template import not_implemented_yet

if __name__ == "__main__":
    not_implemented_yet("train_model", "power_expert")

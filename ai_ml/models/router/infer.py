from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "common"))
from inference_utils import infer_model


if __name__ == "__main__":
    raise SystemExit(infer_model("router"))

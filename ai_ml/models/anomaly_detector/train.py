from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "common"))
from training_utils import train_tensorflow_anomaly_detector


if __name__ == "__main__":
    train_tensorflow_anomaly_detector(Path(__file__).with_name("config.json"))

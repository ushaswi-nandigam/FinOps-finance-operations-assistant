import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.triage.train import train_triage_model

if __name__ == "__main__":
    train_triage_model()

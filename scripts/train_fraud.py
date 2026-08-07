import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.fraud_ml.train import train_fraud_model

if __name__ == "__main__":
    train_fraud_model()

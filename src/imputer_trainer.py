import logging
import pickle
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestRegressor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_imputer(dataset_dir="datasets", model_out="artifacts/sensor_imputer.pkl"):
    ds_path = Path(dataset_dir)
    out_path = Path(model_out)
    
    logger.info(f"Scanning {ds_path} for compressed CSVs...")
    all_files = list(ds_path.glob("compressed_*_whole_df.csv"))
    
    if not all_files:
        logger.error(f"No datasets found in {ds_path}")
        return

    frames = []
    for f in all_files:
        logger.info(f"Loading {f.name}")
        df = pd.read_csv(f, usecols=["HR", "EDA", "TEMP", "BVP"])
        df = df.dropna(subset=["HR", "EDA", "TEMP", "BVP"])
        frames.append(df)

    if not frames:
        logger.error("No valid data frames could be loaded")
        return

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"Combined data shape: {combined.shape}")

    X = combined[["HR"]]
    y = combined[["EDA", "TEMP", "BVP"]]

    logger.info("Training RandomForestRegressor...")
    model = RandomForestRegressor(n_estimators=10, max_depth=10, n_jobs=-1, random_state=42)
    model.fit(X, y)

    logger.info(f"Saving model to {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(model, f)
        
    logger.info("Imputer trained successfully!")

if __name__ == "__main__":
    train_imputer()

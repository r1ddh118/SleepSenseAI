"""Spark MLlib RandomForest model training for sleep risk classification.

IMPORTANT: Uses a USER-LEVEL (not row-level) train/test split.
  - Users U001–U070 → training set (70%)
  - Users U071–U085 → validation set (15%)
  - Users U086–U100 → test set (15%)

No user appears in more than one partition. This prevents data leakage
from longitudinal correlations within the same user's history.

This methodology is explicitly stated in all evaluation reports and API responses.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.feature import VectorAssembler
from pyspark.sql import functions as F

from spark.spark_session import create_spark_session

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "sleep_efficiency",
    "sleep_duration_hours",
    "n3_fraction",
    "rem_fraction",
    "wake_fraction",
    "avg_hr",
    "hr_std",
    "avg_movement",
    "event_rate",
    "caffeine",
    "screen_time",
    "stress_level",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
PARQUET_PATH = REPO_ROOT / "data" / "parquet"
MODEL_PATH = REPO_ROOT / "models" / "sleep_risk_rf"


def load_training_data(spark):
    """Load aggregated Parquet analytics table."""
    if not PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"Parquet analytics table not found at {PARQUET_PATH}. "
            "Run: python scripts/run_spark_pipeline.py first."
        )
    df = spark.read.parquet(str(PARQUET_PATH))

    # Create binary label: 1 = HIGH risk, 0 = otherwise
    df = df.withColumn(
        "label",
        F.when(F.col("risk_level") == "HIGH", 1).otherwise(0).cast("double"),
    )

    # Fill nulls in feature columns
    for col in FEATURE_COLS:
        if col in df.columns:
            df = df.fillna({col: 0.0})

    return df


def user_level_split(df):
    """Split by user_id — USER-LEVEL split (no data leakage between users).

    Train:  users 001–070
    Val:    users 071–085
    Test:   users 086–100
    """
    def user_num(uid: str) -> int:
        try:
            return int(uid.replace("U", ""))
        except ValueError:
            return 0

    from pyspark.sql.types import IntegerType
    extract_num = F.udf(lambda uid: user_num(uid), IntegerType())
    df = df.withColumn("user_num", extract_num(F.col("user_id")))

    train = df.filter(F.col("user_num") <= 70)
    val   = df.filter((F.col("user_num") > 70) & (F.col("user_num") <= 85))
    test  = df.filter(F.col("user_num") > 85)

    return train, val, test


def build_pipeline():
    """Build ML pipeline: VectorAssembler → RandomForestClassifier."""
    # Only use columns that actually exist in our feature set
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS,
        outputCol="features",
        handleInvalid="keep",
    )
    rf = RandomForestClassifier(
        featuresCol="features",
        labelCol="label",
        predictionCol="prediction",
        probabilityCol="probability",
        numTrees=100,
        maxDepth=8,
        seed=42,
    )
    return Pipeline(stages=[assembler, rf])


def train():
    spark = create_spark_session("SleepSenseAI-MLlib-Train")
    try:
        logger.info("Loading training data from %s", PARQUET_PATH)
        df = load_training_data(spark)

        total = df.count()
        logger.info("Total rows for training: %d", total)

        train_df, val_df, test_df = user_level_split(df)
        logger.info(
            "User-level split: train=%d rows, val=%d rows, test=%d rows",
            train_df.count(), val_df.count(), test_df.count(),
        )

        # Filter to available feature columns
        available_features = [c for c in FEATURE_COLS if c in df.columns]
        if len(available_features) < len(FEATURE_COLS):
            logger.warning(
                "Some feature columns missing: %s",
                set(FEATURE_COLS) - set(available_features),
            )

        pipeline = build_pipeline()
        logger.info("Training RandomForestClassifier...")
        model = pipeline.fit(train_df)

        # Save model
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        model.write().overwrite().save(str(MODEL_PATH))
        logger.info("Model saved to %s", MODEL_PATH)

        return model, val_df, test_df

    finally:
        spark.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    model, val_df, test_df = train()
    print(f"✅ Model trained and saved to {MODEL_PATH}")
    print(f"   Use: python ml/evaluate.py")

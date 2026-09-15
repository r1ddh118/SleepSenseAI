"""MLlib model evaluation with user-level train/test split methodology statement.

EVALUATION METHODOLOGY (explicitly stated):
  This evaluation uses a USER-LEVEL split:
  - Training users: U001–U070
  - Validation users: U071–U085
  - Test users: U086–U100
  
  NO USER appears in both training and test sets. This prevents longitudinal
  data leakage where patterns from one user's night 1 could inform their night 60.
  Row-level splitting would be incorrect for this dataset type.

  Metrics are reported on the held-out test set (users 86–100) only.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.ml import PipelineModel
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.sql import functions as F

from ml.train_spark_model import FEATURE_COLS, MODEL_PATH, PARQUET_PATH, load_training_data, user_level_split
from spark.spark_session import create_spark_session

logger = logging.getLogger(__name__)

SPLIT_METHODOLOGY = (
    "USER-LEVEL TRAIN/TEST SPLIT — Users U001-U070 train, U071-U085 validation, U086-U100 test. "
    "No user appears in both training and test sets. "
    "This prevents longitudinal data leakage within-user across nights."
)


def evaluate():
    if not MODEL_PATH.exists():
        print("❌ Model not found. Run: python ml/train_spark_model.py first")
        sys.exit(1)

    spark = create_spark_session("SleepSenseAI-MLlib-Evaluate")
    try:
        logger.info("Loading model from %s", MODEL_PATH)
        model = PipelineModel.load(str(MODEL_PATH))

        df = load_training_data(spark)
        _, val_df, test_df = user_level_split(df)

        print(f"\n{'='*60}")
        print("SleepSense AI MLlib Model Evaluation")
        print(f"{'='*60}")
        print(f"\n⚠️  METHODOLOGY: {SPLIT_METHODOLOGY}\n")

        for split_name, split_df in [("Validation (U071-U085)", val_df), ("Test (U086-U100)", test_df)]:
            if split_df.count() == 0:
                print(f"⚠️  No data for {split_name} — skipping")
                continue

            predictions = model.transform(split_df)

            # Binary evaluation
            binary_eval = BinaryClassificationEvaluator(
                labelCol="label",
                rawPredictionCol="rawPrediction",
                metricName="areaUnderROC",
            )
            auc = binary_eval.evaluate(predictions)

            # Multi-class (accuracy, precision, recall, F1)
            mc_eval = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction")
            accuracy  = mc_eval.setMetricName("accuracy").evaluate(predictions)
            f1        = mc_eval.setMetricName("f1").evaluate(predictions)
            precision = mc_eval.setMetricName("weightedPrecision").evaluate(predictions)
            recall    = mc_eval.setMetricName("weightedRecall").evaluate(predictions)

            n_users = split_df.select("user_id").distinct().count()
            n_rows = split_df.count()

            print(f"{'─'*40}")
            print(f"Split: {split_name}")
            print(f"  Users: {n_users} | Rows: {n_rows}")
            print(f"  AUC-ROC:   {auc:.4f}")
            print(f"  Accuracy:  {accuracy:.4f}")
            print(f"  F1:        {f1:.4f}")
            print(f"  Precision: {precision:.4f}")
            print(f"  Recall:    {recall:.4f}")
            if auc > 0.995:
                print("  ⚠️  AUC is suspiciously high — check for data leakage")

        print(f"\n{'='*60}")
        print("NOTE: These metrics are on SYNTHETIC data and not representative")
        print("of clinical real-world performance. Model not clinically validated.")
        print(f"{'='*60}\n")

    finally:
        spark.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evaluate()

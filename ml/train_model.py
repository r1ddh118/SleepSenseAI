"""SleepSense AI - Model Training Pipeline"""

import json
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, AdaBoostClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

class SleepModelTrainer:
    def __init__(self):
        self.models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'extra_trees': ExtraTreesClassifier(n_estimators=100, random_state=42),
            'logistic_regression': LogisticRegression(max_iter=1000, random_state=42),
            'adaboost': AdaBoostClassifier(random_state=42),
            'knn': KNeighborsClassifier(n_neighbors=5),
            'mlp_neural_net': MLPClassifier(max_iter=500, random_state=42),
        }

    def train_and_evaluate(self, df: pd.DataFrame, target_col: str = 'risk_label') -> dict:
        feature_cols = [c for c in df.columns if c != target_col and df[c].dtype in [np.float64, np.int64, float, int]]
        X = df[feature_cols].fillna(0)
        y = df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

        metrics_list = []
        trained_models = {}

        for name, model in self.models.items():
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            probs = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else preds

            acc = float(accuracy_score(y_test, preds))
            f1 = float(f1_score(y_test, preds, average='weighted', zero_division=0))
            prec = float(precision_score(y_test, preds, average='weighted', zero_division=0))
            rec = float(recall_score(y_test, preds, average='weighted', zero_division=0))

            metrics_list.append({
                'model_name': name,
                'accuracy': acc,
                'f1_score': f1,
                'precision': prec,
                'recall': rec
            })
            trained_models[name] = model

        leaderboard = pd.DataFrame(metrics_list).sort_values(by='f1_score', ascending=False)
        best_model_name = leaderboard.iloc[0]['model_name']
        best_model = trained_models[best_model_name]

        return {
            'best_model_name': best_model_name,
            'best_model': best_model,
            'leaderboard': leaderboard,
            'feature_columns': feature_cols
        }

def run_training_pipeline(csv_path: str = 'data/synthetic/sleep_observations.csv', out_dir: str = 'ml'):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if Path(csv_path).exists():
        df = pd.read_csv(csv_path, nrows=5000)
        df['risk_label'] = (df['heart_rate'] > 75).astype(int)
    else:
        # Create synthetic training set
        np.random.seed(42)
        n = 1000
        df = pd.DataFrame({
            'sleep_efficiency': np.random.uniform(0.6, 0.98, n),
            'heart_rate': np.random.uniform(50, 95, n),
            'n3_fraction': np.random.uniform(0.05, 0.30, n),
            'rem_fraction': np.random.uniform(0.10, 0.30, n),
            'wake_fraction': np.random.uniform(0.02, 0.25, n),
            'screen_time': np.random.uniform(0, 180, n),
            'stress_level': np.random.uniform(1, 10, n),
            'risk_label': np.random.choice([0, 1], size=n, p=[0.7, 0.3])
        })

    trainer = SleepModelTrainer()
    results = trainer.train_and_evaluate(df, target_col='risk_label')

    # Save artifacts
    results['leaderboard'].to_csv(out_path / 'model_leaderboard.csv', index=False)
    with open(out_path / 'best_model.pkl', 'wb') as f:
        pickle.dump({
            'model_name': results['best_model_name'],
            'model': results['best_model'],
            'feature_columns': results['feature_columns']
        }, f)

    summary = {
        'best_model': results['best_model_name'],
        'accuracy': float(results['leaderboard'].iloc[0]['accuracy']),
        'f1_score': float(results['leaderboard'].iloc[0]['f1_score']),
        'total_samples': len(df),
        'features_used': results['feature_columns']
    }
    with open(out_path / 'training_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Training complete. Best model: {results['best_model_name']} (F1: {summary['f1_score']:.4f})")
    return summary

if __name__ == '__main__':
    run_training_pipeline()

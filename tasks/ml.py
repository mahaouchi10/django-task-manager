import math
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeRegressor

from .models import Task

MIN_SAMPLES = 5

# Bump this anytime the encoding or the training pipeline changes:
# existing persisted models are then automatically retrained on next predict.
MODEL_VERSION = 2

MODEL_NAMES = {
    'linear': 'Régression linéaire',
    'tree': 'Arbre de décision',
}

# Folder where serialized models (one per user) are stored.
ML_MODEL_DIR = Path(__file__).resolve().parent / 'ml_models'
ML_MODEL_DIR.mkdir(exist_ok=True)


def _model_path(user_id):
    return ML_MODEL_DIR / f"model_user_{user_id}.joblib"


def _to_dataframe(user):
    rows = []
    tasks = Task.objects.filter(
        user=user, status=Task.Status.DONE, completed_at__isnull=False
    )
    for t in tasks:
        days = t.duration_days()
        if days is not None:
            rows.append({
                'category': t.category,
                'priority': t.priority,
                'complexity': t.complexity,
                'duration': days,
            })
    return pd.DataFrame(rows)


def _prepared_columns():
    categories = [c[0] for c in Task.Category.choices]
    priorities = [p[0] for p in Task.Priority.choices]
    cols = []
    for c in categories[1:]:
        cols.append(f'category_{c}')
    for p in priorities[1:]:
        cols.append(f'priority_{p}')
    return cols + ['complexity']


def _encode(df):
    X = pd.get_dummies(df[['category', 'priority']], drop_first=False, dtype=int)
    X = X.reindex(columns=_prepared_columns(), fill_value=0)
    X['complexity'] = df['complexity'].astype(float).values
    return X


def train_best_model(user):
    """Train the best model for ``user`` and persist it on disk via joblib."""
    df = _to_dataframe(user)
    if len(df) < MIN_SAMPLES:
        return None

    X = _encode(df)
    y = df['duration'].values
    n = len(df)
    cv = 3 if n >= 12 else 2

    # Keep track of mean complexity to allow a simple heuristic
    # when the training set lacks variation in features.
    mean_complexity = float(X['complexity'].mean()) if 'complexity' in X.columns else 1.0

    # Detect a training set with no informative signal: either the
    # features are basically constant, or every completed task took
    # exactly the same time (constant target). In both cases any
    # learned model would just output a constant, so we persist a
    # small bundle enabling a lightweight, responsive heuristic.
    non_complex_cols = X.drop(columns=['complexity'], errors='ignore')
    has_variation = (
        (non_complex_cols.nunique().sum() > 0 or X['complexity'].nunique() > 1)
        and len(np.unique(y)) > 1
    )

    candidates = {
        'linear': LinearRegression(),
        'tree': DecisionTreeRegressor(random_state=42, max_depth=5, min_samples_leaf=2),
    }

    results = {}
    for name, model in candidates.items():
        try:
            scores = cross_val_score(model, X, y, cv=cv, scoring='r2')
            results[name] = (model, float(scores.mean()))
        except Exception:
            results[name] = (model, float('-inf'))

    best_name = max(results, key=lambda k: results[k][1])
    best_model, _ = results[best_name]
    if not has_variation:
        # Features or target constant: create a constant bundle (no trained model)
        bundle = {
            'model': None,
            'columns': X.columns.tolist(),
            'version': MODEL_VERSION,
            'name': 'constant',
            'label': 'Constante (pas assez de variation)',
            'rmse': 0.0,
            'r2': 1.0,
            'samples': n,
            'mean_duration': round(float(y.mean()), 2),
            'mean_complexity': round(mean_complexity, 2),
            'insufficient_features': True,
        }

        path = _model_path(user.id)
        joblib.dump(bundle, path)
        bundle['trained_at'] = os.path.getmtime(path)
        return bundle

    best_model.fit(X, y)

    y_pred = best_model.predict(X)
    rmse = float(math.sqrt(mean_squared_error(y, y_pred)))
    r2 = float(r2_score(y, y_pred))

    bundle = {
        'model': best_model,
        'columns': X.columns.tolist(),
        'version': MODEL_VERSION,
        'name': best_name,
        'label': MODEL_NAMES[best_name],
        'rmse': round(rmse, 2),
        'r2': round(r2, 3),
        'samples': n,
        'mean_duration': round(float(y.mean()), 2),
        'mean_complexity': round(mean_complexity, 2),
        'insufficient_features': False,
    }

    path = _model_path(user.id)
    joblib.dump(bundle, path)
    bundle['trained_at'] = os.path.getmtime(path)
    return bundle


def _needs_retrain(user):
    """Return True when the persisted model must be retrained."""
    path = _model_path(user.id)
    if not path.exists():
        return True
    df = _to_dataframe(user)
    if len(df) < MIN_SAMPLES:
        return False
    try:
        bundle = joblib.load(path)
        return (
            bundle.get('version') != MODEL_VERSION
            or bundle.get('samples') != len(df)
        )
    except Exception:
        return True


def predict_duration(user, category, priority, complexity):
    """Predict the completion duration (in days).

    Uses a persisted model (one per user) when available, retraining only
    when the underlying dataset has changed.
    """
    if _needs_retrain(user):
        train_best_model(user)

    path = _model_path(user.id)
    # Not enough data or training failed / impossible.
    if not path.exists():
        df_len = len(_to_dataframe(user))
        return {
            'predicted_days': None,
            'samples': df_len,
            'insufficient': True,
        }

    bundle = joblib.load(path)

    # If the persisted bundle indicates there was no informative
    # variation in the training set, fall back to a simple heuristic
    # that scales the mean duration by the ratio of requested
    # complexity to the mean complexity observed in the training set.
    if bundle.get('model') is None or bundle.get('insufficient_features'):
        mean_complexity = float(bundle.get('mean_complexity', 1.0)) or 1.0
        mean_duration = float(bundle.get('mean_duration', 0.0))
        try:
            prediction = max(0.0, mean_duration * (float(complexity) / mean_complexity))
        except Exception:
            prediction = max(0.0, mean_duration)

        return {
            'predicted_days': round(prediction, 2),
            'model': bundle.get('name', 'constant'),
            'model_label': bundle.get('label', 'Constante'),
            'rmse': bundle.get('rmse', 0.0),
            'r2': bundle.get('r2', 0.0),
            'samples': bundle.get('samples', 0),
            'mean_duration': bundle.get('mean_duration', None),
            'insufficient': False,
            'insufficient_features': True,
        }

    row = pd.DataFrame([{
        'category': category,
        'priority': priority,
        'complexity': float(complexity),
    }])
    X_new = _encode(row).reindex(columns=bundle['columns'], fill_value=0)

    prediction = float(max(0.0, bundle['model'].predict(X_new)[0]))

    return {
        'predicted_days': round(prediction, 2),
        'model': bundle['name'],
        'model_label': bundle['label'],
        'rmse': bundle['rmse'],
        'r2': bundle['r2'],
        'samples': bundle['samples'],
        'mean_duration': bundle['mean_duration'],
        'insufficient': False,
    }

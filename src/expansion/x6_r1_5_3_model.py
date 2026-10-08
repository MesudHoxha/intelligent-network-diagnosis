"""Fixed development-only preprocessing, model and hybrid policy."""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from src.expansion.x6_r1_5_3_dataset import model_matrix
from src.orchestration.x6_r1_5_1_contract import canonical, digest, require
from src.orchestration.x6_r1_5_3_contract import FEATURES

PARAMETERS = {
    "penalty": "l2", "solver": "liblinear", "C": 1.0, "dual": False,
    "fit_intercept": True, "intercept_scaling": 1.0, "class_weight": None,
    "tol": 1e-10, "max_iter": 1000, "random_state": 20260925,
    "warm_start": False, "n_jobs": None, "verbose": 0, "l1_ratio": None,
}


def fit(rows, development_inventory_sha256, source_identity):
    import platform,importlib.metadata
    required={"python":"3.12.3","numpy":"2.5.1","scikit_learn":"1.7.2","joblib":"1.5.3"}
    actual={"python":platform.python_version(),"numpy":np.__version__,"scikit_learn":importlib.metadata.version("scikit-learn"),"joblib":importlib.metadata.version("joblib")}
    require(actual==required,"accepted model dependencies differ")
    x, y = model_matrix(rows); x = np.asarray(x, dtype=np.float64); y = np.asarray(y, dtype=np.int64)
    require(len(x) >= 48 and sum(y == 0) >= 24 and sum(y == 1) >= 24, "insufficient development data")
    mean = x.mean(axis=0); variance = ((x - mean) ** 2).mean(axis=0); scale = np.sqrt(variance); scale[scale == 0] = 1.0
    z = (x - mean) / scale
    estimator = LogisticRegression(**PARAMETERS)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        estimator.fit(z, y)
    require(not any(issubclass(item.category, ConvergenceWarning) for item in caught), "model convergence warning")
    require(int(estimator.n_iter_[0]) < PARAMETERS["max_iter"] and estimator.classes_.tolist() == [0, 1], "model convergence/classes")
    numbers = np.concatenate([mean, variance, scale, estimator.coef_.ravel(), estimator.intercept_.ravel()])
    require(np.isfinite(numbers).all(), "non-finite model")
    artifact = {
        "schema_version": 1, "method": "L2_REGULARIZED_BINARY_LOGISTIC_REGRESSION",
        "feature_order": list(FEATURES), "development_inventory_sha256": development_inventory_sha256,
        "source_identity": source_identity, "dependencies": actual,
        "scaler": {"n": len(x), "mean_hex": [v.hex() for v in mean], "variance_hex": [v.hex() for v in variance], "scale_hex": [v.hex() for v in scale]},
        "classes": [0, 1], "coefficient_hex": [v.hex() for v in estimator.coef_[0]], "intercept_hex": estimator.intercept_[0].hex(),
        "parameters": PARAMETERS, "n_iter": int(estimator.n_iter_[0]),
    }
    artifact["model_sha256"] = digest(canonical(artifact))
    expected = probabilities(artifact, x.tolist())
    actual = estimator.predict_proba(z)[:, 1].tolist()
    require([v.hex() for v in expected] == [v.hex() for v in actual], "model serialization round trip")
    artifact["development_probability_hex"] = [v.hex() for v in expected]
    return artifact


def probabilities(artifact, matrix):
    require(artifact["feature_order"] == list(FEATURES), "model feature order")
    x = np.asarray(matrix, dtype=np.float64)
    mean = np.asarray([float.fromhex(v) for v in artifact["scaler"]["mean_hex"]])
    scale = np.asarray([float.fromhex(v) for v in artifact["scaler"]["scale_hex"]])
    coef = np.asarray([float.fromhex(v) for v in artifact["coefficient_hex"]])
    intercept = float.fromhex(artifact["intercept_hex"])
    score = ((x - mean) / scale) @ coef + intercept
    result = 1.0 / (1.0 + np.exp(-score))
    require(np.isfinite(result).all(), "non-finite probability")
    return result.tolist()


def ml_output(probability):
    return "F1_PRESENT" if probability >= .5 else "F1_ABSENT"


def hybrid_output(rule_output, probability=None):
    if rule_output == "F1_PRESENT": return "F1_PRESENT"
    if probability is None: return "UNAVAILABLE_EVIDENCE"
    if probability >= .8: return "F1_PRESENT"
    if probability <= .2: return "F1_ABSENT"
    return "ABSTAIN"

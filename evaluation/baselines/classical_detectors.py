#!/usr/bin/env python3
"""
WP-4.2: Classical Anomaly-Detection Baselines
==============================================

Standalone module implementing the six (plus extra) classical detector families
used as comparison baselines for the SCAFAD evaluation.

Detector catalogue
------------------
Statistical:
  - StatisticalZScoreDetector    — per-feature Z-score with configurable threshold
  - StatisticalIQRDetector       — inter-quartile-range outlier detection
  - MovingAverageDetector        — moving-average control limits (time-series)

Classical ML (sklearn):
  - IsolationForestDetector      — ensemble isolation trees
  - OneClassSVMDetector          — kernel SVM with nu-parameterisation
  - LocalOutlierFactorDetector   — local density-based LOF (novelty mode)
  - EllipticEnvelopeDetector     — robust covariance / Mahalanobis distance
  - KMeansDetector               — distance to nearest K-Means centroid

Bonus:
  - DBSCANAnomalyDetector        — density-scan, points outside clusters = anomaly

All detectors share the ``BaseAnomalyDetector`` interface:
    detector.fit(X_train, feature_names=None)
    result = detector.predict(X_test)   →  BaselineResult

``BaselineResult`` carries:
    .anomaly_predictions   np.ndarray[int]   (0=normal, 1=anomaly)
    .anomaly_scores        np.ndarray[float] (higher → more anomalous)
    .model_parameters      dict              (serialisable params for JSON output)

This module has no dependency on the SCAFAD package.  It only requires
``numpy`` and ``scikit-learn`` (plus ``scipy`` / ``statsmodels`` optionally).

Academic references
-------------------
- Chandola et al. (2009) "Anomaly Detection: A Survey", ACM CSUR.
- Liu et al. (2008) "Isolation Forest", ICDM.
- Breunig et al. (2000) "LOF: Density-Based Local Outliers", SIGMOD.
- Manevitz & Yousef (2001) "One-class SVMs for Document Classification", JMLR.
- Rousseeuw & Van Driessen (1999) "A Fast Algorithm for the MCD Estimator", Technometrics.
"""

from __future__ import annotations

import logging
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------

try:
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.covariance import EllipticEnvelope
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import roc_auc_score
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import OneClassSVM

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    warnings.warn("scikit-learn not available — ML detectors will raise ImportError.")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class BaselineType(Enum):
    """Coarse category of a baseline detector."""

    STATISTICAL = "statistical"
    CLASSICAL_ML = "classical_ml"
    TIME_SERIES = "time_series"


@dataclass
class BaselineResult:
    """Output of a single detector's ``predict()`` call.

    Attributes
    ----------
    detector_name:
        Human-readable name echoed from the detector instance.
    baseline_type:
        Coarse category of the detector.
    anomaly_predictions:
        Binary array — 1 means anomaly, 0 means normal.
    anomaly_scores:
        Continuous anomaly scores (higher → more anomalous).
    detection_threshold:
        Decision threshold that was applied (informational).
    processing_time:
        Wall-clock seconds taken by the ``predict()`` call.
    model_parameters:
        Serialisable dict of the detector's configuration/fitted params.
    """

    detector_name: str
    baseline_type: BaselineType
    anomaly_predictions: np.ndarray
    anomaly_scores: np.ndarray
    detection_threshold: float
    processing_time: float
    model_parameters: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseAnomalyDetector(ABC):
    """Interface shared by every baseline detector.

    Parameters
    ----------
    name:
        Human-readable label (appears in results JSON).
    baseline_type:
        Category enum value.
    """

    def __init__(self, name: str, baseline_type: BaselineType) -> None:
        self.name = name
        self.baseline_type = baseline_type
        self.is_trained: bool = False
        self.feature_names: List[str] = []
        self.scaler: Optional[Any] = None

    @abstractmethod
    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Train the detector on (benign) data.

        Parameters
        ----------
        X:
            Feature matrix of shape ``(n_samples, n_features)``.
        feature_names:
            Optional list of feature names for logging/serialisation.
        """

    @abstractmethod
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict anomalies on new data.

        Parameters
        ----------
        X:
            Feature matrix of shape ``(n_samples, n_features)``.

        Returns
        -------
        BaselineResult with predictions, scores, and model parameters.
        """


# ---------------------------------------------------------------------------
# Statistical detectors
# ---------------------------------------------------------------------------


class StatisticalZScoreDetector(BaseAnomalyDetector):
    """Per-feature Z-score anomaly detection.

    A sample is flagged as anomalous when its **maximum** per-feature Z-score
    exceeds the configured ``threshold``.

    Parameters
    ----------
    threshold:
        Z-score cutoff (default 3.0 ≈ 99.7 % of a normal distribution).
    """

    def __init__(self, threshold: float = 3.0) -> None:
        super().__init__("Statistical Z-Score", BaselineType.STATISTICAL)
        self.threshold = threshold
        self.means_: Optional[np.ndarray] = None
        self.stds_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Estimate per-feature mean and standard deviation from ``X``."""
        self.means_ = np.mean(X, axis=0)
        self.stds_ = np.std(X, axis=0)
        # Guard against constant features.
        self.stds_ = np.where(self.stds_ == 0, 1e-8, self.stds_)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using Z-score decision rule."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        z_scores = np.abs((X - self.means_) / self.stds_)
        anomaly_scores = np.max(z_scores, axis=1)
        anomaly_predictions = (anomaly_scores > self.threshold).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=self.threshold,
            processing_time=elapsed,
            model_parameters={
                "threshold": self.threshold,
                "means": self.means_.tolist(),
                "stds": self.stds_.tolist(),
            },
        )


class StatisticalIQRDetector(BaseAnomalyDetector):
    """Interquartile-range (IQR) outlier detection.

    A sample is anomalous if any feature falls outside
    ``[Q1 − m·IQR, Q3 + m·IQR]`` where ``m`` is the ``iqr_multiplier``.

    Parameters
    ----------
    iqr_multiplier:
        Fence multiplier (1.5 = Tukey's rule; 3.0 = far outliers).
    """

    def __init__(self, iqr_multiplier: float = 1.5) -> None:
        super().__init__("Statistical IQR", BaselineType.STATISTICAL)
        self.iqr_multiplier = iqr_multiplier
        self.q1_: Optional[np.ndarray] = None
        self.q3_: Optional[np.ndarray] = None
        self.iqr_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Compute quartiles and IQR from training data."""
        self.q1_ = np.percentile(X, 25, axis=0)
        self.q3_ = np.percentile(X, 75, axis=0)
        self.iqr_ = self.q3_ - self.q1_
        self.iqr_ = np.where(self.iqr_ == 0, 1e-8, self.iqr_)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using IQR fence rule."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        lower = self.q1_ - self.iqr_multiplier * self.iqr_
        upper = self.q3_ + self.iqr_multiplier * self.iqr_
        outlier_mask = (X < lower) | (X > upper)

        lower_dist = np.maximum(0.0, lower - X) / self.iqr_
        upper_dist = np.maximum(0.0, X - upper) / self.iqr_
        anomaly_scores = np.max(np.maximum(lower_dist, upper_dist), axis=1)
        anomaly_predictions = np.any(outlier_mask, axis=1).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=self.iqr_multiplier,
            processing_time=elapsed,
            model_parameters={
                "iqr_multiplier": self.iqr_multiplier,
                "q1": self.q1_.tolist(),
                "q3": self.q3_.tolist(),
                "iqr": self.iqr_.tolist(),
            },
        )


class MovingAverageDetector(BaseAnomalyDetector):
    """Moving-average control-limit anomaly detection.

    For each test point the detector computes the moving average and standard
    deviation over the preceding ``window_size`` samples and flags the point
    if its maximum per-feature Z-score against that window exceeds
    ``std_multiplier``.

    Parameters
    ----------
    window_size:
        Number of preceding samples to include in the rolling window.
    std_multiplier:
        Z-score threshold applied to the rolling statistics.
    """

    def __init__(self, window_size: int = 10, std_multiplier: float = 2.0) -> None:
        super().__init__("Moving Average", BaselineType.TIME_SERIES)
        self.window_size = window_size
        self.std_multiplier = std_multiplier
        self._history: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Store training data as the initial rolling window buffer."""
        self._history = X.copy()
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Evaluate each test sample against a rolling window."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        combined = np.vstack([self._history, X])
        start_idx = len(self._history)

        scores: List[float] = []
        preds: List[int] = []

        for i in range(start_idx, len(combined)):
            win_start = max(0, i - self.window_size)
            window = combined[win_start:i]
            if len(window) < 3:
                scores.append(0.0)
                preds.append(0)
                continue
            mu = np.mean(window, axis=0)
            sigma = np.std(window, axis=0)
            sigma = np.where(sigma == 0, 1e-8, sigma)
            z = np.max(np.abs((combined[i] - mu) / sigma))
            scores.append(float(z))
            preds.append(int(z > self.std_multiplier))

        elapsed = time.perf_counter() - t0
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=np.array(preds, dtype=int),
            anomaly_scores=np.array(scores, dtype=float),
            detection_threshold=self.std_multiplier,
            processing_time=elapsed,
            model_parameters={
                "window_size": self.window_size,
                "std_multiplier": self.std_multiplier,
            },
        )


# ---------------------------------------------------------------------------
# Classical ML detectors (require scikit-learn)
# ---------------------------------------------------------------------------


class IsolationForestDetector(BaseAnomalyDetector):
    """Isolation Forest ensemble anomaly detector (Liu et al., 2008).

    Fits an ensemble of isolation trees on standardised features.  Anomaly
    score is derived from the negated ``decision_function`` (higher = more
    anomalous).

    Parameters
    ----------
    contamination:
        Expected fraction of anomalies; controls the decision boundary.
    n_estimators:
        Number of isolation trees in the ensemble.
    random_state:
        Reproducibility seed.
    """

    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        super().__init__("Isolation Forest", BaselineType.CLASSICAL_ML)
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self._model: Optional[Any] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Fit the Isolation Forest on standardised ``X``."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for IsolationForestDetector.")
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(X_s)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using Isolation Forest decision boundary."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        X_s = self.scaler.transform(X)
        raw = -self._model.decision_function(X_s)          # higher = more anomalous
        lo, hi = float(np.min(raw)), float(np.max(raw))
        anomaly_scores = (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)
        anomaly_predictions = (self._model.predict(X_s) == -1).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=0.0,
            processing_time=elapsed,
            model_parameters={
                "contamination": self.contamination,
                "n_estimators": self.n_estimators,
                "random_state": self.random_state,
            },
        )


class OneClassSVMDetector(BaseAnomalyDetector):
    """One-Class SVM anomaly detector (Schölkopf et al., 2001).

    Fits a kernel SVM boundary around normal data.  The negated
    ``decision_function`` serves as an anomaly score.

    Parameters
    ----------
    gamma:
        Kernel coefficient — ``'scale'`` or ``'auto'`` (sklearn default).
    nu:
        Upper bound on the fraction of training errors; governs boundary
        tightness.
    """

    def __init__(self, gamma: str = "scale", nu: float = 0.1) -> None:
        super().__init__("One-Class SVM", BaselineType.CLASSICAL_ML)
        self.gamma = gamma
        self.nu = nu
        self._model: Optional[Any] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Fit One-Class SVM on standardised ``X``."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for OneClassSVMDetector.")
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        self._model = OneClassSVM(gamma=self.gamma, nu=self.nu)
        self._model.fit(X_s)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using One-Class SVM decision boundary."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        X_s = self.scaler.transform(X)
        raw = -self._model.decision_function(X_s)
        lo, hi = float(np.min(raw)), float(np.max(raw))
        anomaly_scores = (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)
        anomaly_predictions = (self._model.predict(X_s) == -1).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=0.0,
            processing_time=elapsed,
            model_parameters={"gamma": self.gamma, "nu": self.nu},
        )


class LocalOutlierFactorDetector(BaseAnomalyDetector):
    """Local Outlier Factor (LOF) anomaly detector (Breunig et al., 2000).

    Uses ``novelty=True`` so that previously unseen test points can be
    scored against the fitted neighbourhood graph.

    Parameters
    ----------
    n_neighbors:
        Number of neighbours used to compute the local reachability density.
    contamination:
        Expected fraction of outliers; sets the LOF threshold.
    """

    def __init__(self, n_neighbors: int = 20, contamination: float = 0.1) -> None:
        super().__init__("Local Outlier Factor", BaselineType.CLASSICAL_ML)
        self.n_neighbors = n_neighbors
        self.contamination = contamination
        self._model: Optional[Any] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Fit LOF on standardised ``X``."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for LocalOutlierFactorDetector.")
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        self._model = LocalOutlierFactor(
            n_neighbors=self.n_neighbors,
            contamination=self.contamination,
            novelty=True,
        )
        self._model.fit(X_s)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using LOF decision boundary."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        X_s = self.scaler.transform(X)
        raw = -self._model.decision_function(X_s)
        lo, hi = float(np.min(raw)), float(np.max(raw))
        anomaly_scores = (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)
        anomaly_predictions = (self._model.predict(X_s) == -1).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=0.0,
            processing_time=elapsed,
            model_parameters={
                "n_neighbors": self.n_neighbors,
                "contamination": self.contamination,
            },
        )


class EllipticEnvelopeDetector(BaseAnomalyDetector):
    """Elliptic Envelope (robust covariance) anomaly detector.

    Fits a Minimum Covariance Determinant (MCD) Gaussian to training data.
    Test points with large Mahalanobis distance from the fitted distribution
    are classified as anomalies.

    Reference: Rousseeuw & Van Driessen (1999).

    Parameters
    ----------
    contamination:
        Expected proportion of outliers in the training set.  In one-class
        learning the training set is benign-only, so 0.10 is a conservative
        upper bound.
    """

    def __init__(self, contamination: float = 0.1) -> None:
        super().__init__("Elliptic Envelope", BaselineType.CLASSICAL_ML)
        self.contamination = contamination
        self._model: Optional[Any] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Fit robust covariance model on standardised ``X``."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for EllipticEnvelopeDetector.")
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        self._model = EllipticEnvelope(
            contamination=self.contamination,
            random_state=42,
        )
        self._model.fit(X_s)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict anomalies using Mahalanobis distance from fitted Gaussian."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        X_s = self.scaler.transform(X)
        # decision_function: positive = inlier, negative = outlier
        raw = -self._model.decision_function(X_s)           # higher = more anomalous
        lo, hi = float(np.min(raw)), float(np.max(raw))
        anomaly_scores = (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)
        anomaly_predictions = (self._model.predict(X_s) == -1).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=0.0,
            processing_time=elapsed,
            model_parameters={"contamination": self.contamination},
        )


class KMeansDetector(BaseAnomalyDetector):
    """K-Means centroid-distance anomaly detector.

    Trains K-Means on benign data to learn typical behaviour clusters.  The
    anomaly score for a test point is its Euclidean distance to the nearest
    cluster centroid in standardised feature space.  The decision threshold
    is set to ``mean + k·std`` of training-set centroid distances.

    Parameters
    ----------
    n_clusters:
        Number of K-Means clusters (behaviour modes).
    threshold_std_multiplier:
        Standard-deviation multiplier for the anomaly threshold.
    """

    def __init__(
        self,
        n_clusters: int = 5,
        threshold_std_multiplier: float = 2.0,
    ) -> None:
        super().__init__("KMeans", BaselineType.CLASSICAL_ML)
        self.n_clusters = n_clusters
        self.threshold_std_multiplier = threshold_std_multiplier
        self._model: Optional[Any] = None
        self.threshold_: float = 0.0

    # ------------------------------------------------------------------
    def _nearest_centroid_distances(self, X_scaled: np.ndarray) -> np.ndarray:
        """Return per-sample Euclidean distance to the nearest centroid.

        Parameters
        ----------
        X_scaled:
            Standardised feature matrix, shape ``(n, d)``.
        """
        C = self._model.cluster_centers_                     # (k, d)
        diff = X_scaled[:, np.newaxis, :] - C[np.newaxis, :, :]
        return np.sqrt((diff ** 2).sum(axis=2)).min(axis=1)  # (n,)

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Fit K-Means on standardised ``X`` and calibrate the threshold."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for KMeansDetector.")
        n_clusters = min(self.n_clusters, len(X))
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        self._model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self._model.fit(X_s)
        train_dists = self._nearest_centroid_distances(X_s)
        self.threshold_ = float(
            np.mean(train_dists) + self.threshold_std_multiplier * np.std(train_dists)
        )
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict anomalies via centroid-distance threshold."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        X_s = self.scaler.transform(X)
        dists = self._nearest_centroid_distances(X_s)
        lo, hi = float(np.min(dists)), float(np.max(dists))
        anomaly_scores = (dists - lo) / (hi - lo) if hi > lo else np.zeros_like(dists)
        anomaly_predictions = (dists > self.threshold_).astype(int)
        elapsed = time.perf_counter() - t0

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=self.threshold_,
            processing_time=elapsed,
            model_parameters={
                "n_clusters": self.n_clusters,
                "threshold_std_multiplier": self.threshold_std_multiplier,
                "fitted_threshold": self.threshold_,
            },
        )


class DBSCANAnomalyDetector(BaseAnomalyDetector):
    """DBSCAN clustering-based anomaly detector.

    Fits DBSCAN on training data.  At prediction time, points are scored by
    their distance to the nearest training cluster centroid; those far from
    all clusters are flagged as anomalies.

    Parameters
    ----------
    eps:
        DBSCAN neighbourhood radius (standardised feature space).
    min_samples:
        Minimum number of points in a neighbourhood to form a core point.
    """

    def __init__(self, eps: float = 0.5, min_samples: int = 5) -> None:
        super().__init__("DBSCAN Clustering", BaselineType.CLASSICAL_ML)
        self.eps = eps
        self.min_samples = min_samples
        self._cluster_centroids: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        """Fit DBSCAN and compute cluster centroids for distance scoring."""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for DBSCANAnomalyDetector.")
        self.scaler = StandardScaler()
        X_s = self.scaler.fit_transform(X)
        model = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = model.fit_predict(X_s)

        unique_labels = set(labels) - {-1}
        if unique_labels:
            self._cluster_centroids = np.array(
                [X_s[labels == lbl].mean(axis=0) for lbl in sorted(unique_labels)]
            )
        else:
            # No clusters found — treat everything as anomaly.
            self._cluster_centroids = None

        self._num_clusters = len(unique_labels)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict anomalies via distance to nearest cluster centroid."""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction.")

        t0 = time.perf_counter()
        X_s = self.scaler.transform(X)

        if self._cluster_centroids is None:
            anomaly_scores = np.ones(len(X_s), dtype=float)
            anomaly_predictions = np.ones(len(X_s), dtype=int)
            threshold = 0.5
        else:
            diff = X_s[:, np.newaxis, :] - self._cluster_centroids[np.newaxis, :, :]
            dists = np.sqrt((diff ** 2).sum(axis=2)).min(axis=1)
            max_d = float(np.max(dists))
            anomaly_scores = dists / max_d if max_d > 0 else np.zeros_like(dists)
            threshold = float(
                np.mean(anomaly_scores) + 2.0 * np.std(anomaly_scores)
            )
            anomaly_predictions = (anomaly_scores > threshold).astype(int)

        elapsed = time.perf_counter() - t0
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_predictions=anomaly_predictions,
            anomaly_scores=anomaly_scores,
            detection_threshold=threshold,
            processing_time=elapsed,
            model_parameters={
                "eps": self.eps,
                "min_samples": self.min_samples,
                "num_clusters": self._num_clusters,
            },
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "BaseAnomalyDetector",
    "BaselineResult",
    "BaselineType",
    "StatisticalZScoreDetector",
    "StatisticalIQRDetector",
    "MovingAverageDetector",
    "IsolationForestDetector",
    "OneClassSVMDetector",
    "LocalOutlierFactorDetector",
    "EllipticEnvelopeDetector",
    "KMeansDetector",
    "DBSCANAnomalyDetector",
]

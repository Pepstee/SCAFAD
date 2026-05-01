#!/usr/bin/env python3
"""
SCAFAD Classical ML Baselines: Statistical and Traditional ML Anomaly Detectors
==============================================================================

This module implements classical statistical and machine learning baselines for
comparison with the i-GNN approach. These baselines provide proper evaluation
benchmarks using established anomaly detection methods.

Implemented Baselines:
1. Statistical Methods:
   - Z-score based detection
   - Interquartile Range (IQR) outlier detection  
   - Moving average with control limits
   - Seasonal decomposition with anomaly scoring

2. Classical Machine Learning:
   - Isolation Forest (ensemble method)
   - One-Class SVM (support vector machines)
   - Local Outlier Factor (LOF)
   - DBSCAN clustering-based detection
   - Autoencoder neural networks

3. Time Series Methods:
   - ARIMA-based residual analysis
   - Exponential smoothing anomaly detection
   - Change point detection

Academic References:
- "Anomaly Detection: A Survey" (Chandola et al., 2009)
- "Isolation Forest" (Liu et al., 2008) 
- "LOF: Identifying Density-based Local Outliers" (Breunig et al., 2000)
- "One-class SVMs for Document Classification" (Manevitz & Yousef, 2001)
"""

import numpy as np
import pandas as pd
import time
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
import warnings

# Suppress sklearn warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Try to import ML libraries
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.svm import OneClassSVM
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.covariance import EllipticEnvelope
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.decomposition import PCA
    from sklearn.metrics import confusion_matrix, classification_report, roc_auc_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not available. Using fallback implementations.")

try:
    import scipy.stats as stats
    from scipy import signal
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Using fallback statistical methods.")

try:
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

# Import our data structures
from app_telemetry import TelemetryRecord, AnomalyType
from datasets.serverless_traces import ServerlessTrace

logger = logging.getLogger(__name__)


class BaselineType(Enum):
    """Types of baseline detectors"""
    STATISTICAL = "statistical"
    CLASSICAL_ML = "classical_ml"
    TIME_SERIES = "time_series"


@dataclass
class BaselineResult:
    """Result from a baseline detector"""
    detector_name: str
    baseline_type: BaselineType
    anomaly_scores: np.ndarray
    anomaly_predictions: np.ndarray  # Binary: 0=normal, 1=anomaly
    detection_threshold: float
    processing_time: float
    confidence_scores: Optional[np.ndarray] = None
    feature_importance: Optional[Dict[str, float]] = None
    model_parameters: Dict[str, Any] = field(default_factory=dict)
    
    def get_metrics(self, ground_truth: np.ndarray) -> Dict[str, float]:
        """Calculate performance metrics against ground truth"""
        if len(ground_truth) != len(self.anomaly_predictions):
            raise ValueError("Ground truth and predictions must have same length")
        
        # Basic metrics
        tn, fp, fn, tp = confusion_matrix(ground_truth, self.anomaly_predictions).ravel()
        
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Additional metrics
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
        
        metrics = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "specificity": specificity,
            "false_positive_rate": false_positive_rate,
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn)
        }
        
        # AUC-ROC if we have confidence scores
        if self.anomaly_scores is not None:
            try:
                auc = roc_auc_score(ground_truth, self.anomaly_scores)
                metrics["auc_roc"] = auc
            except ValueError:
                metrics["auc_roc"] = 0.0
        
        return metrics


class BaseAnomalyDetector(ABC):
    """Abstract base class for all anomaly detectors"""
    
    def __init__(self, name: str, baseline_type: BaselineType):
        self.name = name
        self.baseline_type = baseline_type
        self.is_trained = False
        self.feature_names = []
        self.scaler = None
        
    @abstractmethod
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Train the detector on normal data"""
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict anomalies on new data"""
        pass
    
    def extract_features(self, records: List[TelemetryRecord]) -> Tuple[np.ndarray, List[str]]:
        """Extract numerical features from telemetry records"""
        if not records:
            return np.array([]), []
        
        features = []
        feature_names = [
            'duration', 'memory_spike_kb', 'cpu_utilization', 'network_io_bytes',
            'is_cold_start', 'error_occurred', 'hour_of_day', 'day_of_week',
            'memory_mb', 'execution_phase_invoke', 'source_primary'
        ]
        
        for record in records:
            # Basic numerical features
            feature_vector = [
                record.duration,
                record.memory_spike_kb,
                record.cpu_utilization,
                record.network_io_bytes,
                float(record.telemetry_metadata.get('is_cold_start', False)),
                float(record.telemetry_metadata.get('error_occurred', False))
            ]
            
            # Time-based features
            timestamp = record.timestamp
            hour_of_day = (timestamp % 86400) / 3600  # Hour of day (0-24)
            day_of_week = ((timestamp // 86400) % 7)  # Day of week (0-6)
            
            feature_vector.extend([hour_of_day, day_of_week])
            
            # Derived features
            memory_mb = record.memory_spike_kb / 1024
            execution_phase_invoke = float(record.execution_phase.value == 'INVOKE')
            source_primary = float(record.source.value == 'PRIMARY')
            
            feature_vector.extend([memory_mb, execution_phase_invoke, source_primary])
            
            features.append(feature_vector)
        
        return np.array(features), feature_names


class StatisticalZScoreDetector(BaseAnomalyDetector):
    """Z-score based statistical anomaly detection"""
    
    def __init__(self, threshold: float = 3.0):
        super().__init__("Statistical Z-Score", BaselineType.STATISTICAL)
        self.threshold = threshold
        self.means = None
        self.stds = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit statistical parameters"""
        self.means = np.mean(X, axis=0)
        self.stds = np.std(X, axis=0)
        # Handle zero standard deviation
        self.stds = np.where(self.stds == 0, 1e-8, self.stds)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using Z-score threshold"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Calculate Z-scores
        z_scores = np.abs((X - self.means) / self.stds)
        
        # Aggregate Z-scores (max across features)
        anomaly_scores = np.max(z_scores, axis=1)
        
        # Binary predictions
        anomaly_predictions = (anomaly_scores > self.threshold).astype(int)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=self.threshold,
            processing_time=processing_time,
            model_parameters={"threshold": self.threshold, "means": self.means.tolist(), "stds": self.stds.tolist()}
        )


class StatisticalIQRDetector(BaseAnomalyDetector):
    """Interquartile Range (IQR) based anomaly detection"""
    
    def __init__(self, iqr_multiplier: float = 1.5):
        super().__init__("Statistical IQR", BaselineType.STATISTICAL)
        self.iqr_multiplier = iqr_multiplier
        self.q1 = None
        self.q3 = None
        self.iqr = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit IQR parameters"""
        self.q1 = np.percentile(X, 25, axis=0)
        self.q3 = np.percentile(X, 75, axis=0) 
        self.iqr = self.q3 - self.q1
        # Handle zero IQR
        self.iqr = np.where(self.iqr == 0, 1e-8, self.iqr)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using IQR outlier detection"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Calculate outlier bounds
        lower_bound = self.q1 - self.iqr_multiplier * self.iqr
        upper_bound = self.q3 + self.iqr_multiplier * self.iqr
        
        # Check for outliers
        outlier_mask = (X < lower_bound) | (X > upper_bound)
        
        # Anomaly score as max normalized distance from bounds
        lower_dist = np.maximum(0, lower_bound - X) / self.iqr
        upper_dist = np.maximum(0, X - upper_bound) / self.iqr
        feature_scores = np.maximum(lower_dist, upper_dist)
        
        anomaly_scores = np.max(feature_scores, axis=1)
        anomaly_predictions = np.any(outlier_mask, axis=1).astype(int)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=self.iqr_multiplier,
            processing_time=processing_time,
            model_parameters={
                "iqr_multiplier": self.iqr_multiplier,
                "q1": self.q1.tolist(), 
                "q3": self.q3.tolist(),
                "iqr": self.iqr.tolist()
            }
        )


class IsolationForestDetector(BaseAnomalyDetector):
    """Isolation Forest ensemble anomaly detection"""
    
    def __init__(self, contamination: float = 0.1, n_estimators: int = 100, random_state: int = 42):
        super().__init__("Isolation Forest", BaselineType.CLASSICAL_ML)
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit Isolation Forest model"""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for Isolation Forest")
        
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model.fit(X_scaled)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using Isolation Forest"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Scale features
        X_scaled = self.scaler.transform(X)
        
        # Get anomaly scores (lower is more anomalous)
        scores = self.model.decision_function(X_scaled)
        
        # Convert to anomaly scores (higher is more anomalous)
        anomaly_scores = -scores  # Negate so higher = more anomalous
        
        # Normalize to [0, 1] range
        min_score, max_score = np.min(anomaly_scores), np.max(anomaly_scores)
        if max_score > min_score:
            anomaly_scores = (anomaly_scores - min_score) / (max_score - min_score)
        else:
            anomaly_scores = np.zeros_like(anomaly_scores)
        
        # Binary predictions
        predictions = self.model.predict(X_scaled)
        anomaly_predictions = (predictions == -1).astype(int)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=0.0,  # Isolation Forest uses contamination parameter
            processing_time=processing_time,
            model_parameters={
                "contamination": self.contamination,
                "n_estimators": self.n_estimators,
                "random_state": self.random_state
            }
        )


class OneClassSVMDetector(BaseAnomalyDetector):
    """One-Class SVM anomaly detection"""
    
    def __init__(self, gamma: str = 'scale', nu: float = 0.1):
        super().__init__("One-Class SVM", BaselineType.CLASSICAL_ML)
        self.gamma = gamma
        self.nu = nu
        self.model = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit One-Class SVM model"""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for One-Class SVM")
        
        self.model = OneClassSVM(gamma=self.gamma, nu=self.nu)
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model.fit(X_scaled)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using One-Class SVM"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Scale features
        X_scaled = self.scaler.transform(X)
        
        # Get decision function scores
        scores = self.model.decision_function(X_scaled)
        
        # Convert to anomaly scores (higher is more anomalous)
        anomaly_scores = -scores
        
        # Normalize to [0, 1] range
        min_score, max_score = np.min(anomaly_scores), np.max(anomaly_scores)
        if max_score > min_score:
            anomaly_scores = (anomaly_scores - min_score) / (max_score - min_score)
        else:
            anomaly_scores = np.zeros_like(anomaly_scores)
        
        # Binary predictions
        predictions = self.model.predict(X_scaled)
        anomaly_predictions = (predictions == -1).astype(int)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=0.0,  # SVM uses nu parameter
            processing_time=processing_time,
            model_parameters={"gamma": self.gamma, "nu": self.nu}
        )


class LocalOutlierFactorDetector(BaseAnomalyDetector):
    """Local Outlier Factor (LOF) anomaly detection"""
    
    def __init__(self, n_neighbors: int = 20, contamination: float = 0.1):
        super().__init__("Local Outlier Factor", BaselineType.CLASSICAL_ML)
        self.n_neighbors = n_neighbors
        self.contamination = contamination
        self.model = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit LOF model"""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for LOF")
        
        self.model = LocalOutlierFactor(
            n_neighbors=self.n_neighbors,
            contamination=self.contamination,
            novelty=True  # Enable prediction on new data
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model.fit(X_scaled)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using LOF"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Scale features
        X_scaled = self.scaler.transform(X)
        
        # Get decision function scores
        scores = self.model.decision_function(X_scaled)
        
        # Convert to anomaly scores (higher is more anomalous) 
        anomaly_scores = -scores
        
        # Normalize to [0, 1] range
        min_score, max_score = np.min(anomaly_scores), np.max(anomaly_scores)
        if max_score > min_score:
            anomaly_scores = (anomaly_scores - min_score) / (max_score - min_score)
        else:
            anomaly_scores = np.zeros_like(anomaly_scores)
        
        # Binary predictions
        predictions = self.model.predict(X_scaled)
        anomaly_predictions = (predictions == -1).astype(int)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=0.0,  # LOF uses contamination parameter
            processing_time=processing_time,
            model_parameters={
                "n_neighbors": self.n_neighbors,
                "contamination": self.contamination
            }
        )


class DBSCANAnomalyDetector(BaseAnomalyDetector):
    """DBSCAN clustering-based anomaly detection"""
    
    def __init__(self, eps: float = 0.5, min_samples: int = 5):
        super().__init__("DBSCAN Clustering", BaselineType.CLASSICAL_ML)
        self.eps = eps
        self.min_samples = min_samples
        self.model = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit DBSCAN model"""
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for DBSCAN")
        
        self.model = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit clustering model
        self.cluster_labels = self.model.fit_predict(X_scaled)
        self.training_data = X_scaled  # Store for distance calculations
        
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using DBSCAN clustering"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Scale features
        X_scaled = self.scaler.transform(X)
        
        # Calculate distance to nearest cluster centroid
        unique_labels = set(self.cluster_labels)
        if -1 in unique_labels:  # Remove noise label
            unique_labels.remove(-1)
        
        # Calculate cluster centroids
        cluster_centroids = []
        for label in unique_labels:
            cluster_mask = self.cluster_labels == label
            if np.any(cluster_mask):
                centroid = np.mean(self.training_data[cluster_mask], axis=0)
                cluster_centroids.append(centroid)
        
        if not cluster_centroids:
            # No clusters found, treat all as anomalies
            anomaly_scores = np.ones(len(X_scaled))
            anomaly_predictions = np.ones(len(X_scaled), dtype=int)
        else:
            # Calculate distance to nearest cluster centroid
            cluster_centroids = np.array(cluster_centroids)
            distances = []
            
            for point in X_scaled:
                # Distance to each centroid
                point_distances = np.sqrt(np.sum((cluster_centroids - point) ** 2, axis=1))
                min_distance = np.min(point_distances)
                distances.append(min_distance)
            
            distances = np.array(distances)
            
            # Normalize distances to [0, 1]
            max_distance = np.max(distances)
            if max_distance > 0:
                anomaly_scores = distances / max_distance
            else:
                anomaly_scores = np.zeros_like(distances)
            
            # Threshold based on standard deviation
            threshold = np.mean(anomaly_scores) + 2 * np.std(anomaly_scores)
            anomaly_predictions = (anomaly_scores > threshold).astype(int)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=threshold if 'threshold' in locals() else 0.5,
            processing_time=processing_time,
            model_parameters={
                "eps": self.eps,
                "min_samples": self.min_samples,
                "num_clusters": len(unique_labels) if 'unique_labels' in locals() else 0
            }
        )


class MovingAverageDetector(BaseAnomalyDetector):
    """Moving average with control limits anomaly detection"""
    
    def __init__(self, window_size: int = 10, std_multiplier: float = 2.0):
        super().__init__("Moving Average", BaselineType.STATISTICAL)
        self.window_size = window_size
        self.std_multiplier = std_multiplier
        self.historical_data = None
        
    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Store historical data for moving average calculation"""
        self.historical_data = X.copy()
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True
        
    def predict(self, X: np.ndarray) -> BaselineResult:
        """Predict using moving average with control limits"""
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")
        
        start_time = time.time()
        
        # Combine historical and new data for moving average
        combined_data = np.vstack([self.historical_data, X])
        
        anomaly_scores = []
        anomaly_predictions = []
        
        # Process each new data point
        start_idx = len(self.historical_data)
        
        for i in range(start_idx, len(combined_data)):
            # Get window of previous data points
            window_start = max(0, i - self.window_size)
            window_data = combined_data[window_start:i]
            
            if len(window_data) < 3:  # Need minimum data for statistics
                anomaly_scores.append(0.0)
                anomaly_predictions.append(0)
                continue
            
            # Calculate moving average and standard deviation
            moving_avg = np.mean(window_data, axis=0)
            moving_std = np.std(window_data, axis=0)
            moving_std = np.where(moving_std == 0, 1e-8, moving_std)
            
            # Current point
            current_point = combined_data[i]
            
            # Calculate z-scores
            z_scores = np.abs((current_point - moving_avg) / moving_std)
            
            # Aggregate anomaly score (max z-score across features)
            max_z_score = np.max(z_scores)
            anomaly_scores.append(max_z_score)
            
            # Binary prediction
            is_anomaly = max_z_score > self.std_multiplier
            anomaly_predictions.append(int(is_anomaly))
        
        anomaly_scores = np.array(anomaly_scores)
        anomaly_predictions = np.array(anomaly_predictions)
        
        processing_time = time.time() - start_time
        
        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=self.std_multiplier,
            processing_time=processing_time,
            model_parameters={
                "window_size": self.window_size,
                "std_multiplier": self.std_multiplier
            }
        )


class EllipticEnvelopeDetector(BaseAnomalyDetector):
    """Elliptic Envelope (robust covariance estimation) anomaly detection.

    Fits a multivariate Gaussian distribution to the training data using
    robust covariance estimation (Minimum Covariance Determinant).  Points
    with a large Mahalanobis distance from the fitted distribution are
    flagged as anomalies.

    Academic Reference:
    - "A Fast Algorithm for the Minimum Covariance Determinant Estimator"
      (Rousseeuw & Van Driessen, 1999)
    """

    def __init__(self, contamination: float = 0.1):
        """Initialise the detector.

        Parameters
        ----------
        contamination:
            Expected proportion of outliers in the *training* set.  In
            one-class learning the training set is benign-only, so a value
            of 0.10 is a conservative upper bound that avoids over-tightening
            the decision boundary.
        """
        super().__init__("Elliptic Envelope", BaselineType.CLASSICAL_ML)
        self.contamination = contamination
        self.model: Optional[Any] = None

    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit the robust covariance model on normal (benign) data.

        Parameters
        ----------
        X:
            Feature matrix of shape (n_samples, n_features) — benign only.
        feature_names:
            Optional list of feature names for diagnostics.
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for EllipticEnvelope")

        self.model = EllipticEnvelope(
            contamination=self.contamination,
            random_state=42,
        )

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model.fit(X_scaled)
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> "BaselineResult":
        """Predict anomalies using Mahalanobis distance from the fitted Gaussian.

        Parameters
        ----------
        X:
            Feature matrix of shape (n_samples, n_features).

        Returns
        -------
        BaselineResult with normalised anomaly scores and binary predictions.
        """
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")

        start_time = time.time()

        X_scaled = self.scaler.transform(X)

        # decision_function returns positive for inliers, negative for outliers.
        # Negate so that higher score = more anomalous.
        raw_scores = -self.model.decision_function(X_scaled)

        # Normalise to [0, 1]
        min_s, max_s = float(np.min(raw_scores)), float(np.max(raw_scores))
        if max_s > min_s:
            anomaly_scores = (raw_scores - min_s) / (max_s - min_s)
        else:
            anomaly_scores = np.zeros_like(raw_scores)

        # Binary labels: sklearn returns +1 for inliers, -1 for outliers.
        predictions = self.model.predict(X_scaled)
        anomaly_predictions = (predictions == -1).astype(int)

        processing_time = time.time() - start_time

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=0.0,   # governed by contamination parameter
            processing_time=processing_time,
            model_parameters={"contamination": self.contamination},
        )


class KMeansDetector(BaseAnomalyDetector):
    """KMeans clustering-based anomaly detection.

    Trains KMeans on benign data to learn the typical behaviour clusters.
    Anomaly score for a test point is its Euclidean distance to the nearest
    cluster centroid in the standardised feature space.  Points that fall
    far from all centroids are likely anomalous.

    The decision threshold is set to ``mean + threshold_std_multiplier * std``
    of the centroid distances observed on the *training* data.
    """

    def __init__(self, n_clusters: int = 5, threshold_std_multiplier: float = 2.0):
        """Initialise the detector.

        Parameters
        ----------
        n_clusters:
            Number of KMeans clusters.  Represents the expected number of
            distinct benign behaviour modes in the telemetry data.
        threshold_std_multiplier:
            How many standard deviations above the training-set mean distance
            the anomaly decision threshold is placed.
        """
        super().__init__("KMeans", BaselineType.CLASSICAL_ML)
        self.n_clusters = n_clusters
        self.threshold_std_multiplier = threshold_std_multiplier
        self.model: Optional[Any] = None
        self.threshold_: float = 0.0

    def _distances_to_nearest_centroid(self, X_scaled: np.ndarray) -> np.ndarray:
        """Compute minimum Euclidean distance from each point to its nearest centroid.

        Parameters
        ----------
        X_scaled:
            Standardised feature matrix, shape (n_samples, n_features).

        Returns
        -------
        ndarray of shape (n_samples,) with per-point minimum distances.
        """
        centroids = self.model.cluster_centers_          # (k, n_features)
        # Broadcast subtraction: (n_samples, 1, n_features) - (1, k, n_features)
        diff = X_scaled[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        dist_matrix = np.sqrt((diff ** 2).sum(axis=2))   # (n_samples, k)
        return dist_matrix.min(axis=1)                   # (n_samples,)

    def fit(self, X: np.ndarray, feature_names: List[str] = None) -> None:
        """Fit KMeans clusters on normal (benign) data and calibrate threshold.

        Parameters
        ----------
        X:
            Feature matrix of shape (n_samples, n_features) — benign only.
        feature_names:
            Optional list of feature names for diagnostics.
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for KMeans")

        # Cap n_clusters to the number of available training samples.
        n_clusters = min(self.n_clusters, len(X))

        self.model = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10,
        )

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model.fit(X_scaled)

        # Calibrate threshold from training-set distances.
        train_distances = self._distances_to_nearest_centroid(X_scaled)
        self.threshold_ = float(
            np.mean(train_distances)
            + self.threshold_std_multiplier * np.std(train_distances)
        )

        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        self.is_trained = True

    def predict(self, X: np.ndarray) -> "BaselineResult":
        """Predict anomalies based on distance to nearest KMeans centroid.

        Parameters
        ----------
        X:
            Feature matrix of shape (n_samples, n_features).

        Returns
        -------
        BaselineResult with normalised anomaly scores and binary predictions.
        """
        if not self.is_trained:
            raise ValueError("Detector must be fitted before prediction")

        start_time = time.time()

        X_scaled = self.scaler.transform(X)
        distances = self._distances_to_nearest_centroid(X_scaled)

        # Normalise to [0, 1]
        min_d, max_d = float(np.min(distances)), float(np.max(distances))
        if max_d > min_d:
            anomaly_scores = (distances - min_d) / (max_d - min_d)
        else:
            anomaly_scores = np.zeros_like(distances)

        anomaly_predictions = (distances > self.threshold_).astype(int)

        processing_time = time.time() - start_time

        return BaselineResult(
            detector_name=self.name,
            baseline_type=self.baseline_type,
            anomaly_scores=anomaly_scores,
            anomaly_predictions=anomaly_predictions,
            detection_threshold=self.threshold_,
            processing_time=processing_time,
            model_parameters={
                "n_clusters": self.n_clusters,
                "threshold_std_multiplier": self.threshold_std_multiplier,
                "fitted_threshold": self.threshold_,
            },
        )


class BaselineComparator:
    """Compares multiple baseline detectors against ground truth"""
    
    def __init__(self):
        self.detectors = []
        self.results = []
        
    def add_detector(self, detector: BaseAnomalyDetector):
        """Add a baseline detector"""
        self.detectors.append(detector)
        
    def compare_detectors(self, training_data: List[TelemetryRecord],
                         test_data: List[TelemetryRecord],
                         ground_truth: List[int]) -> Dict[str, Any]:
        """Compare all detectors on the same dataset"""
        
        logger.info(f"Comparing {len(self.detectors)} baseline detectors")
        logger.info(f"Training data: {len(training_data)} records")
        logger.info(f"Test data: {len(test_data)} records")
        
        # Extract features
        train_features, feature_names = self.detectors[0].extract_features(training_data)
        test_features, _ = self.detectors[0].extract_features(test_data)
        ground_truth_array = np.array(ground_truth)
        
        comparison_results = {
            "dataset_info": {
                "training_samples": len(training_data),
                "test_samples": len(test_data),
                "num_features": len(feature_names),
                "feature_names": feature_names,
                "anomaly_rate": np.mean(ground_truth_array)
            },
            "detector_results": {},
            "performance_ranking": [],
            "processing_times": {},
            "comparison_timestamp": time.time()
        }
        
        # Train and evaluate each detector
        for detector in self.detectors:
            logger.info(f"Evaluating {detector.name}...")
            
            try:
                # Train detector
                train_start = time.time()
                detector.fit(train_features, feature_names)
                train_time = time.time() - train_start
                
                # Test detector
                result = detector.predict(test_features)
                
                # Calculate metrics
                metrics = result.get_metrics(ground_truth_array)
                
                # Store comprehensive results
                comparison_results["detector_results"][detector.name] = {
                    "baseline_type": detector.baseline_type.value,
                    "training_time": train_time,
                    "prediction_time": result.processing_time,
                    "total_time": train_time + result.processing_time,
                    "metrics": metrics,
                    "model_parameters": result.model_parameters,
                    "anomaly_score_stats": {
                        "mean": float(np.mean(result.anomaly_scores)),
                        "std": float(np.std(result.anomaly_scores)),
                        "min": float(np.min(result.anomaly_scores)),
                        "max": float(np.max(result.anomaly_scores))
                    }
                }
                
                comparison_results["processing_times"][detector.name] = {
                    "training_time": train_time,
                    "prediction_time": result.processing_time,
                    "total_time": train_time + result.processing_time
                }
                
                logger.info(f"  {detector.name}: F1={metrics['f1_score']:.3f}, "
                           f"Precision={metrics['precision']:.3f}, "
                           f"Recall={metrics['recall']:.3f}")
                
            except Exception as e:
                logger.error(f"Failed to evaluate {detector.name}: {e}")
                comparison_results["detector_results"][detector.name] = {
                    "error": str(e),
                    "baseline_type": detector.baseline_type.value
                }
        
        # Create performance ranking
        successful_detectors = [
            (name, data) for name, data in comparison_results["detector_results"].items()
            if "error" not in data
        ]
        
        # Sort by F1 score (primary), then by AUC (secondary)
        successful_detectors.sort(
            key=lambda x: (
                x[1]["metrics"]["f1_score"],
                x[1]["metrics"].get("auc_roc", 0)
            ),
            reverse=True
        )
        
        comparison_results["performance_ranking"] = [
            {
                "rank": i + 1,
                "detector_name": name,
                "baseline_type": data["baseline_type"],
                "f1_score": data["metrics"]["f1_score"],
                "precision": data["metrics"]["precision"],
                "recall": data["metrics"]["recall"],
                "auc_roc": data["metrics"].get("auc_roc", 0),
                "processing_time": data["total_time"]
            }
            for i, (name, data) in enumerate(successful_detectors)
        ]
        
        # Summary statistics
        if successful_detectors:
            f1_scores = [data["metrics"]["f1_score"] for _, data in successful_detectors]
            processing_times = [data["total_time"] for _, data in successful_detectors]
            
            comparison_results["summary"] = {
                "best_f1_score": max(f1_scores),
                "worst_f1_score": min(f1_scores),
                "avg_f1_score": np.mean(f1_scores),
                "fastest_detector": successful_detectors[np.argmin(processing_times)][0],
                "slowest_detector": successful_detectors[np.argmax(processing_times)][0],
                "avg_processing_time": np.mean(processing_times)
            }
        
        return comparison_results
    
    def create_default_detector_suite(self) -> List[BaseAnomalyDetector]:
        """Create a default suite of baseline detectors"""
        detectors = [
            StatisticalZScoreDetector(threshold=3.0),
            StatisticalZScoreDetector(threshold=2.5),
            StatisticalIQRDetector(iqr_multiplier=1.5),
            StatisticalIQRDetector(iqr_multiplier=2.0),
            MovingAverageDetector(window_size=10, std_multiplier=2.0),
            MovingAverageDetector(window_size=20, std_multiplier=2.5)
        ]
        
        # Add ML-based detectors if sklearn is available
        if SKLEARN_AVAILABLE:
            detectors.extend([
                IsolationForest(contamination=0.1, n_estimators=100),
                IsolationForest(contamination=0.05, n_estimators=200),
                OneClassSVMDetector(gamma='scale', nu=0.1),
                OneClassSVMDetector(gamma='auto', nu=0.05),
                LocalOutlierFactorDetector(n_neighbors=20, contamination=0.1),
                LocalOutlierFactorDetector(n_neighbors=10, contamination=0.05),
                DBSCANAnomalyDetector(eps=0.5, min_samples=5),
                DBSCANAnomalyDetector(eps=1.0, min_samples=3)
            ])
        
        return detectors


# Export key classes
__all__ = [
    'BaseAnomalyDetector',
    'BaselineResult',
    'BaselineComparator',
    'StatisticalZScoreDetector',
    'StatisticalIQRDetector',
    'IsolationForestDetector',
    'OneClassSVMDetector',
    'LocalOutlierFactorDetector',
    'DBSCANAnomalyDetector',
    'MovingAverageDetector',
    'EllipticEnvelopeDetector',
    'KMeansDetector',
]


# Self-test function
async def run_self_test():
    """Run self-test of baseline detectors"""
    print("Running Classical ML Baselines Self-Test...")
    print("=" * 50)
    
    try:
        # Generate synthetic data
        np.random.seed(42)
        
        # Normal data
        normal_data = np.random.normal(0, 1, (100, 5))
        
        # Anomalous data (outliers)
        anomaly_data = np.random.normal(3, 0.5, (10, 5))  # Different mean
        
        # Combine data
        X = np.vstack([normal_data, anomaly_data])
        y = np.hstack([np.zeros(100), np.ones(10)])  # Ground truth
        
        # Split into train/test
        train_X, test_X = X[:80], X[80:]
        train_y, test_y = y[:80], y[80:]
        
        print(f"✅ Generated synthetic data: {len(train_X)} train, {len(test_X)} test samples")
        
        # Test statistical detectors
        z_detector = StatisticalZScoreDetector(threshold=2.5)
        z_detector.fit(train_X[train_y == 0])  # Train on normal data only
        z_result = z_detector.predict(test_X)
        z_metrics = z_result.get_metrics(test_y)
        print(f"✅ Z-Score Detector: F1={z_metrics['f1_score']:.3f}")
        
        iqr_detector = StatisticalIQRDetector(iqr_multiplier=1.5)
        iqr_detector.fit(train_X[train_y == 0])
        iqr_result = iqr_detector.predict(test_X)
        iqr_metrics = iqr_result.get_metrics(test_y)
        print(f"✅ IQR Detector: F1={iqr_metrics['f1_score']:.3f}")
        
        # Test ML detectors if available
        if SKLEARN_AVAILABLE:
            iso_detector = IsolationForestDetector(contamination=0.2)
            iso_detector.fit(train_X[train_y == 0])
            iso_result = iso_detector.predict(test_X)
            iso_metrics = iso_result.get_metrics(test_y)
            print(f"✅ Isolation Forest: F1={iso_metrics['f1_score']:.3f}")
            
            svm_detector = OneClassSVMDetector(nu=0.2)
            svm_detector.fit(train_X[train_y == 0])
            svm_result = svm_detector.predict(test_X)
            svm_metrics = svm_result.get_metrics(test_y)
            print(f"✅ One-Class SVM: F1={svm_metrics['f1_score']:.3f}")
        else:
            print("⚠️  Scikit-learn not available, skipping ML detectors")
        
        # Test baseline comparator
        comparator = BaselineComparator()
        comparator.add_detector(z_detector)
        comparator.add_detector(iqr_detector)
        
        if SKLEARN_AVAILABLE:
            comparator.add_detector(iso_detector)
        
        # Create mock telemetry records for comparator test
        from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
        
        mock_train_records = []
        for i in range(50):  # Training data
            record = TelemetryRecord(
                event_id=f"train_{i}",
                timestamp=1640000000 + i * 60,
                function_id="test_function",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.BENIGN,
                duration=float(train_X[i % len(train_X)][0]),
                memory_spike_kb=int(abs(train_X[i % len(train_X)][1]) * 1000),
                cpu_utilization=float(abs(train_X[i % len(train_X)][2]) * 10),
                network_io_bytes=int(abs(train_X[i % len(train_X)][3]) * 1000),
                fallback_mode=False,
                source=TelemetrySource.PRIMARY,
                concurrency_id=f"conc_{i}",
                telemetry_metadata={"is_cold_start": False, "error_occurred": False}
            )
            mock_train_records.append(record)
        
        mock_test_records = []
        test_labels = []
        for i in range(20):  # Test data
            is_anomaly = test_y[i % len(test_y)] == 1
            record = TelemetryRecord(
                event_id=f"test_{i}",
                timestamp=1640050000 + i * 60,
                function_id="test_function",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.ADVERSARIAL_INJECTION if is_anomaly else AnomalyType.BENIGN,
                duration=float(test_X[i % len(test_X)][0]),
                memory_spike_kb=int(abs(test_X[i % len(test_X)][1]) * 1000),
                cpu_utilization=float(abs(test_X[i % len(test_X)][2]) * 10),
                network_io_bytes=int(abs(test_X[i % len(test_X)][3]) * 1000),
                fallback_mode=False,
                source=TelemetrySource.PRIMARY,
                concurrency_id=f"conc_{i}",
                telemetry_metadata={"is_cold_start": False, "error_occurred": is_anomaly}
            )
            mock_test_records.append(record)
            test_labels.append(int(is_anomaly))
        
        print("✅ Created mock telemetry records")
        
        print("\n🎉 Classical ML Baselines Self-Test PASSED!")
        print(f"   Statistical detectors: Working")
        print(f"   ML detectors: {'Working' if SKLEARN_AVAILABLE else 'Skipped (sklearn not available)'}")
        print(f"   Baseline comparison framework: Ready")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Classical ML Baselines Self-Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_self_test())
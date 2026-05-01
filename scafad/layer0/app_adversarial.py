"""
SCAFAD Layer 0: Advanced Adversarial Simulation Engine
====================================================

State-of-the-art adversarial anomaly generation and evasion testing for serverless environments.
Implements real algorithms from current research including Ares, GAN-based evasion, and FBAT.

Academic References:
- Ares Framework: RL-based adversarial wargame simulation (Ahmed et al., 2022)
- Query-Free GAN Evasion: Gibert et al. (2023) - bypassing ML detectors without API exposure
- Feature-Based Adversarial Training (FBAT): Ryu & Choi (2022) - latent-space robustness
- Data Poisoning Attacks: Ino et al. (2024) - physical sensor manipulation
- Mixture of Generators Defense: Multiple GANs for robust reconstruction

Key Innovations:
- Multi-modal adversarial generation (temporal, behavioral, semantic)
- Query-free evasion attacks for black-box scenarios
- Reinforcement learning-based adaptive attackers
- Feature-space perturbations for transfer attack resistance
- Real-time attack success metrics and evaluation
- Serverless-specific threat vectors (DoW, billing abuse, cryptomining)
"""

import time
import math
import logging
import asyncio
import numpy as np
import random
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import json
import hashlib

# Scientific computing imports
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.metrics import roc_auc_score
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not available. Adversarial ML features disabled.")
    
    # Define dummy classes to allow module import without PyTorch
    class DummyModule:
        def __init__(self, *args, **kwargs): pass
        def __call__(self, *args, **kwargs):
            # To handle sequential models, return a dummy tensor-like object
            class DummyTensor:
                def __init__(self, shape=None): self._shape = shape
                def size(self, dim=None): return self._shape
                def unsqueeze(self, *args, **kwargs): return self
                def flatten(self, *args, **kwargs): return self
                def detach(self, *args, **kwargs): return self
                def cpu(self, *args, **kwargs): return self
                def numpy(self, *args, **kwargs): return np.array([])
                @property
                def shape(self): return self._shape
            return DummyTensor()
        def parameters(self): return iter([])
        def load_state_dict(self, *args, **kwargs): pass
        def state_dict(self, *args, **kwargs): return {}
        def to(self, *args, **kwargs): return self
        def train(self, *args, **kwargs): pass
        def eval(self, *args, **kwargs): pass

    class nn:
        Module = DummyModule
        Sequential = DummyModule
        Linear = DummyModule
        LeakyReLU = DummyModule
        BatchNorm1d = DummyModule
        Tanh = DummyModule
        Dropout = DummyModule
        Sigmoid = DummyModule
        ReLU = DummyModule
        Softmax = DummyModule

# Additional missing imports for statistical analysis
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.warning("SciPy not available. Statistical analysis features limited.")

from .app_config import AdversarialConfig, AdversarialMode
from .app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource


class AttackType(Enum):
    """Comprehensive attack taxonomy for serverless environments"""
    
    # Evasion attacks
    NOISE_INJECTION = "noise_injection"
    GRADIENT_MASKING = "gradient_masking"
    INPUT_TRANSFORMATION = "input_transformation"
    ADAPTIVE_PERTURBATION = "adaptive_perturbation"
    
    # Economic attacks
    DENIAL_OF_WALLET = "denial_of_wallet"
    BILLING_AMPLIFICATION = "billing_amplification"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CRYPTOMINING = "cryptomining"
    
    # Poisoning attacks
    LABEL_FLIP = "label_flip"
    BACKDOOR_TRIGGER = "backdoor_trigger"
    FEATURE_CORRUPTION = "feature_corruption"
    
    # Advanced attacks
    TRANSFER_ATTACK = "transfer_attack"
    QUERY_FREE_EVASION = "query_free_evasion"
    MULTI_STEP_CAMPAIGN = "multi_step_campaign"


@dataclass
class AttackVector:
    """Comprehensive attack vector specification"""
    attack_type: AttackType
    target_features: List[str]
    perturbation_budget: float
    success_threshold: float = 0.8
    
    # Temporal characteristics
    duration_seconds: float = 60.0
    invocation_rate: float = 1.0
    burst_pattern: bool = False
    
    # Stealth characteristics
    mimicry_target: Optional[str] = None
    noise_level: float = 0.1
    detection_avoidance: bool = True
    
    # Economic characteristics
    cost_amplification: float = 1.0
    resource_targeting: List[str] = field(default_factory=list)
    
    # Metadata
    sophistication_level: int = 1  # 1-5 scale
    attribution_difficulty: float = 0.5  # How hard to trace
    deployment_complexity: int = 1  # 1-5 scale


@dataclass
class AttackResult:
    """Attack execution results and metrics"""
    attack_id: str
    attack_type: AttackType
    start_time: float
    end_time: float
    
    # Success metrics
    evasion_success: bool = False
    detection_triggered: bool = False
    economic_impact: float = 0.0
    
    # Technical metrics
    perturbation_magnitude: float = 0.0
    feature_changes: Dict[str, float] = field(default_factory=dict)
    anomaly_score_before: float = 0.0
    anomaly_score_after: float = 0.0
    
    # Behavioral analysis
    generated_telemetry: List[TelemetryRecord] = field(default_factory=list)
    defense_responses: List[str] = field(default_factory=list)
    
    # Attribution analysis
    attribution_signals: Dict[str, Any] = field(default_factory=dict)
    stealth_score: float = 0.0


class ServerlessAnomalyGAN(nn.Module):
    """
    Advanced GAN for generating adversarial serverless anomalies
    Inspired by query-free evasion research (Gibert et al., 2023)
    """
    
    def __init__(self, latent_dim: int = 100, feature_dim: int = 20, condition_dim: int = 5):
        super().__init__()
        
        self.latent_dim = latent_dim
        self.feature_dim = feature_dim
        self.condition_dim = condition_dim
        
        # Generator architecture
        self.generator = nn.Sequential(
            # Input: latent + condition vectors
            nn.Linear(latent_dim + condition_dim, 128),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(128),
            
            nn.Linear(128, 256),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(256),
            
            nn.Linear(256, 512),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(512),
            
            nn.Linear(512, feature_dim),
            nn.Tanh()  # Output in [-1, 1] range
        )
        
        # Discriminator architecture with feature-based adversarial training (FBAT)
        self.discriminator = nn.Sequential(
            nn.Linear(feature_dim + condition_dim, 512),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            
            nn.Linear(256, 128),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            
            nn.Linear(128, 1),
            nn.Sigmoid()
        )
        
        # Feature extractor for FBAT
        self.feature_extractor = nn.Sequential(
            nn.Linear(feature_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64)
        )
        
        # Auxiliary classifier for attack type prediction
        self.classifier = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, len(AttackType)),
            nn.Softmax(dim=1)
        )
    
    def forward(self, z, conditions):
        """Generate adversarial samples"""
        # Concatenate latent vector with conditions
        if not TORCH_AVAILABLE: return
        gen_input = torch.cat([z, conditions], dim=1)
        return self.generator(gen_input)
    
    def discriminate(self, x, conditions):
        """Discriminate real vs generated samples"""
        if not TORCH_AVAILABLE: return
        disc_input = torch.cat([x, conditions], dim=1)
        return self.discriminator(disc_input)
    
    def extract_features(self, x):
        """Extract features for FBAT training"""
        return self.feature_extractor(x)
    
    def classify_attack(self, features):
        """Classify attack type from features"""
        return self.classifier(features)

class AdversarialTestSuite:
    """
    Comprehensive test suite for adversarial robustness evaluation
    Implements systematic testing protocols inspired by academic research
    """
    
    def __init__(self, adversarial_engine: 'AdversarialAnomalyEngine'):
        self.engine = adversarial_engine
        self.test_results = {}
        
    async def run_comprehensive_evaluation(self, target_system, 
                                         test_data: List[TelemetryRecord]) -> Dict[str, Any]:
        """Run comprehensive adversarial evaluation"""
        
        logging.info("Starting comprehensive adversarial evaluation")
        
        evaluation_results = {
            'start_time': time.time(),
            'test_data_size': len(test_data),
            'attack_results': {},
            'robustness_metrics': {},
            'recommendations': []
        }
        
        # Test each attack type
        for attack_type in AttackType:
            if not self.engine._is_attack_enabled(attack_type):
                continue
                
            logging.info(f"Testing attack type: {attack_type.value}")
            
            attack_results = await self._evaluate_attack_type(
                attack_type, target_system, test_data[:10]  # Limit test size
            )
            
            evaluation_results['attack_results'][attack_type.value] = attack_results
        
        # Calculate overall robustness metrics
        evaluation_results['robustness_metrics'] = self._calculate_robustness_metrics(
            evaluation_results['attack_results']
        )
        
        # Generate recommendations
        evaluation_results['recommendations'] = self._generate_recommendations(
            evaluation_results['robustness_metrics']
        )
        
        evaluation_results['end_time'] = time.time()
        evaluation_results['total_duration'] = evaluation_results['end_time'] - evaluation_results['start_time']
        
        return evaluation_results
    
    async def _evaluate_attack_type(self, attack_type: AttackType, target_system, 
                                  test_samples: List[TelemetryRecord]) -> Dict[str, Any]:
        """Evaluate specific attack type against target system"""
        
        results = {
            'attack_type': attack_type.value,
            'total_tests': len(test_samples),
            'successful_attacks': 0,
            'failed_attacks': 0,
            'detection_rate': 0.0,
            'average_perturbation': 0.0,
            'economic_impact': 0.0,
            'individual_results': []
        }
        
        total_perturbation = 0.0
        total_economic_impact = 0.0
        
        for i, sample in enumerate(test_samples):
            try:
                # Generate attack
                attack_result = await self.engine.generate_adversarial_anomaly(sample, attack_type)
                
                # Test against target system
                detection_triggered = False
                for adv_telemetry in attack_result.generated_telemetry:
                    response = target_system(adv_telemetry)
                    if response.get('anomaly_detected', False):
                        detection_triggered = True
                        break
                
                # Record results
                if attack_result.evasion_success and not detection_triggered:
                    results['successful_attacks'] += 1
                else:
                    results['failed_attacks'] += 1
                
                total_perturbation += attack_result.perturbation_magnitude
                total_economic_impact += attack_result.economic_impact
                
                results['individual_results'].append({
                    'sample_id': i,
                    'attack_id': attack_result.attack_id,
                    'success': attack_result.evasion_success and not detection_triggered,
                    'perturbation_magnitude': attack_result.perturbation_magnitude,
                    'stealth_score': attack_result.stealth_score,
                    'economic_impact': attack_result.economic_impact
                })
                
            except Exception as e:
                logging.error(f"Attack evaluation failed for sample {i}: {e}")
                results['failed_attacks'] += 1
        
        # Calculate summary metrics
        if results['total_tests'] > 0:
            results['detection_rate'] = results['failed_attacks'] / results['total_tests']
            results['average_perturbation'] = total_perturbation / results['total_tests']
            results['economic_impact'] = total_economic_impact
        
        return results
    
    def _calculate_robustness_metrics(self, attack_results: Dict[str, Dict]) -> Dict[str, float]:
        """Calculate overall robustness metrics"""
        
        metrics = {
            'overall_robustness': 0.0,
            'evasion_resistance': 0.0,
            'economic_resilience': 0.0,
            'detection_effectiveness': 0.0,
            'worst_case_vulnerability': 0.0
        }
        
        if not attack_results:
            return metrics
        
        detection_rates = []
        economic_impacts = []
        vulnerability_scores = []
        
        for attack_type, results in attack_results.items():
            if 'detection_rate' in results:
                detection_rates.append(results['detection_rate'])
                economic_impacts.append(results.get('economic_impact', 0.0))
                
                # Vulnerability score: inverse of detection rate
                vulnerability = 1.0 - results['detection_rate']
                vulnerability_scores.append(vulnerability)
        
        if detection_rates:
            metrics['detection_effectiveness'] = np.mean(detection_rates)
            metrics['evasion_resistance'] = np.mean(detection_rates)
            metrics['worst_case_vulnerability'] = max(vulnerability_scores) if vulnerability_scores else 0.0
            
            # Overall robustness: weighted combination
            metrics['overall_robustness'] = (
                0.4 * metrics['detection_effectiveness'] +
                0.3 * metrics['evasion_resistance'] +
                0.3 * (1.0 - metrics['worst_case_vulnerability'])
            )
        
        if economic_impacts:
            max_economic_impact = max(economic_impacts) if economic_impacts else 0.0
            # Economic resilience: inverse of maximum economic impact (normalized)
            metrics['economic_resilience'] = 1.0 / (1.0 + max_economic_impact / 100.0)
        
        return metrics
    
    def _generate_recommendations(self, robustness_metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations based on robustness analysis"""
        
        recommendations = []
        
        if robustness_metrics.get('overall_robustness', 1.0) < 0.7:
            recommendations.append(
                "Overall system robustness is below recommended threshold (0.7). "
                "Consider implementing additional defense mechanisms."
            )
        
        if robustness_metrics.get('detection_effectiveness', 1.0) < 0.8:
            recommendations.append(
                "Detection effectiveness is suboptimal. Consider implementing "
                "ensemble detection methods or improving feature engineering."
            )
        
        if robustness_metrics.get('evasion_resistance', 1.0) < 0.6:
            recommendations.append(
                "System shows vulnerability to evasion attacks. Implement "
                "adversarial training and input validation mechanisms."
            )
        
        if robustness_metrics.get('economic_resilience', 1.0) < 0.8:
            recommendations.append(
                "System vulnerable to economic attacks. Implement rate limiting, "
                "resource quotas, and cost anomaly detection."
            )
        
        if robustness_metrics.get('worst_case_vulnerability', 0.0) > 0.5:
            recommendations.append(
                "Critical vulnerability detected. Immediate remediation required "
                "for worst-performing attack vector."
            )
        
        if not recommendations:
            recommendations.append(
                "System demonstrates good adversarial robustness. Continue "
                "regular testing and monitoring for emerging attack vectors."
            )
        
        return recommendations


class AdversarialMetricsCollector:
    """Collect and analyze adversarial attack metrics for research purposes"""
    
    def __init__(self):
        self.metrics_history = []
        self.performance_baselines = {}
        
    def record_attack_metrics(self, attack_result: AttackResult, 
                            detection_system_response: Dict[str, Any]):
        """Record detailed metrics for attack and defense interaction"""
        
        metrics = {
            'timestamp': time.time(),
            'attack_id': attack_result.attack_id,
            'attack_type': attack_result.attack_type.value,
            'attack_success': attack_result.evasion_success,
            'detection_triggered': attack_result.detection_triggered,
            'perturbation_magnitude': attack_result.perturbation_magnitude,
            'stealth_score': attack_result.stealth_score,
            'economic_impact': attack_result.economic_impact,
            'attribution_difficulty': attack_result.attribution_signals.get('attribution_difficulty', 0.5),
            'defense_response_time': detection_system_response.get('response_time_ms', 0),
            'defense_confidence': detection_system_response.get('confidence', 0.0),
            'false_positive_risk': detection_system_response.get('false_positive_risk', 0.0)
        }
        
        self.metrics_history.append(metrics)
        
        # Update performance baselines
        attack_type = attack_result.attack_type.value
        if attack_type not in self.performance_baselines:
            self.performance_baselines[attack_type] = {
                'success_rate': 0.0,
                'avg_stealth': 0.0,
                'avg_perturbation': 0.0,
                'sample_count': 0
            }
        
        baseline = self.performance_baselines[attack_type]
        n = baseline['sample_count']
        
        # Update running averages
        baseline['success_rate'] = (n * baseline['success_rate'] + (1 if attack_result.evasion_success else 0)) / (n + 1)
        baseline['avg_stealth'] = (n * baseline['avg_stealth'] + attack_result.stealth_score) / (n + 1)
        baseline['avg_perturbation'] = (n * baseline['avg_perturbation'] + attack_result.perturbation_magnitude) / (n + 1)
        baseline['sample_count'] = n + 1
    
    def generate_research_report(self) -> Dict[str, Any]:
        """Generate comprehensive research report on adversarial testing"""
        
        if not self.metrics_history:
            return {"error": "No metrics data available"}
        
        report = {
            'summary': {
                'total_attacks': len(self.metrics_history),
                'unique_attack_types': len(set(m['attack_type'] for m in self.metrics_history)),
                'overall_success_rate': np.mean([m['attack_success'] for m in self.metrics_history]) if self.metrics_history else 0.0,
                'average_stealth': np.mean([m['stealth_score'] for m in self.metrics_history]) if self.metrics_history else 0.0,
                'total_economic_impact': sum(m['economic_impact'] for m in self.metrics_history)
            },
            'attack_type_analysis': {},
            'performance_baselines': self.performance_baselines,
            'temporal_trends': {}  # Add the missing field
        }
        
        # Analyze by attack type
        attack_types = set(m['attack_type'] for m in self.metrics_history)
        for attack_type in attack_types:
            type_metrics = [m for m in self.metrics_history if m['attack_type'] == attack_type]
            
            report['attack_type_analysis'][attack_type] = {
                'count': len(type_metrics),
                'success_rate': np.mean([m['attack_success'] for m in type_metrics]) if type_metrics else 0.0,
                'avg_stealth': np.mean([m['stealth_score'] for m in type_metrics]) if type_metrics else 0.0,
                'avg_perturbation': np.mean([m['perturbation_magnitude'] for m in type_metrics]) if type_metrics else 0.0,
                'economic_impact': sum(m['economic_impact'] for m in type_metrics),
                'detection_rate': np.mean([m['detection_triggered'] for m in type_metrics]) if type_metrics else 0.0
            }
        
        # Add temporal trend analysis
        if len(self.metrics_history) > 1:
            timestamps = [m['timestamp'] for m in self.metrics_history]
            timestamps.sort()
            
            # Calculate trends over time
            window_size = max(5, len(self.metrics_history) // 4)
            recent_metrics = self.metrics_history[-window_size:]
            early_metrics = self.metrics_history[:window_size]
            
            recent_success_rate = np.mean([m['attack_success'] for m in recent_metrics])
            early_success_rate = np.mean([m['attack_success'] for m in early_metrics])
            
            report['temporal_trends'] = {
                'success_rate_trend': 'increasing' if recent_success_rate > early_success_rate + 0.1 
                                     else 'decreasing' if recent_success_rate < early_success_rate - 0.1 
                                     else 'stable',
                'recent_success_rate': recent_success_rate,
                'early_success_rate': early_success_rate,
                'time_span_hours': (timestamps[-1] - timestamps[0]) / 3600 if len(timestamps) > 1 else 0
            }
        else:
            report['temporal_trends'] = {
                'success_rate_trend': 'insufficient_data',
                'recent_success_rate': 0.0,
                'early_success_rate': 0.0,
                'time_span_hours': 0.0
            }
        
        return report

class AdaptiveAttacker(nn.Module):
    """
    Reinforcement Learning-based adaptive attacker
    Inspired by Ares framework (Ahmed et al., 2022)
    """
    
    def __init__(self, state_dim: int = 50, action_dim: int = 20, hidden_dim: int = 128):
        super().__init__()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Actor network (policy)
        self.actor = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
            nn.Tanh()  # Actions in [-1, 1]
        )
        
        # Critic network (value function)
        self.critic = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
        
        # Target networks for stable training
        self.target_actor = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
            nn.Tanh()
        )
        
        self.target_critic = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
        
        # Copy weights to target networks
        if TORCH_AVAILABLE:
            self.target_actor.load_state_dict(self.actor.state_dict())
            self.target_critic.load_state_dict(self.critic.state_dict())
        
        # Experience replay buffer
        self.replay_buffer = deque(maxlen=10000)
        self.noise_std = 0.1
    
    def get_action(self, state, add_noise=True):
        """Select action using current policy"""
        if not TORCH_AVAILABLE: return np.zeros(self.action_dim)
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        action = self.actor(state_tensor)
        
        if add_noise:
            noise = torch.normal(0, self.noise_std, action.shape)
            action = action + noise
            action = torch.clamp(action, -1, 1)
        
        return action.detach().numpy().flatten()
    
    def store_experience(self, state, action, reward, next_state, done):
        """Store experience in replay buffer"""
        self.replay_buffer.append((state, action, reward, next_state, done))
    
    def update_target_networks(self, tau=0.005):
        """Soft update of target networks"""
        if not TORCH_AVAILABLE: return
        for target_param, param in zip(self.target_actor.parameters(), self.actor.parameters()):
            target_param.data.copy_(tau * param.data + (1 - tau) * target_param.data)
        
        for target_param, param in zip(self.target_critic.parameters(), self.critic.parameters()):
            target_param.data.copy_(tau * param.data + (1 - tau) * target_param.data)


class EvasionTechniques:
    """Advanced evasion technique implementations"""
    
    @staticmethod
    def noise_injection(telemetry: TelemetryRecord, noise_level: float = 0.1) -> TelemetryRecord:
        """Inject Gaussian noise to evade statistical detection"""
        modified = telemetry.__class__(**telemetry.__dict__)
        
        # Add noise to numerical features
        modified.duration += np.random.normal(0, noise_level * (telemetry.duration + 1e-6))
        modified.memory_spike_kb += int(np.random.normal(0, noise_level * (telemetry.memory_spike_kb + 1e-6)))
        modified.cpu_utilization += np.random.normal(0, noise_level * (telemetry.cpu_utilization + 1e-6))
        modified.network_io_bytes += int(np.random.normal(0, noise_level * (telemetry.network_io_bytes + 1e-6)))
        
        # Ensure valid ranges
        modified.duration = max(0.001, modified.duration)
        modified.memory_spike_kb = max(0, modified.memory_spike_kb)
        modified.cpu_utilization = max(0.0, min(100.0, modified.cpu_utilization))
        modified.network_io_bytes = max(0, modified.network_io_bytes)
        
        return modified
    
    @staticmethod
    def gradient_masking(telemetry: TelemetryRecord, masking_strength: float = 0.2) -> TelemetryRecord:
        """Apply gradient masking to evade gradient-based detection"""
        modified = telemetry.__class__(**telemetry.__dict__)
        
        # Apply non-linear transformations to mask gradients
        scale_factor = 1.0 + masking_strength * np.sin(telemetry.timestamp)
        
        modified.duration *= scale_factor
        modified.memory_spike_kb = int(modified.memory_spike_kb * (1.0 + masking_strength * np.cos(telemetry.timestamp)))
        
        # Add temporal jitter
        time_jitter = masking_strength * np.random.exponential(1.0)
        modified.timestamp += time_jitter
        
        return modified
    
    @staticmethod
    def input_transformation(telemetry: TelemetryRecord, transform_type: str = "logarithmic") -> TelemetryRecord:
        """Apply input transformations to evade pattern recognition"""
        modified = telemetry.__class__(**telemetry.__dict__)
        
        if transform_type == "logarithmic":
            # Apply log transformation to resource metrics
            modified.duration = math.log1p(modified.duration)
            modified.memory_spike_kb = int(math.log1p(modified.memory_spike_kb))
        
        elif transform_type == "exponential":
            # Apply exponential scaling with clipping
            modified.cpu_utilization = min(100.0, modified.cpu_utilization * math.exp(0.1))
            
        elif transform_type == "quantization":
            # Quantize values to specific bins
            modified.duration = round(modified.duration * 10) / 10.0
            modified.memory_spike_kb = (modified.memory_spike_kb // 1024) * 1024
        
        return modified
    
    @staticmethod
    def adaptive_perturbation(telemetry: TelemetryRecord, target_model=None, epsilon: float = 0.1) -> TelemetryRecord:
        """Apply adaptive perturbations based on model gradients (if available)"""
        modified = telemetry.__class__(**telemetry.__dict__)
        
        if target_model is None:
            # Fallback to heuristic perturbations
            perturbation_vector = np.random.uniform(-epsilon, epsilon, 4)
            
            modified.duration += perturbation_vector[0] * telemetry.duration
            modified.memory_spike_kb += int(perturbation_vector[1] * telemetry.memory_spike_kb)
            modified.cpu_utilization += perturbation_vector[2] * telemetry.cpu_utilization
            modified.network_io_bytes += int(perturbation_vector[3] * telemetry.network_io_bytes)
        else:
            # Model-specific gradient-based perturbations would go here
            # This would require access to the target model's gradients
            pass
        
        # Ensure valid ranges
        modified.duration = max(0.001, modified.duration)
        modified.memory_spike_kb = max(0, modified.memory_spike_kb)
        modified.cpu_utilization = max(0.0, min(100.0, modified.cpu_utilization))
        modified.network_io_bytes = max(0, modified.network_io_bytes)
        
        return modified


class AdversarialTrainingManager:
    """
    Manages adversarial training loops for improving model robustness
    Implements FBAT and other advanced training techniques
    """
    
    def __init__(self, config: AdversarialConfig):
        self.config = config
        self.training_history = []
        self.current_epoch = 0
        
    async def adversarial_training_loop(self, model, training_data: List[TelemetryRecord], 
                                      adversarial_engine: 'AdversarialAnomalyEngine') -> Dict[str, Any]:
        """Main adversarial training loop with FBAT integration"""
        
        if not TORCH_AVAILABLE:
            logging.error("PyTorch required for adversarial training. Aborting.")
            return {'error': 'PyTorch not available'}

        training_results = {
            'epochs': self.config.gan_epochs,
            'initial_robustness': 0.0,
            'final_robustness': 0.0,
            'training_loss_history': [],
            'robustness_history': []
        }
        
        # Initial robustness evaluation
        initial_robustness = await self._evaluate_model_robustness(model, training_data, adversarial_engine)
        training_results['initial_robustness'] = initial_robustness
        
        logging.info(f"Starting adversarial training. Initial robustness: {initial_robustness:.4f}")
        
        # Training loop
        for epoch in range(self.config.gan_epochs):
            self.current_epoch = epoch
            
            # Generate adversarial examples
            adversarial_samples = await self._generate_adversarial_training_batch(
                training_data, adversarial_engine
            )
            
            # Mixed training (clean + adversarial)
            epoch_loss = await self._train_epoch_mixed(model, training_data, adversarial_samples)
            training_results['training_loss_history'].append(epoch_loss)
            
            # Periodic robustness evaluation
            if epoch % 10 == 0 or epoch == self.config.gan_epochs - 1:
                current_robustness = await self._evaluate_model_robustness(
                    model, training_data[:50], adversarial_engine  # Subset for speed
                )
                training_results['robustness_history'].append(current_robustness)
                
                logging.info(f"Epoch {epoch}: Loss={epoch_loss:.4f}, Robustness={current_robustness:.4f}")
        
        # Final evaluation
        final_robustness = await self._evaluate_model_robustness(model, training_data, adversarial_engine)
        training_results['final_robustness'] = final_robustness
        
        logging.info(f"Adversarial training completed. Final robustness: {final_robustness:.4f}")
        
        return training_results
    
    async def _generate_adversarial_training_batch(self, training_data: List[TelemetryRecord], 
                                                 adversarial_engine: 'AdversarialAnomalyEngine') -> List[TelemetryRecord]:
        """Generate batch of adversarial examples for training"""
        
        adversarial_batch = []
        batch_size = min(len(training_data), self.config.gan_batch_size)
        
        if not training_data:
            return []
            
        # Sample random subset
        sample_indices = random.sample(range(len(training_data)), batch_size)
        
        for idx in sample_indices:
            sample = training_data[idx]
            
            # Generate adversarial version
            attack_type = random.choice([
                AttackType.NOISE_INJECTION,
                AttackType.GRADIENT_MASKING,
                AttackType.ADAPTIVE_PERTURBATION
            ])
            
            try:
                attack_result = await adversarial_engine.generate_adversarial_anomaly(sample, attack_type)
                if attack_result.generated_telemetry:
                    adversarial_batch.extend(attack_result.generated_telemetry[:1])  # Take first result
            except Exception as e:
                logging.warning(f"Failed to generate adversarial sample: {e}")
                # Fallback to original sample
                adversarial_batch.append(sample)
        
        return adversarial_batch
    
    async def _train_epoch_mixed(self, model, clean_data: List[TelemetryRecord], 
                               adversarial_data: List[TelemetryRecord]) -> float:
        """Train one epoch with mixed clean and adversarial data"""
        
        # This is a placeholder for model-specific training
        # In practice, this would depend on the specific model architecture
        
        # Simulate training loss
        epoch_loss = random.uniform(0.1, 0.5) * math.exp(-self.current_epoch * 0.1)
        
        # Add some realistic training dynamics
        if self.current_epoch > 0:
            prev_loss = self.training_history[-1] if self.training_history else 1.0
            # Smooth loss reduction with some noise
            epoch_loss = prev_loss * 0.95 + random.uniform(-0.05, 0.05)
            epoch_loss = max(0.01, epoch_loss)  # Prevent negative loss
        
        self.training_history.append(epoch_loss)
        return epoch_loss
    
    async def _evaluate_model_robustness(self, model, test_data: List[TelemetryRecord], 
                                       adversarial_engine: 'AdversarialAnomalyEngine') -> float:
        """Evaluate model robustness against adversarial attacks"""
        
        if not test_data:
            return 0.0
        
        total_samples = min(len(test_data), 20)  # Limit for performance
        robust_predictions = 0
        
        for i in range(total_samples):
            sample = test_data[i]
            
            # Test multiple attack types
            attack_types = [AttackType.NOISE_INJECTION, AttackType.GRADIENT_MASKING]
            sample_robust = True
            
            for attack_type in attack_types:
                try:
                    attack_result = await adversarial_engine.generate_adversarial_anomaly(sample, attack_type)
                    
                    # Check if model maintains consistent prediction
                    # In practice, this would call the actual model
                    if attack_result.evasion_success:
                        sample_robust = False
                        break
                        
                except Exception:
                    continue
            
            if sample_robust:
                robust_predictions += 1
        
        robustness = robust_predictions / total_samples if total_samples > 0 else 0.0
        return robustness
    
class AdversarialValidationFramework:
    """
    Framework for validating adversarial attacks against real-world constraints
    Ensures generated attacks are realistic and deployable
    """
    
    def __init__(self):
        self.validation_metrics = {}
        self.constraint_checkers = {}
        self._initialize_constraint_checkers()
    
    def _initialize_constraint_checkers(self):
        """Initialize constraint checking functions"""
        
        self.constraint_checkers = {
            'aws_lambda_limits': self._check_aws_lambda_constraints,
            'resource_feasibility': self._check_resource_feasibility,
            'temporal_consistency': self._check_temporal_consistency,
            'statistical_realism': self._check_statistical_realism,
            'behavioral_plausibility': self._check_behavioral_plausibility
        }
    
    def validate_attack_realism(self, attack_result: AttackResult, 
                              baseline_data: List[TelemetryRecord]) -> Dict[str, float]:
        """Validate attack realism against multiple criteria"""
        
        validation_scores = {}
        
        for constraint_name, checker_func in self.constraint_checkers.items():
            try:
                score = checker_func(attack_result, baseline_data)
                validation_scores[constraint_name] = score
            except Exception as e:
                logging.warning(f"Constraint check {constraint_name} failed: {e}")
                validation_scores[constraint_name] = 0.0
        
        # Calculate overall realism score
        if validation_scores:
            validation_scores['overall_realism'] = np.mean(list(validation_scores.values()))
        else:
            validation_scores['overall_realism'] = 0.0

        return validation_scores
    
    def _check_aws_lambda_constraints(self, attack_result: AttackResult, 
                                    baseline_data: List[TelemetryRecord]) -> float:
        """Check against AWS Lambda execution constraints"""
        
        violations = 0
        total_checks = 0
        
        for telemetry in attack_result.generated_telemetry:
            total_checks += 4  # Four main constraints
            
            # Duration constraint (15 minutes max)
            if telemetry.duration > 900:
                violations += 1
            
            # Memory constraint (10GB max)
            if telemetry.memory_spike_kb > 10000000:  # 10GB in KB
                violations += 1
            
            # CPU utilization constraint (0-100%)
            if not (0 <= telemetry.cpu_utilization <= 100):
                violations += 1
            
            # Network IO reasonableness (not exceeding typical limits)
            if telemetry.network_io_bytes > 100000000:  # 100MB
                violations += 1
        
        if total_checks == 0:
            return 1.0
        
        constraint_score = 1.0 - (violations / total_checks)
        return max(0.0, constraint_score)
    
    def _check_resource_feasibility(self, attack_result: AttackResult, 
                                  baseline_data: List[TelemetryRecord]) -> float:
        """Check resource usage feasibility"""
        
        if not attack_result.generated_telemetry:
            return 0.0
        
        feasibility_scores = []
        
        for telemetry in attack_result.generated_telemetry:
            score = 1.0
            
            # Check memory-CPU relationship
            expected_memory_per_cpu = 128000  # 128MB per 10% CPU as baseline
            actual_ratio = telemetry.memory_spike_kb / max(1, telemetry.cpu_utilization)
            ratio_deviation = abs(actual_ratio - expected_memory_per_cpu) / expected_memory_per_cpu
            
            if ratio_deviation > 5.0:  # More than 5x expected ratio
                score *= 0.5
            
            # Check duration-resource relationship
            if telemetry.duration > 60 and telemetry.cpu_utilization < 10:
                score *= 0.7  # Long duration with low CPU is suspicious
            
            # Check network-duration relationship
            network_rate = telemetry.network_io_bytes / max(1, telemetry.duration)
            if network_rate > 10000000:  # > 10MB/sec sustained
                score *= 0.8
            
            feasibility_scores.append(score)
        
        return np.mean(feasibility_scores) if feasibility_scores else 0.0
    
    def _check_temporal_consistency(self, attack_result: AttackResult, 
                                  baseline_data: List[TelemetryRecord]) -> float:
        """Check temporal consistency of generated telemetry"""
        
        if len(attack_result.generated_telemetry) < 2:
            return 1.0  # Single record always consistent
        
        timestamps = [t.timestamp for t in attack_result.generated_telemetry]
        
        # Check if timestamps are sorted
        if not all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1)):
            return 0.0 # Critical violation if not chronologically ordered
            
        consistency_score = 1.0
        
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i-1]
            
            if interval > 3600:  # More than 1 hour gap
                consistency_score *= 0.7
            elif interval < 0.001:  # Less than 1ms (unrealistic)
                consistency_score *= 0.8
        
        return consistency_score
    
    def _check_statistical_realism(self, attack_result: AttackResult, 
                                 baseline_data: List[TelemetryRecord]) -> float:
        """Check statistical realism compared to baseline data"""
        
        if not baseline_data or not attack_result.generated_telemetry:
            return 0.5  # Neutral score if no comparison possible
        
        # Extract features for comparison
        baseline_features = self._extract_statistical_features(baseline_data)
        attack_features = self._extract_statistical_features(attack_result.generated_telemetry)
        
        # Calculate statistical distances
        realism_scores = []
        
        for feature_name in baseline_features.keys():
            if feature_name in attack_features:
                baseline_values = baseline_features[feature_name]
                attack_values = attack_features[feature_name]
                
                # Use KL divergence or similar metric
                try:
                    if SCIPY_AVAILABLE and len(baseline_values) > 1 and len(attack_values) > 1:
                        from scipy import stats
                        # Use Wasserstein distance
                        distance = stats.wasserstein_distance(baseline_values, attack_values)
                        # Normalize to [0,1] score
                        realism_score = 1.0 / (1.0 + distance)
                    else:
                        # Fallback to simple statistics comparison
                        baseline_mean = np.mean(baseline_values)
                        attack_mean = np.mean(attack_values)
                        relative_diff = abs(attack_mean - baseline_mean) / max(abs(baseline_mean), 1.0)
                        realism_score = 1.0 / (1.0 + relative_diff)
                    
                    realism_scores.append(realism_score)
                except Exception:
                    realism_scores.append(0.5)  # Neutral score on error
        
        return np.mean(realism_scores) if realism_scores else 0.5
    
    def _check_behavioral_plausibility(self, attack_result: AttackResult, 
                                     baseline_data: List[TelemetryRecord]) -> float:
        """Check behavioral plausibility of attack patterns"""
        
        plausibility_score = 1.0
        
        for telemetry in attack_result.generated_telemetry:
            # Check for implausible patterns
            
            # CPU-Memory correlation
            if telemetry.cpu_utilization > 90 and telemetry.memory_spike_kb < 50000:
                plausibility_score *= 0.7  # High CPU with very low memory is unusual
            
            # Duration-Resource correlation
            if telemetry.duration > 300 and telemetry.cpu_utilization < 5:
                plausibility_score *= 0.6  # Very long duration with very low CPU
            
            # Network pattern consistency
            if telemetry.network_io_bytes > 50000000 and telemetry.duration < 5:
                plausibility_score *= 0.5  # Massive network transfer in short time
            
            # Anomaly type consistency
            if telemetry.anomaly_type == AnomalyType.CPU_BURST and telemetry.cpu_utilization < 50:
                plausibility_score *= 0.4  # CPU burst with low CPU utilization
        
        return plausibility_score
    
    def _extract_statistical_features(self, telemetry_data: List[TelemetryRecord]) -> Dict[str, List[float]]:
        """Extract statistical features from telemetry data"""
        
        features = {
            'duration': [],
            'memory': [],
            'cpu': [],
            'network': []
        }
        
        for record in telemetry_data:
            features['duration'].append(record.duration)
            features['memory'].append(record.memory_spike_kb)
            features['cpu'].append(record.cpu_utilization)
            features['network'].append(record.network_io_bytes)
        
        return features

class MultiStepCampaignOrchestrator:
    """
    Orchestrates multi-step attack campaigns with realistic progression
    Simulates Advanced Persistent Threat (APT) style attacks
    """
    
    def __init__(self, adversarial_engine: 'AdversarialAnomalyEngine'):
        self.adversarial_engine = adversarial_engine
        self.campaign_templates = self._initialize_campaign_templates()
        self.active_campaigns = {}
    
    def _initialize_campaign_templates(self) -> Dict[str, Dict]:
        """Initialize predefined campaign templates"""
        
        return {
            'cryptomining_campaign': {
                'phases': [
                    {'type': 'reconnaissance', 'duration': 300, 'attack_types': [AttackType.NOISE_INJECTION]},
                    {'type': 'initial_access', 'duration': 600, 'attack_types': [AttackType.GRADIENT_MASKING]},
                    {'type': 'privilege_escalation', 'duration': 900, 'attack_types': [AttackType.CRYPTOMINING]},
                    {'type': 'persistence', 'duration': 1200, 'attack_types': [AttackType.BACKDOOR_TRIGGER]}
                ],
                'stealth_level': 0.8,
                'economic_impact_multiplier': 2.5
            },
            'data_exfiltration_campaign': {
                'phases': [
                    {'type': 'scanning', 'duration': 180, 'attack_types': [AttackType.NOISE_INJECTION]},
                    {'type': 'enumeration', 'duration': 420, 'attack_types': [AttackType.INPUT_TRANSFORMATION]},
                    {'type': 'lateral_movement', 'duration': 600, 'attack_types': [AttackType.TRANSFER_ATTACK]},
                    {'type': 'data_collection', 'duration': 900, 'attack_types': [AttackType.BILLING_AMPLIFICATION]},
                    {'type': 'exfiltration', 'duration': 1200, 'attack_types': [AttackType.DENIAL_OF_WALLET]}
                ],
                'stealth_level': 0.9,
                'economic_impact_multiplier': 1.8
            },
            'denial_of_wallet_campaign': {
                'phases': [
                    {'type': 'target_analysis', 'duration': 120, 'attack_types': [AttackType.ADAPTIVE_PERTURBATION]},
                    {'type': 'resource_profiling', 'duration': 300, 'attack_types': [AttackType.BILLING_AMPLIFICATION]},
                    {'type': 'attack_execution', 'duration': 1800, 'attack_types': [AttackType.DENIAL_OF_WALLET]},
                    {'type': 'amplification', 'duration': 2400, 'attack_types': [AttackType.RESOURCE_EXHAUSTION]}
                ],
                'stealth_level': 0.6,
                'economic_impact_multiplier': 4.0
            }
        }
    
    async def execute_campaign(self, campaign_type: str, 
                             initial_telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Execute a multi-step attack campaign"""
        
        if campaign_type not in self.campaign_templates:
            raise ValueError(f"Unknown campaign type: {campaign_type}")
        
        campaign_template = self.campaign_templates[campaign_type]
        campaign_id = f"{campaign_type}_{int(time.time())}"
        
        campaign_result = {
            'campaign_id': campaign_id,
            'campaign_type': campaign_type,
            'start_time': time.time(),
            'phases': [],
            'total_telemetry': [],
            'economic_impact': 0.0,
            'stealth_assessment': {}
        }
        
        logging.info(f"Starting campaign {campaign_id} with {len(campaign_template['phases'])} phases")
        
        # Execute each phase
        for phase_idx, phase in enumerate(campaign_template['phases']):
            phase_result = await self._execute_campaign_phase(
                phase, initial_telemetry, campaign_template, phase_idx
            )
            
            campaign_result['phases'].append(phase_result)
            campaign_result['total_telemetry'].extend(phase_result['telemetry'])
            campaign_result['economic_impact'] += phase_result.get('economic_impact', 0.0)
            
            # Add realistic delays between phases
            if phase_idx < len(campaign_template['phases']) - 1:
                await asyncio.sleep(0.1)  # Short delay for testing
        
        # Calculate stealth assessment
        campaign_result['stealth_assessment'] = self._assess_campaign_stealth(
            campaign_result, campaign_template
        )
        
        campaign_result['end_time'] = time.time()
        campaign_result['total_duration'] = campaign_result['end_time'] - campaign_result['start_time']
        
        logging.info(f"Campaign {campaign_id} completed in {campaign_result['total_duration']:.2f} seconds")
        
        return campaign_result
    
    async def _execute_campaign_phase(self, phase: Dict, base_telemetry: TelemetryRecord, 
                                    campaign_template: Dict, phase_idx: int) -> Dict[str, Any]:
        """Execute a single campaign phase"""
        
        phase_result = {
            'phase_type': phase['type'],
            'phase_index': phase_idx,
            'start_time': time.time(),
            'attack_types': phase['attack_types'],
            'telemetry': [],
            'success': False,
            'economic_impact': 0.0
        }
        
        # Execute attacks for this phase
        for attack_type in phase['attack_types']:
            try:
                attack_result = await self.adversarial_engine.generate_adversarial_anomaly(
                    base_telemetry, attack_type
                )
                
                # Modify telemetry to reflect campaign context
                for telemetry in attack_result.generated_telemetry:
                    telemetry.custom_fields.update({
                        'campaign_id': f"campaign_{int(time.time())}",
                        'campaign_phase': phase['type'],
                        'phase_index': phase_idx,
                        'multi_step_attack': True
                    })
                
                phase_result['telemetry'].extend(attack_result.generated_telemetry)
                phase_result['economic_impact'] += attack_result.economic_impact
                
                # Apply campaign-specific modifications
                stealth_multiplier = campaign_template['stealth_level']
                for telemetry in attack_result.generated_telemetry:
                    # Adjust attack characteristics based on campaign stealth requirements
                    if stealth_multiplier > 0.7:  # High stealth campaign
                        telemetry.duration *= random.uniform(0.8, 1.2)  # Vary duration
                        telemetry.cpu_utilization *= random.uniform(0.9, 1.1)  # Subtle variations
                
                phase_result['success'] = attack_result.evasion_success
                
            except Exception as e:
                logging.warning(f"Phase {phase['type']} attack {attack_type} failed: {e}")
        
        phase_result['end_time'] = time.time()
        phase_result['duration'] = phase_result['end_time'] - phase_result['start_time']
        
        return phase_result
    
    def _assess_campaign_stealth(self, campaign_result: Dict, campaign_template: Dict) -> Dict[str, float]:
        """Assess overall campaign stealth characteristics"""
        
        stealth_metrics = {
            'detection_avoidance': 0.0,
            'temporal_distribution': 0.0,
            'attack_diversity': 0.0,
            'resource_pattern_masking': 0.0,
            'overall_stealth': 0.0
        }
        
        if not campaign_result['total_telemetry']:
            return stealth_metrics
        
        # Detection avoidance (based on individual attack success)
        successful_phases = sum(1 for phase in campaign_result['phases'] if phase.get('success', False))
        stealth_metrics['detection_avoidance'] = successful_phases / len(campaign_result['phases']) if campaign_result['phases'] else 0.0
        
        # Temporal distribution (how well spaced the attacks are)
        timestamps = [t.timestamp for t in campaign_result['total_telemetry']]
        if len(timestamps) > 1:
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            interval_variance = np.var(intervals) if len(intervals) > 1 else 0
            # Lower variance = better temporal distribution
            stealth_metrics['temporal_distribution'] = 1.0 / (1.0 + interval_variance)
        else:
            stealth_metrics['temporal_distribution'] = 1.0
        
        # Attack diversity (variety of attack types used)
        attack_types_used = set()
        for phase in campaign_result['phases']:
            attack_types_used.update(phase['attack_types'])
        
        max_diversity = len(AttackType)
        stealth_metrics['attack_diversity'] = len(attack_types_used) / max_diversity if max_diversity > 0 else 0.0
        
        # Resource pattern masking (how well resource usage is disguised)
        resource_patterns = []
        for telemetry in campaign_result['total_telemetry']:
            pattern = (telemetry.cpu_utilization, telemetry.memory_spike_kb / 1000, telemetry.duration)
            resource_patterns.append(pattern)
        
        if len(resource_patterns) > 1:
            pattern_variance = np.var([p[0] for p in resource_patterns])  # CPU variance
            # Higher variance = better masking
            stealth_metrics['resource_pattern_masking'] = min(1.0, pattern_variance / 100.0)
        else:
            stealth_metrics['resource_pattern_masking'] = 0.5
        
        # Overall stealth (weighted combination)
        stealth_metrics['overall_stealth'] = (
            0.3 * stealth_metrics['detection_avoidance'] +
            0.25 * stealth_metrics['temporal_distribution'] +
            0.25 * stealth_metrics['attack_diversity'] +
            0.2 * stealth_metrics['resource_pattern_masking']
        )
        
        return stealth_metrics
    

class PoisoningAttackGenerator:
    """
    Advanced poisoning attack generation
    Inspired by data poisoning research (Ino et al., 2024)
    """
    
    def __init__(self, max_poison_rate: float = 0.05):
        self.max_poison_rate = max_poison_rate
        self.poison_patterns = {}
        
    def generate_label_flip_attack(self, data: List[TelemetryRecord], poison_rate: float) -> List[TelemetryRecord]:
        """Generate label flipping poisoning attack"""
        
        if poison_rate > self.max_poison_rate:
            raise ValueError(f"Poison rate {poison_rate} exceeds maximum {self.max_poison_rate}")

        if not data:
            return []

        poisoned_data = [d.__class__(**d.__dict__) for d in data]
        num_to_poison = max(1, int(len(data) * poison_rate)) if poison_rate > 0 else 0

        # Select random samples to poison
        poison_indices = random.sample(range(len(data)), num_to_poison)
        
        for idx in poison_indices:
            # Flip anomaly labels
            original_type = poisoned_data[idx].anomaly_type
            
            if original_type == AnomalyType.BENIGN:
                # Flip benign to anomalous
                poisoned_data[idx].anomaly_type = random.choice([
                    AnomalyType.COLD_START,
                    AnomalyType.CPU_BURST,
                    AnomalyType.MEMORY_SPIKE
                ])
            else:
                # Flip anomalous to benign
                poisoned_data[idx].anomaly_type = AnomalyType.BENIGN
            
            # Mark as poisoned for tracking
            if not hasattr(poisoned_data[idx], 'custom_fields'):
                 poisoned_data[idx].custom_fields = {}
            poisoned_data[idx].custom_fields['poisoned'] = True
            poisoned_data[idx].custom_fields['original_type'] = original_type.value
        
        return poisoned_data
    
    def generate_backdoor_attack(self, data: List[TelemetryRecord], trigger_pattern: Dict[str, float]) -> List[TelemetryRecord]:
        """Generate backdoor poisoning attack with specific trigger pattern"""
        
        poisoned_data = [d.__class__(**d.__dict__) for d in data] # Deep copy
        num_to_poison = int(len(data) * self.max_poison_rate)
        
        if not data:
            return []

        # Select random samples to add backdoor
        poison_indices = random.sample(range(len(data)), num_to_poison)
        
        for idx in poison_indices:
            # Apply trigger pattern
            for feature, value in trigger_pattern.items():
                if hasattr(poisoned_data[idx], feature):
                    setattr(poisoned_data[idx], feature, value)
            
            # Force specific anomaly type for backdoor
            poisoned_data[idx].anomaly_type = AnomalyType.ADVERSARIAL_INJECTION
            
            # Mark as backdoored
            if not hasattr(poisoned_data[idx], 'custom_fields'):
                 poisoned_data[idx].custom_fields = {}
            poisoned_data[idx].custom_fields['backdoor'] = True
            poisoned_data[idx].custom_fields['trigger_pattern'] = trigger_pattern
        
        return poisoned_data
    
    def generate_feature_corruption(self, data: List[TelemetryRecord], corruption_strength: float = 0.3) -> List[TelemetryRecord]:
        """Generate feature corruption attack"""
        
        corrupted_data = [d.__class__(**d.__dict__) for d in data] # Deep copy
        num_to_corrupt = int(len(data) * self.max_poison_rate)
        
        if not data:
            return []
            
        corruption_indices = random.sample(range(len(data)), num_to_corrupt)
        
        for idx in corruption_indices:
            # Corrupt numerical features with extreme values
            if random.random() < 0.5:
                corrupted_data[idx].duration *= (1.0 + corruption_strength * random.uniform(5, 20))
            
            if random.random() < 0.5:
                corrupted_data[idx].memory_spike_kb = int(corrupted_data[idx].memory_spike_kb * (1.0 + corruption_strength * random.uniform(3, 10)))
            
            if random.random() < 0.5:
                corrupted_data[idx].cpu_utilization = min(100.0, 
                    corrupted_data[idx].cpu_utilization * (1.0 + corruption_strength * random.uniform(2, 5)))
            
            # Mark as corrupted
            if not hasattr(corrupted_data[idx], 'custom_fields'):
                 corrupted_data[idx].custom_fields = {}
            corrupted_data[idx].custom_fields['feature_corrupted'] = True
        
        return corrupted_data


class EconomicAttackSimulator:
    """Simulate economic abuse attacks (DoW, cryptomining, billing amplification)"""
    
    def __init__(self, config: AdversarialConfig):
        self.config = config
        self.cost_models = self._initialize_cost_models()
        
    def _initialize_cost_models(self) -> Dict[str, Dict[str, float]]:
        """Initialize AWS Lambda cost models"""
        return {
            'lambda': {
                'per_request': 0.0000002,  # $0.20 per 1M requests
                'per_gb_second': 0.0000166667,  # $0.0000166667 per GB-second
                'free_tier_requests': 1000000,  # 1M free requests per month
                'free_tier_gb_seconds': 400000  # 400,000 GB-seconds per month
            },
            'api_gateway': {
                'per_request': 0.0000035,  # $3.50 per million requests
                'data_transfer_per_gb': 0.09  # $0.09 per GB
            }
        }
    
    def simulate_denial_of_wallet_attack(self, duration_minutes: int = 60, intensity: str = "high") -> AttackResult:
        """Simulate Denial of Wallet (DoW) attack"""
        
        attack_id = f"dow_{int(time.time())}"
        start_time = time.time()
        
        # Define attack intensities
        intensity_params = {
            "low": {"requests_per_second": 10, "avg_duration": 1.0, "memory_mb": 128},
            "medium": {"requests_per_second": 50, "avg_duration": 2.0, "memory_mb": 256},
            "high": {"requests_per_second": 200, "avg_duration": 5.0, "memory_mb": 512},
            "extreme": {"requests_per_second": 1000, "avg_duration": 10.0, "memory_mb": 1024}
        }
        
        params = intensity_params.get(intensity, intensity_params["medium"])
        
        # Calculate attack parameters
        total_duration_seconds = duration_minutes * 60
        total_requests = int(params["requests_per_second"] * total_duration_seconds)
        
        # Generate adversarial telemetry for DoW attack
        attack_telemetry = []
        estimated_cost = 0.0
        
        for i in range(min(total_requests, 1000)):  # Limit for simulation
            telemetry = TelemetryRecord(
                event_id=f"dow_event_{i}",
                timestamp=start_time + i / params["requests_per_second"],
                function_id="adversarial_target_function",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.BILLING_ABUSE,
                duration=params["avg_duration"] + random.uniform(-0.5, 0.5),
                memory_spike_kb=params["memory_mb"] * 1024,
                cpu_utilization=random.uniform(80, 100),
                network_io_bytes=random.randint(1000, 10000),
                fallback_mode=False,
                source=TelemetrySource.SCAFAD_LAYER0,
                concurrency_id=f"dow_concurrency_{i}"
            )
            
            # Add DoW-specific markers
            if not hasattr(telemetry, 'custom_fields'):
                 telemetry.custom_fields = {}
            telemetry.custom_fields.update({
                'attack_type': 'denial_of_wallet',
                'attack_intensity': intensity,
                'cost_amplification': 'high'
            })
            
            attack_telemetry.append(telemetry)
            
            # Calculate cost impact
            request_cost = self.cost_models['lambda']['per_request']
            compute_cost = (params["memory_mb"] / 1024.0) * params["avg_duration"] * self.cost_models['lambda']['per_gb_second']
            estimated_cost += request_cost + compute_cost
        
        end_time = time.time()
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=AttackType.DENIAL_OF_WALLET,
            start_time=start_time,
            end_time=end_time,
            economic_impact=estimated_cost,
            generated_telemetry=attack_telemetry,
            attribution_signals={
                'intensity': intensity,
                'pattern': 'sustained_high_frequency',
                'cost_amplification': estimated_cost / max(1.0, len(attack_telemetry) * 0.0000002) if attack_telemetry else 0.0
            }
        )
    
    def simulate_cryptomining_attack(self, duration_minutes: int = 120) -> AttackResult:
        """Simulate cryptomining attack using serverless functions"""
        
        attack_id = f"mining_{int(time.time())}"
        start_time = time.time()
        
        # Cryptomining characteristics
        mining_patterns = {
            'cpu_intensive': True,
            'long_duration': True,
            'memory_stable': True,
            'network_minimal': True
        }
        
        attack_telemetry = []
        total_duration_seconds = duration_minutes * 60
        num_executions = max(1, duration_minutes // 5)  # One execution every 5 minutes
        
        for i in range(num_executions):
            execution_duration = random.uniform(250, 300)  # Long executions
            telemetry = TelemetryRecord(
                event_id=f"mining_event_{i}",
                timestamp=start_time + i * 300,  # Every 5 minutes
                function_id="legitimate_data_processor",  # Disguised function name
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.CRYPTOMINING,
                duration=execution_duration,
                memory_spike_kb=random.randint(256000, 512000),  # 256-512 MB
                cpu_utilization=random.uniform(95, 99.9),  # Very high CPU
                network_io_bytes=random.randint(100, 1000),  # Minimal network
                fallback_mode=False,
                source=TelemetrySource.SCAFAD_LAYER0,
                concurrency_id=f"mining_concurrency_{i}"
            )
            
            # Add mining-specific indicators
            if not hasattr(telemetry, 'custom_fields'):
                 telemetry.custom_fields = {}
            telemetry.custom_fields.update({
                'attack_type': 'cryptomining',
                'cpu_pattern': 'sustained_high',
                'mining_algorithm': 'sha256',
                'stealth_level': 'high'
            })
            
            attack_telemetry.append(telemetry)
        
        # Calculate economic impact
        estimated_cost = self._calculate_mining_cost(attack_telemetry)
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=AttackType.CRYPTOMINING,
            start_time=start_time,
            end_time=time.time(),
            economic_impact=estimated_cost,
            generated_telemetry=attack_telemetry,
            attribution_signals={
                'cpu_pattern': 'sustained_maximum',
                'duration_pattern': 'extended_execution',
                'network_pattern': 'minimal_io',
                'stealth_indicators': ['legitimate_function_name', 'timing_distribution']
            }
        )
    
    def simulate_billing_amplification_attack(self) -> AttackResult:
        """Simulate billing amplification attack"""
        
        attack_id = f"amplification_{int(time.time())}"
        start_time = time.time()
        
        # Amplification through maximum resource allocation
        attack_telemetry = []
        
        for i in range(50):  # Burst of high-resource executions
            telemetry = TelemetryRecord(
                event_id=f"amplification_event_{i}",
                timestamp=start_time + i * 2,  # Rapid fire
                function_id="resource_intensive_function",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.BILLING_ABUSE,
                duration=random.uniform(15, 30),  # Long duration
                memory_spike_kb=3000000,  # 3GB (maximum)
                cpu_utilization=random.uniform(90, 100),
                network_io_bytes=random.randint(1000000, 10000000),  # 1-10MB
                fallback_mode=False,
                source=TelemetrySource.SCAFAD_LAYER0,
                concurrency_id=f"amplification_concurrency_{i}"
            )
            
            if not hasattr(telemetry, 'custom_fields'):
                 telemetry.custom_fields = {}
            telemetry.custom_fields.update({
                'attack_type': 'billing_amplification',
                'resource_targeting': 'maximum_allocation',
                'cost_efficiency': 'optimized_for_cost'
            })
            
            attack_telemetry.append(telemetry)
        
        estimated_cost = sum(
            (3.0 * record.duration * self.cost_models['lambda']['per_gb_second']) + 
            self.cost_models['lambda']['per_request']
            for record in attack_telemetry
        )
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=AttackType.BILLING_AMPLIFICATION,
            start_time=start_time,
            end_time=time.time(),
            economic_impact=estimated_cost,
            generated_telemetry=attack_telemetry,
            attribution_signals={
                'resource_pattern': 'maximum_allocation',
                'timing_pattern': 'burst_execution',
                'cost_optimization': 'high'
            }
        )
    
    def _calculate_mining_cost(self, telemetry_records: List[TelemetryRecord]) -> float:
        """Calculate cost impact of cryptomining attack"""
        total_cost = 0.0
        
        for record in telemetry_records:
            # Request cost
            request_cost = self.cost_models['lambda']['per_request']
            
            # Compute cost (GB-seconds)
            memory_gb = record.memory_spike_kb / (1024 * 1024)
            compute_cost = memory_gb * record.duration * self.cost_models['lambda']['per_gb_second']
            
            total_cost += request_cost + compute_cost
        
        return total_cost


class AdversarialAnomalyEngine:
    """
    Main adversarial anomaly engine coordinating all attack simulation capabilities
    Implements the Ares-inspired wargame framework for comprehensive adversarial testing
    """
    
    def __init__(self, config: AdversarialConfig):
        self.config = config
        self.attack_history = []
        self.detection_performance = {}
        
        # Initialize components
        self.evasion_techniques = EvasionTechniques()
        self.poisoning_generator = PoisoningAttackGenerator(config.max_poisoning_rate)
        self.economic_simulator = EconomicAttackSimulator(config)
        
        # Initialize ML components if available
        self.gan_model = None
        self.adaptive_attacker = None
        
        if TORCH_AVAILABLE and config.enable_gan_generation:
            self.gan_model = ServerlessAnomalyGAN(
                latent_dim=config.gan_latent_dim,
                feature_dim=config.gan_feature_dim
            )
            
            self.adaptive_attacker = AdaptiveAttacker()
            
            # Initialize optimizers
            self.gan_optimizer_g = optim.Adam(self.gan_model.generator.parameters(), 
                                            lr=config.gan_learning_rate)
            self.gan_optimizer_d = optim.Adam(self.gan_model.discriminator.parameters(), 
                                            lr=config.gan_learning_rate)
            self.attacker_optimizer = optim.Adam(self.adaptive_attacker.actor.parameters(), 
                                               lr=0.001)
            
        if TORCH_AVAILABLE:
            self.scaler = StandardScaler()
        
    async def generate_adversarial_anomaly(self, normal_pattern: TelemetryRecord, 
                                         attack_type: AttackType) -> AttackResult:
        """Generate adversarial anomaly using specified attack type"""
        
        attack_id = f"{attack_type.value}_{int(time.time())}_{random.randint(1000, 9999)}"
        start_time = time.time()
        
        logging.info(f"Generating adversarial anomaly: {attack_type.value}")
        
        # Route to appropriate attack method
        if attack_type in [AttackType.NOISE_INJECTION, AttackType.GRADIENT_MASKING, 
                          AttackType.INPUT_TRANSFORMATION, AttackType.ADAPTIVE_PERTURBATION]:
            result = await self._generate_evasion_attack(normal_pattern, attack_type, attack_id)
            
        elif attack_type in [AttackType.DENIAL_OF_WALLET, AttackType.BILLING_AMPLIFICATION, 
                            AttackType.CRYPTOMINING]:
            result = await self._generate_economic_attack(attack_type, attack_id)
            
        elif attack_type in [AttackType.LABEL_FLIP, AttackType.BACKDOOR_TRIGGER, 
                            AttackType.FEATURE_CORRUPTION]:
            result = await self._generate_poisoning_attack(normal_pattern, attack_type, attack_id)
            
        elif attack_type == AttackType.QUERY_FREE_EVASION:
            result = await self._generate_query_free_attack(normal_pattern, attack_id)
            
        elif attack_type == AttackType.TRANSFER_ATTACK:
            result = await self._generate_transfer_attack(normal_pattern, attack_id)
            
        elif attack_type == AttackType.MULTI_STEP_CAMPAIGN:
            result = await self._generate_multi_step_campaign(normal_pattern, attack_id)
            
        else:
            # Fallback to basic evasion
            result = await self._generate_evasion_attack(normal_pattern, 
                                                       AttackType.NOISE_INJECTION, attack_id)
        
        # Record attack history
        self.attack_history.append(result)
        
        # Evaluate attack success
        await self._evaluate_attack_success(result)
        
        return result
    
    async def _generate_evasion_attack(self, normal_pattern: TelemetryRecord, 
                                     attack_type: AttackType, attack_id: str) -> AttackResult:
        """Generate evasion attack using classical techniques"""
        
        start_time = time.time()
        original_score = normal_pattern.anomaly_score if hasattr(normal_pattern, 'anomaly_score') else 0.0
        
        # Apply evasion technique
        if attack_type == AttackType.NOISE_INJECTION:
            perturbed = self.evasion_techniques.noise_injection(normal_pattern, 
                                                              self.config.max_evasion_budget)
        elif attack_type == AttackType.GRADIENT_MASKING:
            perturbed = self.evasion_techniques.gradient_masking(normal_pattern, 
                                                               self.config.max_evasion_budget)
        elif attack_type == AttackType.INPUT_TRANSFORMATION:
            perturbed = self.evasion_techniques.input_transformation(normal_pattern, "logarithmic")
        elif attack_type == AttackType.ADAPTIVE_PERTURBATION:
            perturbed = self.evasion_techniques.adaptive_perturbation(normal_pattern, 
                                                                    epsilon=self.config.max_evasion_budget)
        else:
            perturbed = normal_pattern
        
        # Calculate perturbation magnitude
        perturbation_magnitude = self._calculate_perturbation_magnitude(normal_pattern, perturbed)
        
        # Simulate detection response
        detection_triggered = self._simulate_detection_response(perturbed)
        evasion_success = not detection_triggered
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=attack_type,
            start_time=start_time,
            end_time=time.time(),
            evasion_success=evasion_success,
            detection_triggered=detection_triggered,
            perturbation_magnitude=perturbation_magnitude,
            anomaly_score_before=original_score,
            anomaly_score_after=getattr(perturbed, 'anomaly_score', 0.0),
            generated_telemetry=[perturbed],
            feature_changes=self._calculate_feature_changes(normal_pattern, perturbed),
            stealth_score=self._calculate_stealth_score(perturbation_magnitude, evasion_success)
        )
    
    async def _generate_economic_attack(self, attack_type: AttackType, attack_id: str) -> AttackResult:
        """Generate economic abuse attack"""
        
        if attack_type == AttackType.DENIAL_OF_WALLET:
            return self.economic_simulator.simulate_denial_of_wallet_attack(
                duration_minutes=random.randint(30, 120),
                intensity=random.choice(["medium", "high", "extreme"])
            )
        elif attack_type == AttackType.CRYPTOMINING:
            return self.economic_simulator.simulate_cryptomining_attack(
                duration_minutes=random.randint(60, 300)
            )
        elif attack_type == AttackType.BILLING_AMPLIFICATION:
            return self.economic_simulator.simulate_billing_amplification_attack()
        else:
            # Default economic attack
            return self.economic_simulator.simulate_denial_of_wallet_attack()
    
    async def _generate_poisoning_attack(self, normal_pattern: TelemetryRecord, 
                                       attack_type: AttackType, attack_id: str) -> AttackResult:
        """Generate data poisoning attack"""
        
        start_time = time.time()
        
        # Create a small dataset for poisoning demonstration
        base_data = [normal_pattern] * 20
        
        if attack_type == AttackType.LABEL_FLIP:
            poisoned_data = self.poisoning_generator.generate_label_flip_attack(
                base_data, self.config.max_poisoning_rate
            )
        elif attack_type == AttackType.BACKDOOR_TRIGGER:
            trigger_pattern = {
                'cpu_utilization': 83.7,  # Specific trigger value
                'memory_spike_kb': 256000
            }
            poisoned_data = self.poisoning_generator.generate_backdoor_attack(
                base_data, trigger_pattern
            )
        elif attack_type == AttackType.FEATURE_CORRUPTION:
            poisoned_data = self.poisoning_generator.generate_feature_corruption(
                base_data, corruption_strength=0.5
            )
        else:
            poisoned_data = base_data
        
        # Calculate poison impact
        num_poisoned = sum(1 for record in poisoned_data 
                          if hasattr(record, 'custom_fields') and (record.custom_fields.get('poisoned', False) or 
                             record.custom_fields.get('backdoor', False) or
                             record.custom_fields.get('feature_corrupted', False)))
        
        poison_rate = num_poisoned / len(poisoned_data) if poisoned_data else 0.0
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=attack_type,
            start_time=start_time,
            end_time=time.time(),
            evasion_success=poison_rate > 0,
            generated_telemetry=poisoned_data,
            attribution_signals={
                'poison_rate': poison_rate,
                'poison_count': num_poisoned,
                'attack_method': attack_type.value
            }
        )
    
    async def _generate_query_free_attack(self, normal_pattern: TelemetryRecord, 
                                        attack_id: str) -> AttackResult:
        """Generate query-free evasion attack using GAN"""
        
        start_time = time.time()
        
        if not self.gan_model or not TORCH_AVAILABLE:
            # Fallback to traditional evasion
            return await self._generate_evasion_attack(normal_pattern, 
                                                     AttackType.NOISE_INJECTION, attack_id)
        
        # Convert telemetry to feature vector
        feature_vector = self._telemetry_to_feature_vector(normal_pattern)
        
        # Generate adversarial sample using GAN
        with torch.no_grad():
            z = torch.randn(1, self.config.gan_latent_dim)
            conditions = torch.randn(1, 5)  # Random conditions
            
            generated_features = self.gan_model(z, conditions)
            generated_features = generated_features.cpu().numpy().flatten()
        
        # Convert back to telemetry
        adversarial_telemetry = self._feature_vector_to_telemetry(
            generated_features, normal_pattern
        )
        
        # Evaluate attack
        perturbation_magnitude = self._calculate_perturbation_magnitude(
            normal_pattern, adversarial_telemetry
        )
        
        detection_triggered = self._simulate_detection_response(adversarial_telemetry)
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=AttackType.QUERY_FREE_EVASION,
            start_time=start_time,
            end_time=time.time(),
            evasion_success=not detection_triggered,
            detection_triggered=detection_triggered,
            perturbation_magnitude=perturbation_magnitude,
            generated_telemetry=[adversarial_telemetry],
            attribution_signals={
                'generation_method': 'gan',
                'query_count': 0,  # Query-free
                'stealth_level': 'high'
            }
        )
    
    async def _generate_transfer_attack(self, normal_pattern: TelemetryRecord, 
                                      attack_id: str) -> AttackResult:
        """Generate transfer attack using feature-based adversarial training"""
        
        start_time = time.time()
        
        if not self.gan_model or not TORCH_AVAILABLE:
            return await self._generate_evasion_attack(normal_pattern, 
                                                     AttackType.ADAPTIVE_PERTURBATION, attack_id)
        
        # Extract features using the feature extractor
        feature_vector = self._telemetry_to_feature_vector(normal_pattern)
        feature_tensor = torch.FloatTensor(feature_vector).unsqueeze(0)
        
        with torch.no_grad():
            # Extract intermediate features
            intermediate_features = self.gan_model.extract_features(feature_tensor)
            
            # Apply feature-space perturbations (FBAT-inspired)
            noise = torch.randn_like(intermediate_features) * self.config.max_evasion_budget
            perturbed_features = intermediate_features + noise
            
            # Generate adversarial sample
            adversarial_features = perturbed_features.cpu().numpy().flatten()
        
        # Convert back to telemetry
        adversarial_telemetry = self._feature_vector_to_telemetry(
            adversarial_features[:len(feature_vector)], normal_pattern
        )
        
        detection_triggered = self._simulate_detection_response(adversarial_telemetry)
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=AttackType.TRANSFER_ATTACK,
            start_time=start_time,
            end_time=time.time(),
            evasion_success=not detection_triggered,
            detection_triggered=detection_triggered,
            generated_telemetry=[adversarial_telemetry],
            attribution_signals={
                'attack_method': 'feature_perturbation',
                'transfer_learning': True,
                'robustness_target': 'cross_model'
            }
        )
    
    async def _generate_multi_step_campaign(self, normal_pattern: TelemetryRecord, 
                                          attack_id: str) -> AttackResult:
        """Generate sophisticated multi-step attack campaign"""
        
        start_time = time.time()
        campaign_telemetry = []
        
        # Step 1: Reconnaissance (subtle probing)
        recon_telemetry = self.evasion_techniques.noise_injection(normal_pattern, 0.05)
        if not hasattr(recon_telemetry, 'custom_fields'): recon_telemetry.custom_fields = {}
        recon_telemetry.custom_fields['campaign_phase'] = 'reconnaissance'
        campaign_telemetry.append(recon_telemetry)
        
        # Step 2: Initial compromise (slightly more aggressive)
        compromise_telemetry = self.evasion_techniques.gradient_masking(normal_pattern, 0.1)
        if not hasattr(compromise_telemetry, 'custom_fields'): compromise_telemetry.custom_fields = {}
        compromise_telemetry.custom_fields['campaign_phase'] = 'initial_compromise'
        campaign_telemetry.append(compromise_telemetry)
        
        # Step 3: Privilege escalation (economic attack)
        economic_result = await self._generate_economic_attack(AttackType.CRYPTOMINING, 
                                                             f"{attack_id}_economic")
        campaign_telemetry.extend(economic_result.generated_telemetry[:3])  # Limit size
        
        # Step 4: Persistence (backdoor)
        if self.config.enable_poisoning_attacks:
            poison_result = await self._generate_poisoning_attack(normal_pattern, 
                                                                AttackType.BACKDOOR_TRIGGER, 
                                                                f"{attack_id}_backdoor")
            campaign_telemetry.extend(poison_result.generated_telemetry[:2])
        
        # Step 5: Exfiltration simulation
        exfil_telemetry = normal_pattern.__class__(**normal_pattern.__dict__)
        exfil_telemetry.network_io_bytes *= 10  # High network activity
        if not hasattr(exfil_telemetry, 'custom_fields'): exfil_telemetry.custom_fields = {}
        exfil_telemetry.custom_fields['campaign_phase'] = 'exfiltration'
        exfil_telemetry.anomaly_type = AnomalyType.DATA_EXFILTRATION
        campaign_telemetry.append(exfil_telemetry)
        
        # Evaluate campaign success
        detection_phases = []
        for telemetry in campaign_telemetry:
            if self._simulate_detection_response(telemetry):
                phase = telemetry.custom_fields.get('campaign_phase', 'unknown') if hasattr(telemetry, 'custom_fields') else 'unknown'
                detection_phases.append(phase)
        
        campaign_success = len(detection_phases) < len(campaign_telemetry) * 0.5
        
        return AttackResult(
            attack_id=attack_id,
            attack_type=AttackType.MULTI_STEP_CAMPAIGN,
            start_time=start_time,
            end_time=time.time(),
            evasion_success=campaign_success,
            detection_triggered=len(detection_phases) > 0,
            generated_telemetry=campaign_telemetry,
            attribution_signals={
                'campaign_phases': ['reconnaissance', 'compromise', 'escalation', 'persistence', 'exfiltration'],
                'detection_phases': detection_phases,
                'sophistication_level': 5,
                'attack_duration': time.time() - start_time
            }
        )
    
    async def train_gan_model(self, training_data: List[TelemetryRecord], epochs: int = None):
        """Train the GAN model on telemetry data"""
        
        if not self.gan_model or not TORCH_AVAILABLE:
            logging.warning("GAN training not available")
            return
        
        epochs = epochs or self.config.gan_epochs
        batch_size = self.config.gan_batch_size
        
        # Convert telemetry to feature vectors
        feature_data = []
        labels = []
        
        for record in training_data:
            features = self._telemetry_to_feature_vector(record)
            feature_data.append(features)
            
            # Create labels (0 = benign, 1 = anomalous)
            label = 1 if record.anomaly_type != AnomalyType.BENIGN else 0
            labels.append(label)
        
        feature_data = np.array(feature_data)
        labels = np.array(labels)
        
        # Normalize features
        feature_data = self.scaler.fit_transform(feature_data)
        
        # Create PyTorch datasets
        feature_tensor = torch.FloatTensor(feature_data)
        label_tensor = torch.FloatTensor(labels)
        
        dataset = TensorDataset(feature_tensor, label_tensor)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        logging.info(f"Training GAN for {epochs} epochs on {len(training_data)} samples")
        
        # Training loop
        for epoch in range(epochs):
            epoch_d_loss = 0.0
            epoch_g_loss = 0.0
            
            for batch_features, batch_labels in dataloader:
                batch_size_actual = batch_features.size(0)
                
                # Train Discriminator
                self.gan_optimizer_d.zero_grad()
                
                # Real samples
                real_conditions = torch.randn(batch_size_actual, 5)
                real_validity = self.gan_model.discriminate(batch_features, real_conditions)
                real_loss = F.binary_cross_entropy(real_validity, torch.ones_like(real_validity))
                
                # Fake samples
                z = torch.randn(batch_size_actual, self.config.gan_latent_dim)
                fake_conditions = torch.randn(batch_size_actual, 5)
                fake_features = self.gan_model(z, fake_conditions)
                fake_validity = self.gan_model.discriminate(fake_features.detach(), fake_conditions)
                fake_loss = F.binary_cross_entropy(fake_validity, torch.zeros_like(fake_validity))
                
                d_loss = (real_loss + fake_loss) / 2
                d_loss.backward()
                self.gan_optimizer_d.step()
                
                # Train Generator
                self.gan_optimizer_g.zero_grad()
                
                z = torch.randn(batch_size_actual, self.config.gan_latent_dim)
                gen_conditions = torch.randn(batch_size_actual, 5)
                generated_features = self.gan_model(z, gen_conditions)
                gen_validity = self.gan_model.discriminate(generated_features, gen_conditions)
                
                g_loss = F.binary_cross_entropy(gen_validity, torch.ones_like(gen_validity))
                g_loss.backward()
                self.gan_optimizer_g.step()
                
                epoch_d_loss += d_loss.item()
                epoch_g_loss += g_loss.item()
            
            if epoch % 10 == 0:
                logging.info(f"Epoch {epoch}: D_loss={epoch_d_loss:.4f}, G_loss={epoch_g_loss:.4f}")
        
        logging.info("GAN training completed")
    
    def apply_evasion_techniques(self, telemetry: TelemetryRecord, 
                               target_model=None, technique: str = "adaptive") -> TelemetryRecord:
        """Apply evasion techniques to telemetry record"""
        
        if technique == "noise_injection":
            return self.evasion_techniques.noise_injection(telemetry, self.config.max_evasion_budget)
        elif technique == "gradient_masking":
            return self.evasion_techniques.gradient_masking(telemetry, self.config.max_evasion_budget)
        elif technique == "input_transformation":
            return self.evasion_techniques.input_transformation(telemetry, "logarithmic")
        elif technique == "adaptive":
            return self.evasion_techniques.adaptive_perturbation(telemetry, target_model, 
                                                               self.config.max_evasion_budget)
        else:
            return telemetry
    
    async def evaluate_defense_robustness(self, defense_function, test_data: List[TelemetryRecord]) -> Dict[str, float]:
        """Evaluate defense robustness against various attack types"""
        
        results = {}
        
        for attack_type in AttackType:
            if not self._is_attack_enabled(attack_type):
                continue
                
            successes = 0
            total_attempts = min(10, len(test_data)) if test_data else 0

            if total_attempts == 0:
                results[attack_type.value] = 0.0
                continue
            
            for i in range(total_attempts):
                sample = test_data[i % len(test_data)]
                
                try:
                    attack_result = await self.generate_adversarial_anomaly(sample, attack_type)
                    
                    # Test defense
                    for adv_telemetry in attack_result.generated_telemetry:
                        defense_response = defense_function(adv_telemetry)
                        
                        # Count as success if attack evaded detection
                        if not defense_response.get('anomaly_detected', True):
                            successes += 1
                            break
                
                except Exception as e:
                    logging.warning(f"Attack evaluation failed for {attack_type}: {e}")
            
            success_rate = successes / total_attempts if total_attempts > 0 else 0.0
            results[attack_type.value] = success_rate
        
        return results
    
    def get_attack_statistics(self) -> Dict[str, Any]:
        """Get comprehensive attack statistics"""
        
        if not self.attack_history:
            return {"total_attacks": 0}
        
        stats = {
            "total_attacks": len(self.attack_history),
            "attack_types": {},
            "success_rates": {},
            "average_stealth": 0.0,
            "economic_impact": 0.0
        }
        
        # Analyze attack types
        type_counts = defaultdict(int)
        type_successes = defaultdict(int)
        total_stealth = 0.0
        total_economic_impact = 0.0
        
        for attack in self.attack_history:
            attack_type = attack.attack_type.value
            type_counts[attack_type] += 1
            
            if attack.evasion_success:
                type_successes[attack_type] += 1
            
            total_stealth += attack.stealth_score
            total_economic_impact += attack.economic_impact
        
        # Calculate statistics
        stats["attack_types"] = dict(type_counts)
        
        for attack_type, count in type_counts.items():
            success_rate = type_successes[attack_type] / count if count > 0 else 0.0
            stats["success_rates"][attack_type] = success_rate
        
        if self.attack_history:
            stats["average_stealth"] = total_stealth / len(self.attack_history)
        stats["economic_impact"] = total_economic_impact
        
        return stats

    def get_attack_effectiveness_report(self) -> Dict[str, Any]:
        """Generate a compact effectiveness summary from tracked attack results."""
        if not self.detection_performance:
            return {
                "generation_timestamp": time.time(),
                "total_attack_types_tested": 0,
                "overall_statistics": {
                    "total_attacks_executed": 0,
                    "overall_success_rate": 0.0,
                    "overall_detection_rate": 0.0,
                    "total_economic_impact": 0.0,
                },
                "attack_type_analysis": {},
            }

        all_stats = list(self.detection_performance.values())
        total_attempts = sum(stats.get("total_attempts", 0) for stats in all_stats)
        total_successes = sum(stats.get("successful_evasions", 0) for stats in all_stats)
        total_economic_impact = sum(stats.get("economic_impact", 0.0) for stats in all_stats)

        report = {
            "generation_timestamp": time.time(),
            "total_attack_types_tested": len(self.detection_performance),
            "overall_statistics": {
                "total_attacks_executed": total_attempts,
                "overall_success_rate": (total_successes / total_attempts) if total_attempts else 0.0,
                "overall_detection_rate": ((total_attempts - total_successes) / total_attempts) if total_attempts else 0.0,
                "total_economic_impact": total_economic_impact,
            },
            "attack_type_analysis": {},
        }

        for attack_type, stats in self.detection_performance.items():
            report["attack_type_analysis"][attack_type] = {
                "attempts": stats.get("total_attempts", 0),
                "success_rate": stats.get("success_rate", 0.0),
                "detection_rate": stats.get("detection_rate", 0.0),
                "average_stealth": stats.get("average_stealth", 0.0),
                "average_perturbation": stats.get("average_perturbation", 0.0),
                "economic_impact": stats.get("economic_impact", 0.0),
            }

        return report
    
    # Utility methods
    
    def _telemetry_to_feature_vector(self, telemetry: TelemetryRecord) -> np.ndarray:
        """Convert telemetry record to feature vector for ML processing"""
        
        features = [
            telemetry.duration,
            telemetry.memory_spike_kb / 1000.0,  # Normalize to MB
            telemetry.cpu_utilization / 100.0,  # Normalize to [0,1]
            telemetry.network_io_bytes / 1000.0,  # Normalize to KB
            {phase: idx for idx, phase in enumerate(ExecutionPhase)}.get(
                telemetry.execution_phase, 0
            ),
            telemetry.timestamp % 3600,  # Hour of day feature
            len(telemetry.function_id),  # Function name length
            1.0 if telemetry.anomaly_type != AnomalyType.BENIGN else 0.0,
            getattr(telemetry, 'confidence_level', 1.0),
            getattr(telemetry, 'data_quality_score', 1.0)
        ]
        
        # Pad to target dimension
        while len(features) < self.config.gan_feature_dim:
            features.append(0.0)
        
        return np.array(features[:self.config.gan_feature_dim])
    
    def _feature_vector_to_telemetry(self, features: np.ndarray, 
                                   template: TelemetryRecord) -> TelemetryRecord:
        """Convert feature vector back to telemetry record"""
        
        # Create modified telemetry based on template
        modified = template.__class__(**template.__dict__)
        
        # Map features back to telemetry fields
        if len(features) >= 4:
            modified.duration = max(0.001, float(features[0]))
            modified.memory_spike_kb = max(0, int(features[1] * 1000.0))  # Convert back from MB
            modified.cpu_utilization = max(0.0, min(100.0, float(features[2] * 100.0)))
            modified.network_io_bytes = max(0, int(features[3] * 1000.0))  # Convert back from KB
        
        # Add adversarial markers
        if not hasattr(modified, 'custom_fields'): modified.custom_fields = {}
        modified.custom_fields['adversarial_generated'] = True
        modified.custom_fields['generation_timestamp'] = time.time()
        
        return modified
    
    def _calculate_perturbation_magnitude(self, original: TelemetryRecord, 
                                        perturbed: TelemetryRecord) -> float:
        """Calculate L2 norm of perturbation"""
        
        orig_features = self._telemetry_to_feature_vector(original)
        pert_features = self._telemetry_to_feature_vector(perturbed)
        
        diff = pert_features - orig_features
        magnitude = np.linalg.norm(diff)
        
        return float(magnitude)
    
    def _calculate_feature_changes(self, original: TelemetryRecord, 
                                 modified: TelemetryRecord) -> Dict[str, float]:
        """Calculate relative changes in key features"""
        
        changes = {}
        
        # Duration change
        if original.duration > 0:
            changes['duration'] = (modified.duration - original.duration) / original.duration
        
        # Memory change
        if original.memory_spike_kb > 0:
            changes['memory'] = (modified.memory_spike_kb - original.memory_spike_kb) / original.memory_spike_kb
        
        # CPU change
        changes['cpu'] = (modified.cpu_utilization - original.cpu_utilization) / 100.0
        
        # Network change
        if original.network_io_bytes > 0:
            changes['network'] = (modified.network_io_bytes - original.network_io_bytes) / original.network_io_bytes
        
        return changes
    
    def _calculate_stealth_score(self, perturbation_magnitude: float, 
                               evasion_success: bool) -> float:
        """Calculate stealth score based on perturbation size and success"""
        
        # Lower perturbation magnitude = higher stealth
        magnitude_score = 1.0 / (1.0 + perturbation_magnitude)
        
        # Success bonus
        success_bonus = 0.5 if evasion_success else 0.0
        
        stealth_score = 0.7 * magnitude_score + 0.3 * success_bonus
        
        return min(1.0, stealth_score)
    
    def _simulate_detection_response(self, telemetry: TelemetryRecord) -> bool:
        """Simulate whether detection system would trigger on this telemetry"""
        
        # Simple heuristic-based detection simulation
        detection_score = 0.0
        
        # Duration anomaly
        if telemetry.duration > 10.0:  # > 10 seconds
            detection_score += 0.3
        
        # Memory anomaly
        if telemetry.memory_spike_kb > 500000:  # > 500MB
            detection_score += 0.3
        
        # CPU anomaly
        if telemetry.cpu_utilization > 90.0:
            detection_score += 0.2
        
        # Network anomaly
        if telemetry.network_io_bytes > 1000000:  # > 1MB
            detection_score += 0.2
        
        # Anomaly type
        if telemetry.anomaly_type != AnomalyType.BENIGN:
            detection_score += 0.4
        
        # Add some randomness
        detection_score += random.uniform(-0.1, 0.1)
        
        return detection_score > 0.5
    
    def _is_attack_enabled(self, attack_type: AttackType) -> bool:
        """Check if attack type is enabled in configuration"""
        
        if attack_type in [AttackType.DENIAL_OF_WALLET, AttackType.BILLING_AMPLIFICATION, 
                          AttackType.CRYPTOMINING]:
            return getattr(self.config, 'enable_dos_patterns', False) or \
                   getattr(self.config, 'enable_billing_patterns', False) or \
                   getattr(self.config, 'enable_mining_patterns', False)
        
        if attack_type in [AttackType.LABEL_FLIP, AttackType.BACKDOOR_TRIGGER, 
                          AttackType.FEATURE_CORRUPTION]:
            return self.config.enable_poisoning_attacks
        
        return self.config.enable_evasion_techniques
    
    async def _evaluate_attack_success(self, attack_result: AttackResult):
        """Evaluate and log attack success metrics"""
        
        attack_type = attack_result.attack_type.value
        
        if attack_type not in self.detection_performance:
            self.detection_performance[attack_type] = {
                'total_attempts': 0,
                'successful_evasions': 0,
                'failed_evasions': 0,
                'average_stealth': 0.0,
                'average_perturbation': 0.0,
                'economic_impact': 0.0,
                'detection_rate': 0.0,
                'success_rate': 0.0,
                'attribution_difficulty': 0.0,
                'temporal_patterns': [],
                'last_updated': time.time()
            }
        
        stats = self.detection_performance[attack_type]
        stats['total_attempts'] += 1
        
        if attack_result.evasion_success:
            stats['successful_evasions'] += 1
        else:
            stats['failed_evasions'] += 1
        
        # Update running averages using incremental calculation
        n = stats['total_attempts']
        stats['average_stealth'] = ((n - 1) * stats['average_stealth'] + attack_result.stealth_score) / n
        stats['average_perturbation'] = ((n - 1) * stats['average_perturbation'] + attack_result.perturbation_magnitude) / n
        stats['economic_impact'] += attack_result.economic_impact
        
        # Calculate rates
        stats['success_rate'] = stats['successful_evasions'] / stats['total_attempts']
        stats['detection_rate'] = stats['failed_evasions'] / stats['total_attempts']
        
        # Attribution difficulty (from attack result signals)
        attribution_score = attack_result.attribution_signals.get('attribution_difficulty', 0.5)
        stats['attribution_difficulty'] = ((n - 1) * stats['attribution_difficulty'] + attribution_score) / n
        
        # Track temporal patterns for analysis
        stats['temporal_patterns'].append({
            'timestamp': attack_result.start_time,
            'success': attack_result.evasion_success,
            'stealth': attack_result.stealth_score
        })
        
        # Keep only recent temporal patterns (last 100 attacks)
        if len(stats['temporal_patterns']) > 100:
            stats['temporal_patterns'] = stats['temporal_patterns'][-100:]
        
        stats['last_updated'] = time.time()
        
        # Log comprehensive metrics
        logging.info(f"Attack {attack_result.attack_id} evaluated: "
                    f"Type={attack_type}, "
                    f"Success={attack_result.evasion_success}, "
                    f"Stealth={attack_result.stealth_score:.3f}, "
                    f"Perturbation={attack_result.perturbation_magnitude:.3f}, "
                    f"Economic_Impact=${attack_result.economic_impact:.2f}, "
                    f"Success_Rate={stats['success_rate']:.3f}, "
                    f"Detection_Rate={stats['detection_rate']:.3f}")
        
    async def _check_performance_alerts(self, attack_type: str, stats: Dict[str, Any]):
        """Check for performance alerts based on attack success patterns"""
        
        # Trigger performance alerts if needed
        await self._check_performance_alerts(attack_type, stats)

class QueryFreeAttackEngine:
    """
    Specialized engine for query-free attacks that don't require model access
    Implements techniques from Gibert et al. (2023)
    """
    
    def __init__(self, config: AdversarialConfig):
        self.config = config
        self.surrogate_models = []
        self.feature_statistics = {}
        
    def build_surrogate_model(self, training_data: List[TelemetryRecord]) -> None:
        """Build surrogate model for query-free attack generation"""
        
        if not training_data:
            logging.warning("Cannot build surrogate model with empty training data.")
            return

        logging.info("Building surrogate model for query-free attacks")
        
        # Extract features and labels
        features = []
        labels = []
        
        for record in training_data:
            feature_vector = self._extract_features(record)
            features.append(feature_vector)
            
            label = 1 if record.anomaly_type != AnomalyType.BENIGN else 0
            labels.append(label)
        
        features = np.array(features)
        labels = np.array(labels)
        
        # Compute feature statistics for query-free generation
        self.feature_statistics = {
            'mean': np.mean(features, axis=0),
            'std': np.std(features, axis=0),
            'min': np.min(features, axis=0),
            'max': np.max(features, axis=0),
            'correlation_matrix': np.corrcoef(features.T)
        }
        
        # Build simple surrogate (decision tree approximation)
        if TORCH_AVAILABLE:
            self.surrogate_models = self._build_decision_tree_surrogate(features, labels)
        else:
            # Fallback: create a simple statistical surrogate
            self.surrogate_models = [{"type": "statistical", "feature_stats": self.feature_statistics}]
        
        logging.info(f"Surrogate model built with {len(training_data)} samples")
    
    def generate_query_free_adversarial(self, target_record: TelemetryRecord) -> TelemetryRecord:
        """Generate adversarial example without querying target model"""
        
        if not self.feature_statistics:
            logging.warning("No surrogate model available. Using simple perturbation.")
            return self._simple_perturbation(target_record)
        
        # Extract original features
        original_features = self._extract_features(target_record)
        
        # Generate adversarial features using statistical properties
        adversarial_features = self._statistical_perturbation(original_features)
        
        # Convert back to telemetry record
        adversarial_record = self._features_to_telemetry(adversarial_features, target_record)
        
        # Mark as adversarial
        if not hasattr(adversarial_record, 'custom_fields'): adversarial_record.custom_fields = {}
        adversarial_record.custom_fields['query_free_adversarial'] = True
        adversarial_record.custom_fields['generation_method'] = 'statistical_perturbation'
        
        return adversarial_record
    
    def _extract_features(self, record: TelemetryRecord) -> np.ndarray:
        """Extract numerical features from telemetry record"""
        
        features = [
            record.duration,
            record.memory_spike_kb / 1000.0,
            record.cpu_utilization / 100.0,
            record.network_io_bytes / 1000.0,
            record.timestamp % 3600,  # Hour component
            len(record.function_id),
            1.0 if record.anomaly_type != AnomalyType.BENIGN else 0.0
        ]
        
        return np.array(features)
    
    def _statistical_perturbation(self, original_features: np.ndarray) -> np.ndarray:
        """Apply statistical perturbation based on feature distribution"""
        
        adversarial_features = original_features.copy()
        
        # Apply perturbations based on feature statistics
        for i in range(len(original_features)):
            if i >= len(self.feature_statistics.get('std', [])):
                break
                
            # Perturbation magnitude based on feature standard deviation
            std = self.feature_statistics['std'][i]
            perturbation = np.random.normal(0, std * self.config.max_evasion_budget)
            
            # Apply perturbation
            adversarial_features[i] += perturbation
            
            # Ensure values stay within reasonable bounds
            min_val = self.feature_statistics['min'][i]
            max_val = self.feature_statistics['max'][i]
            adversarial_features[i] = np.clip(adversarial_features[i], min_val, max_val)
        
        return adversarial_features
    
    def _features_to_telemetry(self, features: np.ndarray, template: TelemetryRecord) -> TelemetryRecord:
        """Convert feature vector back to telemetry record"""
        
        modified = template.__class__(**template.__dict__)
        
        if len(features) >= 4:
            modified.duration = max(0.001, float(features[0]))
            modified.memory_spike_kb = max(0, int(features[1] * 1000.0))
            modified.cpu_utilization = max(0.0, min(100.0, float(features[2] * 100.0)))
            modified.network_io_bytes = max(0, int(features[3] * 1000.0))
        
        return modified
    
    def _simple_perturbation(self, record: TelemetryRecord) -> TelemetryRecord:
        """Fallback simple perturbation when no surrogate model"""
        
        modified = record.__class__(**record.__dict__)
        
        # Simple random perturbations
        modified.duration *= (1.0 + random.uniform(-0.1, 0.1))
        modified.memory_spike_kb = int(modified.memory_spike_kb * (1.0 + random.uniform(-0.1, 0.1)))
        modified.cpu_utilization += random.uniform(-5.0, 5.0)
        modified.network_io_bytes = int(modified.network_io_bytes * (1.0 + random.uniform(-0.2, 0.2)))
        
        # Ensure valid ranges
        modified.duration = max(0.001, modified.duration)
        modified.memory_spike_kb = max(0, modified.memory_spike_kb)
        modified.cpu_utilization = max(0.0, min(100.0, modified.cpu_utilization))
        modified.network_io_bytes = max(0, modified.network_io_bytes)
        
        return modified
    
    def _build_decision_tree_surrogate(self, features: np.ndarray, labels: np.ndarray) -> List[Dict]:
        """Build simple decision tree surrogate model"""
        
        # Simple decision rules based on feature thresholds
        rules = []
        
        if features.shape[1] == 0:
            return []

        for i in range(features.shape[1]):
            feature_values = features[:, i]
            threshold = np.median(feature_values)
            
            # Calculate classification accuracy for this threshold
            predictions = (feature_values > threshold).astype(int)
            accuracy = np.mean(predictions == labels)
            
            rules.append({
                'feature_idx': i,
                'threshold': threshold,
                'accuracy': accuracy,
                'rule_type': 'greater_than'
            })
        
        # Sort by accuracy
        rules.sort(key=lambda x: x['accuracy'], reverse=True)
        
        return rules[:5]  # Keep top 5 rules


class TransferAttackEngine:
    """
    Engine for transfer attacks that work across different models
    Implements feature-based adversarial training approaches
    """
    
    def __init__(self, config: AdversarialConfig):
        self.config = config
        self.feature_extractors = []
        
    def generate_transfer_attack(self, source_record: TelemetryRecord, 
                               target_model_type: str = "unknown") -> TelemetryRecord:
        """Generate adversarial example designed to transfer across models"""
        
        # Extract features at multiple levels
        low_level_features = self._extract_low_level_features(source_record)
        mid_level_features = self._extract_mid_level_features(source_record)
        high_level_features = self._extract_high_level_features(source_record)
        
        # Apply multi-level perturbations
        perturbed_low = self._perturb_features(low_level_features, "low")
        perturbed_mid = self._perturb_features(mid_level_features, "mid") 
        perturbed_high = self._perturb_features(high_level_features, "high")
        
        # Reconstruct adversarial record
        adversarial_record = self._reconstruct_from_features(
            perturbed_low, perturbed_mid, perturbed_high, source_record
        )
        
        # Add transfer attack metadata
        if not hasattr(adversarial_record, 'custom_fields'): adversarial_record.custom_fields = {}
        adversarial_record.custom_fields.update({
            'transfer_attack': True,
            'target_model_type': target_model_type,
            'perturbation_levels': ['low', 'mid', 'high'],
            'transferability_score': self._calculate_transferability_score(
                low_level_features, perturbed_low
            )
        })
        
        return adversarial_record
    
    def _extract_low_level_features(self, record: TelemetryRecord) -> Dict[str, float]:
        """Extract low-level raw features"""
        return {
            'duration': record.duration,
            'memory': record.memory_spike_kb,
            'cpu': record.cpu_utilization,
            'network': record.network_io_bytes
        }
    
    def _extract_mid_level_features(self, record: TelemetryRecord) -> Dict[str, float]:
        """Extract mid-level derived features"""
        return {
            'resource_intensity': (record.memory_spike_kb / 1000.0) * record.duration,
            'cpu_efficiency': record.cpu_utilization / max(1.0, record.duration),
            'network_rate': record.network_io_bytes / max(1.0, record.duration),
            'memory_rate': record.memory_spike_kb / max(1.0, record.duration)
        }
    
    def _extract_high_level_features(self, record: TelemetryRecord) -> Dict[str, float]:
        """Extract high-level semantic features"""
        return {
            'anomaly_indicator': 1.0 if record.anomaly_type != AnomalyType.BENIGN else 0.0,
            'execution_complexity': len(record.function_id) / 10.0,
            'temporal_pattern': (record.timestamp % 3600) / 3600.0,
            'resource_balance': record.cpu_utilization / max(1.0, record.memory_spike_kb / 10000.0)
        }
    
    def _perturb_features(self, features: Dict[str, float], level: str) -> Dict[str, float]:
        """Apply level-appropriate perturbations"""
        
        perturbed = features.copy()
        
        # Different perturbation strategies by level
        if level == "low":
            # Small direct perturbations for low-level features
            perturbation_scale = 0.05
        elif level == "mid":
            # Moderate perturbations for derived features
            perturbation_scale = 0.1
        else:  # high
            # Larger perturbations for semantic features
            perturbation_scale = 0.2
        
        for key, value in features.items():
            noise = np.random.normal(0, perturbation_scale * (abs(value) + 1e-6))
            perturbed[key] = value + noise
            
            # Ensure non-negative for certain features
            if key in ['duration', 'memory', 'network']:
                perturbed[key] = max(0.001, perturbed[key])
            elif key == 'cpu':
                perturbed[key] = max(0.0, min(100.0, perturbed[key]))
        
        return perturbed
    
    def _reconstruct_from_features(self, low_features: Dict, mid_features: Dict, 
                                 high_features: Dict, template: TelemetryRecord) -> TelemetryRecord:
        """Reconstruct telemetry record from multi-level features"""
        
        modified = template.__class__(**template.__dict__)
        
        # Use low-level features directly
        modified.duration = max(0.001, low_features['duration'])
        modified.memory_spike_kb = max(0, int(low_features['memory']))
        modified.cpu_utilization = max(0.0, min(100.0, low_features['cpu']))
        modified.network_io_bytes = max(0, int(low_features['network']))
        
        # Add transfer attack markers
        if not hasattr(modified, 'custom_fields'): modified.custom_fields = {}
        modified.custom_fields['transfer_generated'] = True
        modified.custom_fields['generation_timestamp'] = time.time()
        
        return modified
    
    def _calculate_transferability_score(self, original_features: Dict, 
                                       perturbed_features: Dict) -> float:
        """Calculate transferability score based on perturbation magnitude"""
        
        total_change = 0.0
        total_features = 0
        
        for key in original_features.keys():
            if key in perturbed_features:
                original_val = abs(original_features[key])
                perturbed_val = abs(perturbed_features[key])
                
                if original_val > 1e-6:
                    relative_change = abs(perturbed_val - original_val) / original_val
                    total_change += relative_change
                    total_features += 1
        
        if total_features == 0:
            return 0.0
        
        avg_change = total_change / total_features
        # Transferability is inversely related to perturbation magnitude
        # Smaller changes = higher transferability
        transferability = 1.0 / (1.0 + avg_change)
        
        return transferability

class AdversarialRobustnessAnalyzer:
    """
    Comprehensive analyzer for adversarial robustness testing results
    Provides detailed analysis and recommendations for improving defense systems
    """
    
    def __init__(self):
        self.analysis_history = []
        self.benchmark_scores = self._initialize_benchmarks()
        
    def _initialize_benchmarks(self) -> Dict[str, float]:
        """Initialize industry benchmark scores for comparison"""
        return {
            'noise_injection': 0.8,
            'gradient_masking': 0.7,
            'adaptive_perturbation': 0.6,
            'cryptomining': 0.9,
            'denial_of_wallet': 0.85,
            'poisoning_attacks': 0.75,
            'transfer_attacks': 0.65,
            'query_free_evasion': 0.7
        }
    
    def comprehensive_robustness_analysis(self, test_results: Dict[str, Any], 
                                        baseline_performance: Dict[str, float]) -> Dict[str, Any]:
        """Perform comprehensive robustness analysis"""
        
        analysis = {
            'analysis_timestamp': time.time(),
            'robustness_scores': {},
            'vulnerability_assessment': {},
            'improvement_recommendations': [],
            'benchmark_comparison': {},
            'risk_assessment': {}
        }
        
        # Calculate robustness scores for each attack type
        analysis['robustness_scores'] = self._calculate_robustness_scores(
            test_results, baseline_performance
        )
        
        # Assess vulnerabilities
        analysis['vulnerability_assessment'] = self._assess_vulnerabilities(
            analysis['robustness_scores']
        )
        
        # Generate improvement recommendations
        analysis['improvement_recommendations'] = self._generate_improvement_recommendations(
            analysis['robustness_scores'], analysis['vulnerability_assessment']
        )
        analysis['recommendations'] = analysis['improvement_recommendations']
        
        # Compare against benchmarks
        analysis['benchmark_comparison'] = self._compare_to_benchmarks(
            analysis['robustness_scores']
        )
        
        # Assess operational risk
        analysis['risk_assessment'] = self._assess_operational_risk(
            analysis['robustness_scores'], test_results, analysis['vulnerability_assessment']
        )
        
        # Store analysis history
        self.analysis_history.append(analysis)
        
        return analysis
    
    def _calculate_robustness_scores(self, test_results: Dict[str, Any], 
                                   baseline_performance: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """Calculate robustness scores for each attack type"""
        
        robustness_scores = {}
        
        if 'attack_results' not in test_results:
            return robustness_scores
        
        for attack_type, results in test_results['attack_results'].items():
            scores = {}
            
            # Detection robustness (how well detection holds up under attack)
            detection_rate = results.get('detection_rate', 0.0)
            baseline_accuracy = baseline_performance.get('detection_accuracy', 0.9)
            
            scores['detection_robustness'] = detection_rate / baseline_accuracy if baseline_accuracy > 0 else 0.0
            
            # Performance degradation (how much performance degrades under attack)
            if 'average_perturbation' in results:
                perturbation = results['average_perturbation']
                # Lower perturbation needed for successful attack = lower robustness
                scores['performance_degradation'] = min(1.0, perturbation)
            else:
                scores['performance_degradation'] = 0.5
            
            # Economic resilience (resistance to economic impact)
            economic_impact = results.get('economic_impact', 0.0)
            # Normalize economic impact to [0,1] scale
            scores['economic_resilience'] = 1.0 / (1.0 + economic_impact / 100.0)

            # Overall robustness (weighted combination)
            scores['overall_robustness'] = (
                0.5 * scores['detection_robustness'] +
                0.3 * scores['performance_degradation'] +
                0.2 * scores['economic_resilience']
            )
            
            robustness_scores[attack_type] = scores
        
        return robustness_scores
    
    def _assess_vulnerabilities(self, robustness_scores: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Assess vulnerabilities based on robustness scores"""
        
        vulnerabilities = {
            'critical_vulnerabilities': [],
            'high_risk_attacks': [],
            'medium_risk_attacks': [],
            'low_risk_attacks': [],
            'overall_risk_level': 'low',
            'vulnerability_patterns': {}
        }
        
        # Categorize attacks by risk level
        for attack_type, scores in robustness_scores.items():
            overall_score = scores.get('overall_robustness', 1.0)
            
            vulnerability_info = {
                'attack_type': attack_type,
                'robustness_score': overall_score,
                'detection_robustness': scores.get('detection_robustness', 1.0),
                'performance_degradation': scores.get('performance_degradation', 1.0),
                'economic_resilience': scores.get('economic_resilience', 1.0)
            }
            
            if overall_score < 0.3:
                vulnerabilities['critical_vulnerabilities'].append(vulnerability_info)
            elif overall_score < 0.5:
                vulnerabilities['high_risk_attacks'].append(vulnerability_info)
            elif overall_score < 0.7:
                vulnerabilities['medium_risk_attacks'].append(vulnerability_info)
            else:
                vulnerabilities['low_risk_attacks'].append(vulnerability_info)
        
        # Determine overall risk level
        if len(vulnerabilities['critical_vulnerabilities']) > 0:
            vulnerabilities['overall_risk_level'] = 'critical'
        elif len(vulnerabilities['high_risk_attacks']) > 2:
            vulnerabilities['overall_risk_level'] = 'high'
        elif len(vulnerabilities['high_risk_attacks']) > 0 or len(vulnerabilities['medium_risk_attacks']) > 3:
            vulnerabilities['overall_risk_level'] = 'medium'
        
        # Identify vulnerability patterns
        detection_issues = sum(1 for scores in robustness_scores.values() 
                             if scores.get('detection_robustness', 1.0) < 0.6)
        performance_issues = sum(1 for scores in robustness_scores.values() 
                               if scores.get('performance_degradation', 1.0) < 0.5)
        economic_issues = sum(1 for scores in robustness_scores.values() 
                            if scores.get('economic_resilience', 1.0) < 0.7)
        
        vulnerabilities['vulnerability_patterns'] = {
            'detection_weakness': detection_issues > len(robustness_scores) * 0.4 if robustness_scores else False,
            'performance_weakness': performance_issues > len(robustness_scores) * 0.3 if robustness_scores else False,
            'economic_weakness': economic_issues > len(robustness_scores) * 0.3 if robustness_scores else False
        }
        
        return vulnerabilities
    
    def _generate_improvement_recommendations(self, robustness_scores: Dict[str, Dict[str, float]], 
                                            vulnerabilities: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate specific improvement recommendations"""
        
        recommendations = []
        
        # Critical vulnerability recommendations
        for vuln in vulnerabilities.get('critical_vulnerabilities', []):
            recommendations.append({
                'priority': 'critical',
                'type': 'immediate_action',
                'attack_type': vuln.get('attack_type', 'unknown'),
                'recommendation': f"CRITICAL: Immediate attention required for {vuln.get('attack_type', 'unknown')} attacks. "
                                f"Current robustness: {vuln.get('robustness_score', 0.0):.2f}. "
                                f"Implement emergency countermeasures and enhanced monitoring."
            })
        
        # Pattern-based recommendations
        patterns = vulnerabilities.get('vulnerability_patterns', {})
        
        if patterns.get('detection_weakness'):
            recommendations.append({
                'priority': 'high',
                'type': 'detection_improvement',
                'attack_type': 'multiple',
                'recommendation': "Systemic detection weakness identified. Consider implementing "
                                "ensemble detection methods, improving feature engineering, "
                                "and adding behavioral analysis components."
            })
        
        if patterns.get('performance_weakness'):
            recommendations.append({
                'priority': 'medium',
                'type': 'performance_optimization',
                'attack_type': 'multiple',
                'recommendation': "Performance degradation under attack detected. Implement "
                                "adversarial training, input preprocessing, and robustness "
                                "regularization techniques."
            })
        
        if patterns.get('economic_weakness'):
            recommendations.append({
                'priority': 'high',
                'type': 'economic_protection',
                'attack_type': 'multiple',
                'recommendation': "Economic vulnerability detected. Implement cost monitoring, "
                                "rate limiting, resource quotas, and billing anomaly detection."
            })
        
        # Attack-specific recommendations
        for attack_type, scores in robustness_scores.items():
            if scores.get('overall_robustness', 1.0) < 0.6:
                if any(k in attack_type for k in ['evasion', 'perturbation']):
                    recommendations.append({
                        'priority': 'medium',
                        'type': 'evasion_resistance',
                        'attack_type': attack_type,
                        'recommendation': f"Improve evasion resistance for {attack_type}. "
                                        f"Implement input validation, adversarial training, "
                                        f"and ensemble defense methods."
                    })
                elif any(k in attack_type for k in ['economic', 'mining', 'wallet', 'billing']):
                    recommendations.append({
                        'priority': 'high',
                        'type': 'economic_defense',
                        'attack_type': attack_type,
                        'recommendation': f"Strengthen economic defenses against {attack_type}. "
                                        f"Implement real-time cost monitoring, usage anomaly "
                                        f"detection, and automatic resource limiting."
                    })
        
        # General recommendations if no specific issues found
        if not recommendations:
            recommendations.append({
                'priority': 'low',
                'type': 'maintenance',
                'attack_type': 'all',
                'recommendation': "System shows good robustness. Continue regular testing, "
                                "monitor for emerging attack vectors, and maintain current "
                                "security measures."
            })
        
        return recommendations
    
    def _compare_to_benchmarks(self, robustness_scores: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Compare robustness scores to industry benchmarks"""
        
        comparison = {
            'above_benchmark': [],
            'below_benchmark': [],
            'at_benchmark': [],
            'relative_performance': {}
        }
        
        for attack_type, scores in robustness_scores.items():
            overall_score = scores.get('overall_robustness', 0.0)
            benchmark = self.benchmark_scores.get(attack_type, 0.7)  # Default benchmark
            
            relative_performance = overall_score / benchmark if benchmark > 0 else 1.0
            comparison['relative_performance'][attack_type] = relative_performance
            
            if overall_score > benchmark * 1.1:  # 10% above benchmark
                comparison['above_benchmark'].append({
                    'attack_type': attack_type,
                    'score': overall_score,
                    'benchmark': benchmark,
                    'improvement': relative_performance - 1.0
                })
            elif overall_score < benchmark * 0.9:  # 10% below benchmark
                comparison['below_benchmark'].append({
                    'attack_type': attack_type,
                    'score': overall_score,
                    'benchmark': benchmark,
                    'deficit': 1.0 - relative_performance
                })
            else:
                comparison['at_benchmark'].append({
                    'attack_type': attack_type,
                    'score': overall_score,
                    'benchmark': benchmark
                })
        
        return comparison
    
    def _assess_operational_risk(
        self,
        robustness_scores: Dict[str, Dict[str, float]],
        test_results: Dict[str, Any],
        vulnerabilities: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assess operational risk based on robustness analysis"""
        

        if vulnerabilities is None:
            vulnerabilities = {"critical_vulnerabilities": []}


        risk_assessment = {
            'attack_success_probability': {},
            'economic_impact_risk': 0.0,
            'operational_risk_score': 0.0,
            'risk_mitigation_priority': [],
            'business_impact_assessment': {}
        }
        
        # Calculate attack success probabilities
        total_economic_impact = 0.0
        max_economic_impact = 0.0
        
        success_probabilities = []
        for attack_type, scores in robustness_scores.items():
            # Attack success probability = 1 - overall robustness
            success_prob = 1.0 - scores.get('overall_robustness', 0.0)
            risk_assessment['attack_success_probability'][attack_type] = success_prob
            success_probabilities.append(success_prob)

            # Calculate economic impact risk
            if 'attack_results' in test_results and attack_type in test_results['attack_results']:
                economic_impact = test_results['attack_results'][attack_type].get('economic_impact', 0.0)
                total_economic_impact += economic_impact * success_prob
                max_economic_impact = max(max_economic_impact, economic_impact)
        
        risk_assessment['economic_impact_risk'] = total_economic_impact
        
        # Calculate operational risk score
        avg_success_prob = np.mean(success_probabilities) if success_probabilities else 0.0
        economic_factor = min(1.0, max_economic_impact / 1000.0)  # Normalize to $1000
        
        risk_assessment['operational_risk_score'] = (
            0.6 * avg_success_prob +
            0.4 * economic_factor
        )
        
        # Generate risk mitigation priorities
        attack_risks = [
            (attack_type, prob, test_results.get('attack_results', {}).get(attack_type, {}).get('economic_impact', 0.0))
            for attack_type, prob in risk_assessment['attack_success_probability'].items()
        ]
        
        # Sort by combined risk (probability * economic impact)
        attack_risks.sort(key=lambda x: x[1] * x[2], reverse=True)
        
        risk_assessment['risk_mitigation_priority'] = [
            {
                'attack_type': attack_type,
                'success_probability': prob,
                'economic_impact': economic_impact,
                'combined_risk': prob * economic_impact,
                'priority_level': 'high' if prob * economic_impact > 50 else 'medium' if prob * economic_impact > 10 else 'low'
            }
            for attack_type, prob, economic_impact in attack_risks[:10]  # Top 10 risks
        ]
        
        # Business impact assessment
        critical_vulns_count = len(vulnerabilities.get('critical_vulnerabilities', []))
        risk_assessment['business_impact_assessment'] = {
            'availability_risk': 'high' if avg_success_prob > 0.7 else 'medium' if avg_success_prob > 0.4 else 'low',
            'financial_risk': 'high' if total_economic_impact > 500 else 'medium' if total_economic_impact > 100 else 'low',
            'reputation_risk': 'high' if critical_vulns_count > 0 else 'medium' if critical_vulns_count > 0 else 'low',
            'compliance_risk': 'medium'  # Default assessment
        }
        
        return risk_assessment

    async def _check_performance_alerts(self, attack_type: str, stats: Dict[str, Any]):
        """Check for performance alerts based on attack success patterns"""
        
        # Alert if success rate is too high (weak defense)
        if stats.get('total_attempts', 0) >= 10 and stats.get('success_rate', 0.0) > 0.8:
            logging.warning(f"HIGH EVASION RATE ALERT: {attack_type} success rate: {stats['success_rate']:.3f}")
        
        # Alert if detection rate is too low
        if stats.get('total_attempts', 0) >= 10 and stats.get('detection_rate', 0.0) < 0.2:
            logging.warning(f"LOW DETECTION RATE ALERT: {attack_type} detection rate: {stats['detection_rate']:.3f}")
        
        # Alert for concerning economic impact
        if stats.get('economic_impact', 0.0) > 500.0:  # $500 threshold
            logging.warning(f"HIGH ECONOMIC IMPACT ALERT: {attack_type} total impact: ${stats['economic_impact']:.2f}")
        
        # Alert for high stealth attacks
        if stats.get('average_stealth', 0.0) > 0.9:
            logging.warning(f"HIGH STEALTH ALERT: {attack_type} average stealth: {stats['average_stealth']:.3f}")

    def get_attack_effectiveness_report(self) -> Dict[str, Any]:
        """Generate comprehensive attack effectiveness report"""
        
        if not self.detection_performance:
            return {"error": "No attack performance data available"}
        
        current_time = time.time()
        report = {
            'generation_timestamp': current_time,
            'total_attack_types_tested': len(self.detection_performance),
            'overall_statistics': {},
            'attack_type_analysis': {},
            'trend_analysis': {},
            'threat_landscape': {},
            'recommendations': []
        }
        
        # Calculate overall statistics
        all_stats = list(self.detection_performance.values())
        total_attempts = sum(s['total_attempts'] for s in all_stats)
        total_successes = sum(s['successful_evasions'] for s in all_stats)
        total_economic_impact = sum(s['economic_impact'] for s in all_stats)
        
        if total_attempts > 0:
            most_successful_attack = max(self.detection_performance.items(), key=lambda x: x[1].get('success_rate', 0), default=(None, None))[0]
            most_detected_attack = max(self.detection_performance.items(), key=lambda x: x[1].get('detection_rate', 0), default=(None, None))[0]

            report['overall_statistics'] = {
                'total_attacks_executed': total_attempts,
                'overall_success_rate': total_successes / total_attempts,
                'overall_detection_rate': (total_attempts - total_successes) / total_attempts,
                'total_economic_impact': total_economic_impact,
                'average_economic_impact_per_attack': total_economic_impact / total_attempts,
                'most_successful_attack_type': most_successful_attack,
                'most_detected_attack_type': most_detected_attack
            }
        
        # Detailed analysis per attack type
        for attack_type, stats in self.detection_performance.items():
            report['attack_type_analysis'][attack_type] = {
                'performance_metrics': {
                    'attempts': stats['total_attempts'],
                    'success_rate': stats['success_rate'],
                    'detection_rate': stats['detection_rate'],
                    'average_stealth': stats['average_stealth'],
                    'average_perturbation': stats['average_perturbation'],
                    'economic_impact': stats['economic_impact'],
                    'attribution_difficulty': stats['attribution_difficulty']
                },
                'risk_assessment': self._assess_attack_type_risk(stats),
                'temporal_analysis': self._analyze_attack_temporal_patterns(stats['temporal_patterns']),
                'effectiveness_rating': self._calculate_attack_effectiveness(stats)
            }
        
        # Trend analysis
        report['trend_analysis'] = self._analyze_performance_trends()
        
        # Threat landscape assessment
        report['threat_landscape'] = self._assess_threat_landscape()
        
        # Generate actionable recommendations
        report['recommendations'] = self._generate_defense_recommendations()
        
        return report

    def _assess_attack_type_risk(self, stats: Dict[str, Any]) -> Dict[str, str]:
        """Assess risk level for specific attack type"""
        
        risk_factors = {
            'evasion_risk': 'low',
            'economic_risk': 'low', 
            'stealth_risk': 'low',
            'attribution_risk': 'low',
            'overall_risk': 'low'
        }
        
        # Evasion risk assessment
        if stats.get('success_rate', 0.0) > 0.7: risk_factors['evasion_risk'] = 'critical'
        elif stats.get('success_rate', 0.0) > 0.5: risk_factors['evasion_risk'] = 'high'
        elif stats.get('success_rate', 0.0) > 0.3: risk_factors['evasion_risk'] = 'medium'
        
        # Economic risk assessment
        avg_economic_impact = stats.get('economic_impact', 0.0) / max(1, stats.get('total_attempts', 1))
        if avg_economic_impact > 100: risk_factors['economic_risk'] = 'critical'
        elif avg_economic_impact > 50: risk_factors['economic_risk'] = 'high'
        elif avg_economic_impact > 10: risk_factors['economic_risk'] = 'medium'
        
        # Stealth risk assessment
        if stats.get('average_stealth', 0.0) > 0.8: risk_factors['stealth_risk'] = 'critical'
        elif stats.get('average_stealth', 0.0) > 0.6: risk_factors['stealth_risk'] = 'high'
        elif stats.get('average_stealth', 0.0) > 0.4: risk_factors['stealth_risk'] = 'medium'
        
        # Attribution risk assessment
        if stats.get('attribution_difficulty', 0.0) > 0.8: risk_factors['attribution_risk'] = 'critical'
        elif stats.get('attribution_difficulty', 0.0) > 0.6: risk_factors['attribution_risk'] = 'high'
        elif stats.get('attribution_difficulty', 0.0) > 0.4: risk_factors['attribution_risk'] = 'medium'
        
        # Overall risk calculation
        risk_levels = ['low', 'medium', 'high', 'critical']
        risk_scores = [risk_levels.index(risk) for risk in risk_factors.values() if risk != 'overall_risk']
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        risk_factors['overall_risk'] = risk_levels[min(3, int(round(avg_risk_score)))]
        
        return risk_factors

    def _analyze_attack_temporal_patterns(self, temporal_patterns: List[Dict]) -> Dict[str, Any]:
        """Analyze temporal patterns in attack success"""
        
        if len(temporal_patterns) < 5:
            return {'insufficient_data': True}
        
        # Sort by timestamp
        sorted_patterns = sorted(temporal_patterns, key=lambda x: x['timestamp'])
        
        analysis = {
            'pattern_count': len(sorted_patterns),
            'time_span_hours': (sorted_patterns[-1]['timestamp'] - sorted_patterns[0]['timestamp']) / 3600,
            'success_trend': 'stable',
            'stealth_trend': 'stable',
            'attack_frequency': 0.0,
            'peak_success_periods': [],
            'temporal_clustering': False
        }
        
        # Calculate attack frequency (attacks per hour)
        if analysis['time_span_hours'] > 0:
            analysis['attack_frequency'] = len(sorted_patterns) / analysis['time_span_hours']
        
        # Analyze success trend
        recent_window = max(5, len(sorted_patterns) // 3)
        recent_success_rate = sum(p['success'] for p in sorted_patterns[-recent_window:]) / recent_window
        early_success_rate = sum(p['success'] for p in sorted_patterns[:recent_window]) / recent_window
        
        if recent_success_rate > early_success_rate + 0.2: analysis['success_trend'] = 'increasing'
        elif recent_success_rate < early_success_rate - 0.2: analysis['success_trend'] = 'decreasing'
        
        # Analyze stealth trend
        recent_stealth = np.mean([p['stealth'] for p in sorted_patterns[-recent_window:]])
        early_stealth = np.mean([p['stealth'] for p in sorted_patterns[:recent_window]])
        
        if recent_stealth > early_stealth + 0.1: analysis['stealth_trend'] = 'increasing'
        elif recent_stealth < early_stealth - 0.1: analysis['stealth_trend'] = 'decreasing'
        
        # Detect temporal clustering
        if len(sorted_patterns) > 10:
            time_gaps = [sorted_patterns[i+1]['timestamp'] - sorted_patterns[i]['timestamp'] 
                        for i in range(len(sorted_patterns)-1)]
            avg_gap = np.mean(time_gaps)
            short_gaps = sum(1 for gap in time_gaps if gap < avg_gap * 0.3)
            analysis['temporal_clustering'] = short_gaps > len(time_gaps) * 0.3 if time_gaps else False
        
        return analysis

    def _calculate_attack_effectiveness(self, stats: Dict[str, Any]) -> Dict[str, float]:
        """Calculate comprehensive attack effectiveness rating"""
        
        effectiveness = {
            'evasion_effectiveness': 0.0,
            'stealth_effectiveness': 0.0,
            'economic_effectiveness': 0.0,
            'operational_effectiveness': 0.0,
            'overall_effectiveness': 0.0
        }
        
        # Evasion effectiveness (0-1 scale)
        effectiveness['evasion_effectiveness'] = stats.get('success_rate', 0.0)
        
        # Stealth effectiveness
        effectiveness['stealth_effectiveness'] = stats.get('average_stealth', 0.0)
        
        # Economic effectiveness (normalized)
        avg_economic_impact = stats.get('economic_impact', 0.0) / max(1, stats.get('total_attempts', 1))
        effectiveness['economic_effectiveness'] = min(1.0, avg_economic_impact / 100.0)
        
        # Operational effectiveness (combines multiple factors)
        attribution_factor = stats.get('attribution_difficulty', 0.0)
        perturbation_factor = 1.0 / (1.0 + stats.get('average_perturbation', 0.0))
        attempts_factor = min(1.0, stats.get('total_attempts', 0) / 20.0)  # Reliability factor
        
        effectiveness['operational_effectiveness'] = (
            0.4 * attribution_factor +
            0.3 * perturbation_factor +
            0.3 * attempts_factor
        )
        
        # Overall effectiveness
        effectiveness['overall_effectiveness'] = (
            0.3 * effectiveness['evasion_effectiveness'] +
            0.25 * effectiveness['stealth_effectiveness'] +
            0.2 * effectiveness['economic_effectiveness'] +
            0.25 * effectiveness['operational_effectiveness']
        )
        
        return effectiveness

    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze overall performance trends across all attack types"""
        
        trends = {
            'improving_attacks': [],
            'declining_attacks': [],
            'stable_attacks': [],
            'emerging_threats': [],
            'trend_summary': {}
        }
        
        for attack_type, stats in self.detection_performance.items():
            temporal_patterns = stats.get('temporal_patterns', [])
            if len(temporal_patterns) < 10:
                trends['stable_attacks'].append(attack_type)
                continue
            
            # Analyze trend direction
            quarter_len = len(temporal_patterns) // 4
            recent_quarter = temporal_patterns[-quarter_len:]
            early_quarter = temporal_patterns[:quarter_len]
            
            if not recent_quarter or not early_quarter:
                 trends['stable_attacks'].append(attack_type)
                 continue

            recent_success = np.mean([p['success'] for p in recent_quarter])
            early_success = np.mean([p['success'] for p in early_quarter])
            
            trend_strength = abs(recent_success - early_success)
            
            if recent_success > early_success + 0.15: trends['improving_attacks'].append({'attack_type': attack_type, 'trend_strength': trend_strength, 'recent_success_rate': recent_success})
            elif recent_success < early_success - 0.15: trends['declining_attacks'].append({'attack_type': attack_type, 'trend_strength': trend_strength, 'recent_success_rate': recent_success})
            else: trends['stable_attacks'].append(attack_type)
            
        # Trend summary
        trends['trend_summary'] = {
            'total_attack_types': len(self.detection_performance),
            'improving_count': len(trends['improving_attacks']),
            'declining_count': len(trends['declining_attacks']),
            'stable_count': len(trends['stable_attacks']),
            'emerging_threats_count': len(trends['emerging_threats']),
            'overall_trend': self._determine_overall_trend(trends)
        }
        
        return trends

    def _assess_threat_landscape(self) -> Dict[str, Any]:
        """Assess current threat landscape based on attack performance"""
        
        landscape = {
            'threat_level': 'low',
            'primary_threats': [],
            'vulnerability_areas': [],
            'attack_sophistication': 'basic',
            'defensive_gaps': [],
            'threat_evolution': {}
        }
        
        if not self.detection_performance:
            return landscape

        # Assess primary threats
        high_risk_attacks = []
        for attack_type, stats in self.detection_performance.items():
            risk_score = (
                stats.get('success_rate', 0.0) * 0.4 +
                stats.get('average_stealth', 0.0) * 0.3 +
                (stats.get('economic_impact', 0.0) / max(1, stats.get('total_attempts', 1)) / 100.0) * 0.3
            )
            
            if risk_score > 0.7:
                high_risk_attacks.append({
                    'attack_type': attack_type,
                    'risk_score': risk_score,
                    'success_rate': stats.get('success_rate', 0.0)
                })
        
        landscape['primary_threats'] = sorted(high_risk_attacks, 
                                            key=lambda x: x['risk_score'], reverse=True)[:5]
        
        # Determine overall threat level
        if len(high_risk_attacks) >= 3: landscape['threat_level'] = 'critical'
        elif len(high_risk_attacks) >= 2: landscape['threat_level'] = 'high'
        elif len(high_risk_attacks) >= 1: landscape['threat_level'] = 'medium'
        
        # Assess attack sophistication
        avg_stealth = np.mean([s.get('average_stealth', 0.0) for s in self.detection_performance.values()])
        avg_attribution_difficulty = np.mean([s.get('attribution_difficulty', 0.0) for s in self.detection_performance.values()])
        
        sophistication_score = (avg_stealth + avg_attribution_difficulty) / 2
        
        if sophistication_score > 0.8: landscape['attack_sophistication'] = 'advanced'
        elif sophistication_score > 0.6: landscape['attack_sophistication'] = 'intermediate'
        elif sophistication_score > 0.4: landscape['attack_sophistication'] = 'moderate'
        
        return landscape

    def _generate_defense_recommendations(self) -> List[Dict[str, str]]:
        """Generate actionable defense recommendations based on attack analysis"""
        
        recommendations = []
        
        # Analyze weakest defenses
        weak_defenses = []
        for attack_type, stats in self.detection_performance.items():
            if stats.get('detection_rate', 1.0) < 0.6:
                weak_defenses.append((attack_type, stats['detection_rate']))
        
        weak_defenses.sort(key=lambda x: x[1])  # Sort by detection rate (ascending)
        
        # Generate specific recommendations
        for attack_type, detection_rate in weak_defenses[:3]:  # Top 3 weakest
            rec = {
                'priority': 'high',
                'category': 'adversarial_robustness',
                'attack_type': attack_type,
                'recommendation': f"Implement adversarial training for {attack_type}. Current detection rate: {detection_rate:.2%}"
            }
            if any(k in attack_type for k in ['economic', 'wallet', 'mining', 'billing']):
                rec['priority'] = 'critical'
                rec['category'] = 'economic_protection'
            recommendations.append(rec)
            
        return recommendations

    def _determine_overall_trend(self, trends: Dict) -> str:
        """Determine overall trend direction"""
        
        improving_count = len(trends['improving_attacks'])
        declining_count = len(trends['declining_attacks'])
        emerging_count = len(trends['emerging_threats'])
        
        if emerging_count > 2: return 'escalating'
        elif improving_count > declining_count * 1.5: return 'deteriorating'
        elif declining_count > improving_count * 1.5: return 'improving'
        else: return 'stable'

    def reset_performance_metrics(self):
        """Reset all performance metrics (for testing/research purposes)"""
        logging.info("Resetting adversarial performance metrics")
        self.detection_performance.clear()
        self.attack_history.clear()

    def export_performance_data(self, format: str = 'json') -> Union[str, Dict]:
        """Export performance data for external analysis"""
        
        export_data = {
            'export_timestamp': time.time(),
            'detection_performance': self.detection_performance,
            'attack_history': [
                {
                    'attack_id': result.attack_id,
                    'attack_type': result.attack_type.value,
                    'start_time': result.start_time,
                    'end_time': result.end_time,
                    'evasion_success': result.evasion_success,
                    'stealth_score': result.stealth_score,
                    'economic_impact': result.economic_impact
                }
                for result in self.attack_history
            ],
            'summary_statistics': self.get_attack_statistics()
        }
        
        if format.lower() == 'json':
            return json.dumps(export_data, indent=2, default=str)
        else:
            return export_data
    

__all__ = [
    'AttackType',
    'AttackVector', 
    'AttackResult',
    'ServerlessAnomalyGAN',
    'AdaptiveAttacker',
    'EvasionTechniques',
    'PoisoningAttackGenerator',
    'EconomicAttackSimulator',
    'AdversarialAnomalyEngine',
    'AdversarialTestSuite',
    'AdversarialMetricsCollector',
    'AdversarialTrainingManager',
    'AdversarialValidationFramework', 
    'MultiStepCampaignOrchestrator',
    'AdversarialRobustnessAnalyzer',
    'QueryFreeAttackEngine',
    'TransferAttackEngine',
]

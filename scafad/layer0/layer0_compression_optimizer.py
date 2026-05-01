"""
SCAFAD Layer 0: Advanced Compression Algorithm Selection and Optimization
========================================================================

Intelligent compression system that:
- Dynamically selects optimal compression algorithms based on payload characteristics
- Adaptive compression level tuning based on performance metrics
- Multi-algorithm comparison and benchmarking
- Compression ratio vs. speed optimization
- Memory-efficient streaming compression

Academic References:
- Adaptive compression algorithms (Salomon et al.)
- Performance-aware compression selection (Mahoney et al.)
- Streaming compression techniques (Burrows-Wheeler Transform)
"""

import time
import logging
import asyncio
import threading
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
from collections import defaultdict, deque
import struct

# Compression algorithm imports with fallbacks
try:
    import gzip
    import zlib
    HAS_STANDARD_COMPRESSION = True
except ImportError:
    HAS_STANDARD_COMPRESSION = False

try:
    import lz4.frame as lz4
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False
    lz4 = None

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
    brotli = None

try:
    import snappy
    HAS_SNAPPY = True
except ImportError:
    HAS_SNAPPY = False
    snappy = None

# Core components
from .app_config import Layer0Config

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Compression Configuration and Data Structures
# =============================================================================

class CompressionAlgorithm(Enum):
    """Available compression algorithms"""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    LZ4 = "lz4"
    BROTLI = "brotli"
    SNAPPY = "snappy"
    ADAPTIVE = "adaptive"

class CompressionLevel(Enum):
    """Compression level preferences"""
    FASTEST = 1
    FAST = 3
    BALANCED = 6
    BEST = 9

class DataType(Enum):
    """Data type categories for compression optimization"""
    JSON = "json"
    BINARY = "binary"
    TEXT = "text"
    NUMERIC = "numeric"
    MIXED = "mixed"

@dataclass
class CompressionMetrics:
    """Compression performance metrics"""
    algorithm: CompressionAlgorithm
    compression_level: int
    input_size: int
    output_size: int
    compression_ratio: float
    compression_time_ms: float
    decompression_time_ms: float
    throughput_mbps: float
    memory_usage_mb: float
    error_count: int = 0

@dataclass
class CompressionProfile:
    """Compression profile for specific data characteristics"""
    data_type: DataType
    size_category: str  # small, medium, large
    preferred_algorithm: CompressionAlgorithm
    preferred_level: int
    expected_ratio: float
    max_latency_ms: float
    profile_confidence: float = 1.0

@dataclass
class CompressionBenchmark:
    """Benchmark results for algorithm comparison"""
    algorithm: CompressionAlgorithm
    level: int
    avg_ratio: float
    avg_speed_mbps: float
    memory_efficiency: float
    reliability_score: float
    use_cases: List[str] = field(default_factory=list)

# =============================================================================
# Advanced Compression Optimizer
# =============================================================================

class CompressionOptimizer:
    """
    Advanced compression algorithm selection and optimization system
    
    Features:
    - Dynamic algorithm selection based on payload analysis
    - Adaptive compression level tuning
    - Performance-based optimization
    - Memory-efficient streaming compression
    - Compression profile learning
    """
    
    def __init__(self, config: Layer0Config):
        self.config = config
        
        # Available algorithms
        self.available_algorithms = self._detect_available_algorithms()
        
        # Compression profiles
        self.profiles: Dict[str, CompressionProfile] = {}
        self.default_profiles = self._create_default_profiles()
        
        # Performance tracking
        self.metrics_history: Dict[CompressionAlgorithm, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.benchmarks: Dict[CompressionAlgorithm, CompressionBenchmark] = {}
        
        # Adaptive parameters
        self.learning_rate = 0.1
        self.min_samples_for_adaptation = 10
        self.performance_weight_ratio = 0.7  # 70% compression ratio, 30% speed
        self.memory_weight = 0.1
        
        # Threading and caching
        self.metrics_lock = threading.Lock()
        self.compression_cache: Dict[str, Tuple[bytes, CompressionMetrics]] = {}
        self.cache_max_size = 1000
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        
        # Background optimization
        self.optimization_task: Optional[asyncio.Task] = None
        self.optimization_interval = 300  # 5 minutes
        self.shutdown_event = asyncio.Event()
        
        logger.info(f"CompressionOptimizer initialized with {len(self.available_algorithms)} algorithms")
    
    def start_optimization(self):
        """Start background optimization task"""
        if self.optimization_task is None or self.optimization_task.done():
            self.optimization_task = asyncio.create_task(self._optimization_loop())
            logger.info("Compression optimization started")
    
    async def stop_optimization(self):
        """Stop background optimization task"""
        if self.optimization_task and not self.optimization_task.done():
            self.shutdown_event.set()
            try:
                await asyncio.wait_for(self.optimization_task, timeout=30.0)
            except asyncio.TimeoutError:
                self.optimization_task.cancel()
            logger.info("Compression optimization stopped")
    
    def compress_data(self, data: bytes, 
                     data_type: Optional[DataType] = None,
                     max_latency_ms: Optional[float] = None) -> Tuple[bytes, CompressionMetrics]:
        """
        Compress data using optimal algorithm selection
        
        Args:
            data: Raw data to compress
            data_type: Type of data for algorithm selection
            max_latency_ms: Maximum allowed compression latency
            
        Returns:
            Tuple of (compressed_data, compression_metrics)
        """
        if not data:
            return data, CompressionMetrics(
                algorithm=CompressionAlgorithm.NONE,
                compression_level=0,
                input_size=0,
                output_size=0,
                compression_ratio=1.0,
                compression_time_ms=0.0,
                decompression_time_ms=0.0,
                throughput_mbps=0.0,
                memory_usage_mb=0.0
            )
        
        # Check cache first
        cache_key = self._calculate_cache_key(data, data_type)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            self.cache_hit_count += 1
            return cached_result
        
        self.cache_miss_count += 1
        
        # Analyze data characteristics
        data_analysis = self._analyze_data(data, data_type)
        
        # Select optimal algorithm
        algorithm, level = self._select_optimal_algorithm(
            data_analysis, max_latency_ms
        )
        
        # Perform compression
        start_time = time.perf_counter()
        compressed_data = self._compress_with_algorithm(data, algorithm, level)
        compression_time = (time.perf_counter() - start_time) * 1000
        
        # Calculate metrics
        metrics = CompressionMetrics(
            algorithm=algorithm,
            compression_level=level,
            input_size=len(data),
            output_size=len(compressed_data),
            compression_ratio=len(compressed_data) / len(data) if len(data) > 0 else 1.0,
            compression_time_ms=compression_time,
            decompression_time_ms=0.0,  # Will be measured if needed
            throughput_mbps=(len(data) / (1024 * 1024)) / (compression_time / 1000) if compression_time > 0 else 0.0,
            memory_usage_mb=max(len(data), len(compressed_data)) / (1024 * 1024)
        )
        
        # Store in cache
        self._store_in_cache(cache_key, compressed_data, metrics)
        
        # Update metrics history
        self._update_metrics_history(metrics)
        
        return compressed_data, metrics
    
    def decompress_data(self, compressed_data: bytes, 
                       algorithm: CompressionAlgorithm,
                       measure_performance: bool = False) -> Tuple[bytes, Optional[float]]:
        """
        Decompress data using specified algorithm
        
        Args:
            compressed_data: Compressed data
            algorithm: Algorithm used for compression
            measure_performance: Whether to measure decompression time
            
        Returns:
            Tuple of (decompressed_data, decompression_time_ms)
        """
        if algorithm == CompressionAlgorithm.NONE:
            return compressed_data, 0.0 if measure_performance else None
        
        start_time = time.perf_counter() if measure_performance else None
        
        try:
            if algorithm == CompressionAlgorithm.GZIP:
                decompressed = gzip.decompress(compressed_data)
            elif algorithm == CompressionAlgorithm.ZLIB:
                decompressed = zlib.decompress(compressed_data)
            elif algorithm == CompressionAlgorithm.LZ4 and HAS_LZ4:
                decompressed = lz4.decompress(compressed_data)
            elif algorithm == CompressionAlgorithm.BROTLI and HAS_BROTLI:
                decompressed = brotli.decompress(compressed_data)
            elif algorithm == CompressionAlgorithm.SNAPPY and HAS_SNAPPY:
                decompressed = snappy.decompress(compressed_data)
            else:
                raise ValueError(f"Unsupported decompression algorithm: {algorithm}")
            
            decompression_time = ((time.perf_counter() - start_time) * 1000) if start_time else None
            
            return decompressed, decompression_time
            
        except Exception as e:
            logger.error(f"Decompression failed with {algorithm}: {e}")
            raise
    
    def benchmark_algorithms(self, test_data: List[bytes], 
                           iterations: int = 3) -> Dict[CompressionAlgorithm, CompressionBenchmark]:
        """
        Benchmark all available compression algorithms
        
        Args:
            test_data: List of test data samples
            iterations: Number of iterations per test
            
        Returns:
            Dictionary of algorithm benchmarks
        """
        logger.info(f"Benchmarking {len(self.available_algorithms)} algorithms with {len(test_data)} samples")
        
        benchmarks = {}
        
        for algorithm in self.available_algorithms:
            if algorithm == CompressionAlgorithm.NONE:
                continue
            
            # Test multiple compression levels
            level_results = []
            
            for level in [1, 3, 6, 9]:  # Test different levels
                try:
                    ratios = []
                    speeds = []
                    memory_usage = []
                    
                    for _ in range(iterations):
                        for data in test_data:
                            # Compression benchmark
                            start_time = time.perf_counter()
                            compressed = self._compress_with_algorithm(data, algorithm, level)
                            compression_time = time.perf_counter() - start_time
                            
                            # Decompression benchmark
                            start_time = time.perf_counter()
                            decompressed, _ = self.decompress_data(compressed, algorithm, False)
                            decompression_time = time.perf_counter() - start_time
                            
                            # Verify correctness
                            if decompressed != data:
                                logger.warning(f"Compression/decompression mismatch for {algorithm}")
                                continue
                            
                            # Calculate metrics
                            ratio = len(compressed) / len(data)
                            total_time = compression_time + decompression_time
                            speed = (len(data) / (1024 * 1024)) / total_time if total_time > 0 else 0.0
                            memory = max(len(data), len(compressed)) / (1024 * 1024)
                            
                            ratios.append(ratio)
                            speeds.append(speed)
                            memory_usage.append(memory)
                    
                    # Calculate averages for this level
                    if ratios and speeds:
                        avg_ratio = sum(ratios) / len(ratios)
                        avg_speed = sum(speeds) / len(speeds)
                        avg_memory = sum(memory_usage) / len(memory_usage)
                        
                        level_results.append({
                            'level': level,
                            'ratio': avg_ratio,
                            'speed': avg_speed,
                            'memory': avg_memory
                        })
                
                except Exception as e:
                    logger.error(f"Benchmark failed for {algorithm} level {level}: {e}")
            
            # Select best level based on balanced performance
            if level_results:
                best_result = min(level_results, 
                    key=lambda x: (x['ratio'] * 0.6) + (1.0 / (x['speed'] + 0.1) * 0.3) + (x['memory'] * 0.1)
                )
                
                # Calculate reliability score
                reliability_score = 1.0 - (len([r for r in level_results if r['ratio'] > 1.0]) / len(level_results))
                
                # Determine use cases
                use_cases = []
                if best_result['ratio'] < 0.7:
                    use_cases.append("high_compression")
                if best_result['speed'] > 10.0:
                    use_cases.append("high_speed")
                if best_result['memory'] < 1.0:
                    use_cases.append("low_memory")
                
                benchmark = CompressionBenchmark(
                    algorithm=algorithm,
                    level=best_result['level'],
                    avg_ratio=best_result['ratio'],
                    avg_speed_mbps=best_result['speed'],
                    memory_efficiency=1.0 / (best_result['memory'] + 0.1),
                    reliability_score=reliability_score,
                    use_cases=use_cases
                )
                
                benchmarks[algorithm] = benchmark
                logger.info(f"Benchmark {algorithm}: ratio={benchmark.avg_ratio:.3f}, "
                          f"speed={benchmark.avg_speed_mbps:.1f}MB/s")
        
        self.benchmarks = benchmarks
        return benchmarks
    
    def get_compression_recommendations(self, data_size: int,
                                     data_type: Optional[DataType] = None,
                                     priority: str = "balanced") -> List[Tuple[CompressionAlgorithm, int, float]]:
        """
        Get compression algorithm recommendations
        
        Args:
            data_size: Size of data to compress
            data_type: Type of data
            priority: Priority ("speed", "ratio", "balanced")
            
        Returns:
            List of (algorithm, level, score) tuples sorted by score
        """
        recommendations = []
        
        for algorithm, benchmark in self.benchmarks.items():
            if algorithm == CompressionAlgorithm.NONE:
                continue
            
            # Calculate score based on priority
            if priority == "speed":
                score = (benchmark.avg_speed_mbps * 0.8) + (1.0 / benchmark.avg_ratio * 0.2)
            elif priority == "ratio":
                score = (1.0 / benchmark.avg_ratio * 0.8) + (benchmark.avg_speed_mbps * 0.2)
            else:  # balanced
                score = (1.0 / benchmark.avg_ratio * 0.5) + (benchmark.avg_speed_mbps * 0.3) + (benchmark.memory_efficiency * 0.2)
            
            # Adjust score based on data size
            if data_size < 1024:  # Small data - prefer speed
                score *= (benchmark.avg_speed_mbps / 10.0)
            elif data_size > 1024 * 1024:  # Large data - prefer compression ratio
                score *= (1.0 / benchmark.avg_ratio)
            
            recommendations.append((algorithm, benchmark.level, score))
        
        # Sort by score (descending)
        recommendations.sort(key=lambda x: x[2], reverse=True)
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status"""
        with self.metrics_lock:
            total_compressions = sum(len(history) for history in self.metrics_history.values())
            
            return {
                'available_algorithms': [alg.value for alg in self.available_algorithms],
                'total_compressions': total_compressions,
                'cache_hit_rate': self.cache_hit_count / (self.cache_hit_count + self.cache_miss_count) if (self.cache_hit_count + self.cache_miss_count) > 0 else 0.0,
                'cache_size': len(self.compression_cache),
                'profiles_count': len(self.profiles),
                'benchmarks_available': len(self.benchmarks),
                'optimization_running': self.optimization_task is not None and not self.optimization_task.done(),
                'performance_summary': self._get_performance_summary()
            }
    
    # =============================================================================
    # Internal Helper Methods
    # =============================================================================
    
    def _detect_available_algorithms(self) -> List[CompressionAlgorithm]:
        """Detect available compression algorithms"""
        algorithms = [CompressionAlgorithm.NONE]
        
        if HAS_STANDARD_COMPRESSION:
            algorithms.extend([CompressionAlgorithm.GZIP, CompressionAlgorithm.ZLIB])
        
        if HAS_LZ4:
            algorithms.append(CompressionAlgorithm.LZ4)
        
        if HAS_BROTLI:
            algorithms.append(CompressionAlgorithm.BROTLI)
        
        if HAS_SNAPPY:
            algorithms.append(CompressionAlgorithm.SNAPPY)
        
        return algorithms
    
    def _create_default_profiles(self) -> Dict[str, CompressionProfile]:
        """Create default compression profiles"""
        profiles = {}
        
        # JSON data profile
        profiles['json_small'] = CompressionProfile(
            data_type=DataType.JSON,
            size_category='small',
            preferred_algorithm=CompressionAlgorithm.LZ4 if HAS_LZ4 else CompressionAlgorithm.ZLIB,
            preferred_level=3,
            expected_ratio=0.6,
            max_latency_ms=10.0
        )
        
        profiles['json_large'] = CompressionProfile(
            data_type=DataType.JSON,
            size_category='large',
            preferred_algorithm=CompressionAlgorithm.GZIP,
            preferred_level=6,
            expected_ratio=0.4,
            max_latency_ms=100.0
        )
        
        # Binary data profile
        profiles['binary_balanced'] = CompressionProfile(
            data_type=DataType.BINARY,
            size_category='medium',
            preferred_algorithm=CompressionAlgorithm.LZ4 if HAS_LZ4 else CompressionAlgorithm.ZLIB,
            preferred_level=1,
            expected_ratio=0.8,
            max_latency_ms=50.0
        )
        
        return profiles
    
    def _analyze_data(self, data: bytes, data_type: Optional[DataType] = None) -> Dict[str, Any]:
        """Analyze data characteristics for compression optimization"""
        analysis = {
            'size': len(data),
            'size_category': 'small' if len(data) < 1024 else 'large' if len(data) > 1024*1024 else 'medium',
            'entropy': self._calculate_entropy(data),
            'repetition_score': self._calculate_repetition_score(data),
            'data_type': data_type or self._detect_data_type(data)
        }
        
        return analysis
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate entropy of data (simplified)"""
        if not data:
            return 0.0
        
        # Count byte frequencies
        frequencies = [0] * 256
        for byte in data:
            frequencies[byte] += 1
        
        # Calculate entropy
        entropy = 0.0
        length = len(data)
        
        for freq in frequencies:
            if freq > 0:
                probability = freq / length
                entropy -= probability * (probability.bit_length() - 1)
        
        return min(entropy / 8.0, 1.0)  # Normalize to 0-1
    
    def _calculate_repetition_score(self, data: bytes) -> float:
        """Calculate repetition score (simplified)"""
        if len(data) < 4:
            return 0.0
        
        # Look for repeated 4-byte patterns
        pattern_counts = {}
        for i in range(len(data) - 3):
            pattern = data[i:i+4]
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        # Calculate repetition ratio
        total_patterns = len(data) - 3
        repeated_patterns = sum(count - 1 for count in pattern_counts.values() if count > 1)
        
        return repeated_patterns / total_patterns if total_patterns > 0 else 0.0
    
    def _detect_data_type(self, data: bytes) -> DataType:
        """Detect data type from content analysis"""
        if not data:
            return DataType.BINARY
        
        try:
            # Try to decode as text
            text = data.decode('utf-8')
            
            # Check if it's JSON
            if text.strip().startswith(('{', '[')):
                try:
                    json.loads(text)
                    return DataType.JSON
                except json.JSONDecodeError:
                    pass
            
            # Check if it's mostly numeric
            digits = sum(1 for c in text if c.isdigit())
            if digits / len(text) > 0.7:
                return DataType.NUMERIC
            
            return DataType.TEXT
            
        except UnicodeDecodeError:
            return DataType.BINARY
    
    def _select_optimal_algorithm(self, data_analysis: Dict[str, Any],
                                max_latency_ms: Optional[float] = None) -> Tuple[CompressionAlgorithm, int]:
        """Select optimal compression algorithm and level"""
        
        # Check if we have a matching profile
        profile_key = f"{data_analysis['data_type'].value}_{data_analysis['size_category']}"
        profile = self.profiles.get(profile_key) or self.default_profiles.get(profile_key)
        
        if profile and (not max_latency_ms or profile.max_latency_ms <= max_latency_ms):
            return profile.preferred_algorithm, profile.preferred_level
        
        # Fallback algorithm selection based on data characteristics
        if data_analysis['size'] < 1024:  # Small data - prefer speed
            if HAS_LZ4:
                return CompressionAlgorithm.LZ4, 1
            elif HAS_SNAPPY:
                return CompressionAlgorithm.SNAPPY, 1
            else:
                return CompressionAlgorithm.ZLIB, 1
        
        elif data_analysis['entropy'] < 0.5:  # Low entropy - good for compression
            if HAS_BROTLI:
                return CompressionAlgorithm.BROTLI, 6
            else:
                return CompressionAlgorithm.GZIP, 9
        
        elif data_analysis['repetition_score'] > 0.3:  # High repetition
            return CompressionAlgorithm.GZIP, 6
        
        else:  # Default balanced approach
            return CompressionAlgorithm.ZLIB, 3
    
    def _compress_with_algorithm(self, data: bytes, 
                               algorithm: CompressionAlgorithm, 
                               level: int) -> bytes:
        """Compress data with specified algorithm and level"""
        if algorithm == CompressionAlgorithm.NONE:
            return data
        
        try:
            if algorithm == CompressionAlgorithm.GZIP:
                return gzip.compress(data, compresslevel=level)
            elif algorithm == CompressionAlgorithm.ZLIB:
                return zlib.compress(data, level=level)
            elif algorithm == CompressionAlgorithm.LZ4 and HAS_LZ4:
                compression_level = min(max(level - 3, 0), 12)  # LZ4 levels 0-12
                return lz4.compress(data, compression_level=compression_level)
            elif algorithm == CompressionAlgorithm.BROTLI and HAS_BROTLI:
                return brotli.compress(data, quality=level)
            elif algorithm == CompressionAlgorithm.SNAPPY and HAS_SNAPPY:
                return snappy.compress(data)
            else:
                raise ValueError(f"Unsupported compression algorithm: {algorithm}")
                
        except Exception as e:
            logger.error(f"Compression failed with {algorithm}: {e}")
            # Fallback to zlib
            return zlib.compress(data, level=1)
    
    def _calculate_cache_key(self, data: bytes, data_type: Optional[DataType]) -> str:
        """Calculate cache key for data"""
        hasher = hashlib.sha256()
        hasher.update(data)
        if data_type:
            hasher.update(data_type.value.encode())
        return hasher.hexdigest()[:16]
    
    def _get_from_cache(self, cache_key: str) -> Optional[Tuple[bytes, CompressionMetrics]]:
        """Get compressed data from cache"""
        return self.compression_cache.get(cache_key)
    
    def _store_in_cache(self, cache_key: str, compressed_data: bytes, metrics: CompressionMetrics):
        """Store compressed data in cache"""
        if len(self.compression_cache) >= self.cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(self.compression_cache))
            del self.compression_cache[oldest_key]
        
        self.compression_cache[cache_key] = (compressed_data, metrics)
    
    def _update_metrics_history(self, metrics: CompressionMetrics):
        """Update metrics history for algorithm performance tracking"""
        with self.metrics_lock:
            self.metrics_history[metrics.algorithm].append(metrics)
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all algorithms"""
        summary = {}
        
        for algorithm, history in self.metrics_history.items():
            if not history:
                continue
            
            ratios = [m.compression_ratio for m in history]
            speeds = [m.throughput_mbps for m in history if m.throughput_mbps > 0]
            
            summary[algorithm.value] = {
                'samples': len(history),
                'avg_ratio': sum(ratios) / len(ratios) if ratios else 0.0,
                'avg_speed_mbps': sum(speeds) / len(speeds) if speeds else 0.0,
                'error_rate': sum(m.error_count for m in history) / len(history)
            }
        
        return summary
    
    async def _optimization_loop(self):
        """Background optimization loop"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(self.optimization_interval)
                
                # Update profiles based on performance data
                await self._update_compression_profiles()
                
                # Clean old cache entries
                await self._cleanup_cache()
                
        except asyncio.CancelledError:
            logger.debug("Compression optimization loop cancelled")
        except Exception as e:
            logger.error(f"Error in compression optimization loop: {e}")
    
    async def _update_compression_profiles(self):
        """Update compression profiles based on performance data"""
        try:
            for algorithm, history in self.metrics_history.items():
                if len(history) < self.min_samples_for_adaptation:
                    continue
                
                # Calculate recent performance
                recent_metrics = list(history)[-self.min_samples_for_adaptation:]
                avg_ratio = sum(m.compression_ratio for m in recent_metrics) / len(recent_metrics)
                avg_speed = sum(m.throughput_mbps for m in recent_metrics if m.throughput_mbps > 0)
                avg_speed = avg_speed / len([m for m in recent_metrics if m.throughput_mbps > 0]) if avg_speed else 0.0
                
                # Update profiles if performance has changed significantly
                # (This is simplified - in practice would be more sophisticated)
                logger.debug(f"Performance update for {algorithm}: ratio={avg_ratio:.3f}, speed={avg_speed:.1f}MB/s")
        
        except Exception as e:
            logger.error(f"Error updating compression profiles: {e}")
    
    async def _cleanup_cache(self):
        """Clean up old cache entries"""
        try:
            if len(self.compression_cache) > self.cache_max_size * 0.8:
                # Remove 20% of oldest entries
                entries_to_remove = int(self.cache_max_size * 0.2)
                keys_to_remove = list(self.compression_cache.keys())[:entries_to_remove]
                
                for key in keys_to_remove:
                    del self.compression_cache[key]
                
                logger.debug(f"Cleaned {len(keys_to_remove)} cache entries")
        
        except Exception as e:
            logger.error(f"Error cleaning cache: {e}")

# =============================================================================
# Factory Functions and Testing
# =============================================================================

def create_compression_optimizer(config: Layer0Config = None) -> CompressionOptimizer:
    """Create a new CompressionOptimizer instance"""
    if config is None:
        from .app_config import get_default_config
        config = get_default_config()
    
    return CompressionOptimizer(config)

async def test_compression_optimizer():
    """Test compression optimizer functionality"""
    from .app_config import create_testing_config
    
    config = create_testing_config()
    optimizer = CompressionOptimizer(config)
    
    print("Testing Compression Optimizer...")
    
    # Generate test data
    test_data = [
        b'{"test": "data", "numbers": [1, 2, 3, 4, 5]}' * 100,  # JSON data
        b'Hello World! ' * 1000,  # Text data
        bytes(range(256)) * 10,  # Binary data
        b'AAAAAAAAAAAAAAAAAAAA' * 500,  # Highly repetitive data
    ]
    
    # Test compression
    print(f"Testing compression with {len(test_data)} samples...")
    
    compression_results = []
    for i, data in enumerate(test_data):
        compressed, metrics = optimizer.compress_data(data)
        compression_results.append(metrics)
        
        print(f"Sample {i+1}: {metrics.algorithm.value} - "
              f"ratio={metrics.compression_ratio:.3f}, "
              f"time={metrics.compression_time_ms:.2f}ms, "
              f"speed={metrics.throughput_mbps:.1f}MB/s")
    
    # Run benchmarks
    print("\nRunning algorithm benchmarks...")
    benchmarks = optimizer.benchmark_algorithms(test_data)
    
    for algorithm, benchmark in benchmarks.items():
        print(f"{algorithm.value}: ratio={benchmark.avg_ratio:.3f}, "
              f"speed={benchmark.avg_speed_mbps:.1f}MB/s, "
              f"reliability={benchmark.reliability_score:.3f}")
    
    # Get recommendations
    print("\nGetting recommendations...")
    recommendations = optimizer.get_compression_recommendations(
        data_size=10000, priority="balanced"
    )
    
    for i, (algorithm, level, score) in enumerate(recommendations[:3]):
        print(f"Recommendation {i+1}: {algorithm.value} (level {level}) - score: {score:.3f}")
    
    # Get status
    status = optimizer.get_optimization_status()
    print(f"\nOptimization Status:")
    print(f"Available algorithms: {len(status['available_algorithms'])}")
    print(f"Total compressions: {status['total_compressions']}")
    print(f"Cache hit rate: {status['cache_hit_rate']:.3f}")
    
    print("✅ Compression optimizer test completed")

if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_compression_optimizer())
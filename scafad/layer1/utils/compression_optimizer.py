#!/usr/bin/env python3
"""
SCAFAD Layer 1: Compression Optimizer Utility
============================================

The Compression Optimizer provides payload size optimization utilities for Layer 1's
behavioral intake zone. It supports:

- Adaptive compression algorithms based on data characteristics
- Payload size optimization while preserving anomaly signatures
- Compression ratio analysis and optimization
- Memory-efficient compression for large datasets
- Performance-optimized compression strategies

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import gzip
import zlib
import lzma
import bz2
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from enum import Enum, auto
import time
import base64
import hashlib

# =============================================================================
# Compression Optimizer Data Models
# =============================================================================

class CompressionAlgorithm(Enum):
    """Supported compression algorithms"""
    NONE = "none"                     # No compression
    GZIP = "gzip"                     # Gzip compression (fast, good ratio)
    ZLIB = "zlib"                     # Zlib compression (balanced)
    LZMA = "lzma"                     # LZMA compression (high ratio, slower)
    BZIP2 = "bzip2"                   # Bzip2 compression (high ratio, slower)
    LZ4 = "lz4"                       # LZ4 compression (very fast, lower ratio)
    ZSTD = "zstd"                     # Zstandard compression (balanced, modern)

class CompressionLevel(Enum):
    """Compression levels"""
    FASTEST = "fastest"               # Fastest compression, lower ratio
    FAST = "fast"                     # Fast compression, balanced ratio
    BALANCED = "balanced"             # Balanced speed and ratio
    HIGH = "high"                     # High compression, slower
    MAXIMUM = "maximum"               # Maximum compression, slowest

class OptimizationStrategy(Enum):
    """Optimization strategies"""
    SPEED_OPTIMIZED = "speed_optimized"      # Prioritize compression speed
    RATIO_OPTIMIZED = "ratio_optimized"      # Prioritize compression ratio
    BALANCED = "balanced"                    # Balance speed and ratio
    ADAPTIVE = "adaptive"                    # Adapt based on data characteristics
    ANOMALY_PRESERVING = "anomaly_preserving"  # Preserve anomaly signatures

@dataclass
class CompressionResult:
    """Result of a compression operation"""
    original_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    algorithm: CompressionAlgorithm
    level: CompressionLevel
    processing_time_ms: float
    memory_usage_bytes: int
    checksum: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Calculate compression ratio if not provided"""
        if self.compression_ratio == 0:
            self.compression_ratio = (self.original_size_bytes - self.compressed_size_bytes) / self.original_size_bytes

@dataclass
class CompressionMetrics:
    """Compression performance metrics"""
    algorithm: CompressionAlgorithm
    level: CompressionLevel
    input_size_bytes: int
    output_size_bytes: int
    compression_ratio: float
    processing_time_ms: float
    throughput_mbps: float
    memory_usage_bytes: int
    timestamp: float

@dataclass
class OptimizationProfile:
    """Compression optimization profile"""
    strategy: OptimizationStrategy
    target_compression_ratio: float
    max_processing_time_ms: float
    max_memory_usage_bytes: int
    preserve_anomaly_features: bool
    algorithm_preferences: List[CompressionAlgorithm]
    level_preferences: List[CompressionLevel]

# =============================================================================
# Compression Optimizer Core Classes
# =============================================================================

class CompressionOptimizer:
    """
    Main compression optimizer for Layer 1 payload optimization
    
    Provides intelligent compression selection and optimization based on:
    - Data characteristics and size
    - Performance requirements
    - Anomaly preservation needs
    - Memory constraints
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize compression optimizer with configuration"""
        self.config = config or {}
        self.logger = logging.getLogger("SCAFAD.Layer1.CompressionOptimizer")
        
        # Initialize compression algorithms
        self._initialize_algorithms()
        
        # Performance tracking
        self.performance_history: List[CompressionMetrics] = []
        self.optimization_cache: Dict[str, CompressionResult] = {}
        
        # Default optimization profile
        self.default_profile = OptimizationProfile(
            strategy=OptimizationStrategy.BALANCED,
            target_compression_ratio=0.7,
            max_processing_time_ms=1.0,
            max_memory_usage_bytes=64 * 1024,  # 64KB
            preserve_anomaly_features=True,
            algorithm_preferences=[CompressionAlgorithm.ZSTD, CompressionAlgorithm.GZIP, CompressionAlgorithm.LZ4],
            level_preferences=[CompressionLevel.BALANCED, CompressionLevel.FAST, CompressionLevel.HIGH]
        )
    
    def _initialize_algorithms(self):
        """Initialize available compression algorithms"""
        self.algorithms = {
            CompressionAlgorithm.GZIP: self._compress_gzip,
            CompressionAlgorithm.ZLIB: self._compress_zlib,
            CompressionAlgorithm.LZMA: self._compress_lzma,
            CompressionAlgorithm.BZIP2: self._compress_bzip2,
            CompressionAlgorithm.LZ4: self._compress_lz4,
            CompressionAlgorithm.ZSTD: self._compress_zstd
        }
        
        # Check algorithm availability
        self.available_algorithms = []
        for alg, func in self.algorithms.items():
            try:
                # Test algorithm availability
                test_data = b"test"
                func(test_data, CompressionLevel.FASTEST)
                self.available_algorithms.append(alg)
            except Exception as e:
                self.logger.warning(f"Algorithm {alg.value} not available: {e}")
    
    def optimize_payload(self, 
                        data: Union[str, bytes, Dict[str, Any]], 
                        profile: Optional[OptimizationProfile] = None,
                        preserve_anomaly_features: bool = True) -> CompressionResult:
        """
        Optimize payload compression based on data characteristics and requirements
        
        Args:
            data: Data to compress
            profile: Optimization profile to use
            preserve_anomaly_features: Whether to preserve anomaly detection features
            
        Returns:
            CompressionResult with optimal compression
        """
        profile = profile or self.default_profile
        
        # Convert data to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, dict):
            data_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
        else:
            data_bytes = data
        
        # Analyze data characteristics
        data_analysis = self._analyze_data_characteristics(data_bytes)
        
        # Select optimal compression strategy
        optimal_algorithm, optimal_level = self._select_optimal_compression(
            data_analysis, profile, preserve_anomaly_features
        )
        
        # Perform compression
        start_time = time.time()
        compressed_data = self._compress_data(data_bytes, optimal_algorithm, optimal_level)
        processing_time = (time.time() - start_time) * 1000
        
        # Calculate checksum for integrity
        checksum = hashlib.sha256(compressed_data).hexdigest()
        
        # Create result
        result = CompressionResult(
            original_size_bytes=len(data_bytes),
            compressed_size_bytes=len(compressed_data),
            compression_ratio=0.0,  # Will be calculated in post_init
            algorithm=optimal_algorithm,
            level=optimal_level,
            processing_time_ms=processing_time,
            memory_usage_bytes=len(compressed_data),
            checksum=checksum,
            metadata={
                'data_analysis': data_analysis,
                'optimization_profile': profile.strategy.value,
                'anomaly_features_preserved': preserve_anomaly_features
            }
        )
        
        # Cache result for future optimization
        cache_key = f"{hash(data_bytes)}_{optimal_algorithm.value}_{optimal_level.value}"
        self.optimization_cache[cache_key] = result
        
        # Track performance
        self._track_performance(result)
        
        return result
    
    def _analyze_data_characteristics(self, data: bytes) -> Dict[str, Any]:
        """Analyze data characteristics for compression optimization"""
        analysis = {
            'size_bytes': len(data),
            'entropy': self._calculate_entropy(data),
            'repetition_patterns': self._detect_repetition_patterns(data),
            'text_ratio': self._calculate_text_ratio(data),
            'binary_ratio': self._calculate_binary_ratio(data),
            'compressibility_score': 0.0
        }
        
        # Calculate compressibility score
        analysis['compressibility_score'] = self._calculate_compressibility_score(analysis)
        
        return analysis
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of the data"""
        if not data:
            return 0.0
        
        # Count byte frequencies
        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1
        
        # Calculate entropy
        entropy = 0.0
        data_len = len(data)
        for count in byte_counts:
            if count > 0:
                probability = count / data_len
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy
    
    def _detect_repetition_patterns(self, data: bytes) -> Dict[str, Any]:
        """Detect repetition patterns in the data"""
        patterns = {
            'has_repetitions': False,
            'repetition_ratio': 0.0,
            'common_patterns': []
        }
        
        if len(data) < 100:  # Too small for meaningful pattern analysis
            return patterns
        
        # Simple pattern detection (can be enhanced with more sophisticated algorithms)
        pattern_counts = {}
        for pattern_length in [4, 8, 16]:
            for i in range(len(data) - pattern_length + 1):
                pattern = data[i:i + pattern_length]
                pattern_str = pattern.hex()
                pattern_counts[pattern_str] = pattern_counts.get(pattern_str, 0) + 1
        
        # Find common patterns
        threshold = max(1, len(data) // 1000)  # Pattern must appear at least this many times
        common_patterns = [p for p, count in pattern_counts.items() if count >= threshold]
        
        patterns['has_repetitions'] = len(common_patterns) > 0
        patterns['repetition_ratio'] = len(common_patterns) / len(pattern_counts) if pattern_counts else 0.0
        patterns['common_patterns'] = common_patterns[:10]  # Top 10 patterns
        
        return patterns
    
    def _calculate_text_ratio(self, data: bytes) -> float:
        """Calculate the ratio of text-like content"""
        if not data:
            return 0.0
        
        text_chars = 0
        for byte in data:
            if 32 <= byte <= 126 or byte in [9, 10, 13]:  # Printable ASCII + whitespace
                text_chars += 1
        
        return text_chars / len(data)
    
    def _calculate_binary_ratio(self, data: bytes) -> float:
        """Calculate the ratio of binary content"""
        return 1.0 - self._calculate_text_ratio(data)
    
    def _calculate_compressibility_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall compressibility score (0.0 = not compressible, 1.0 = highly compressible)"""
        score = 0.0
        
        # Size factor (smaller data is less compressible)
        if analysis['size_bytes'] < 100:
            score += 0.1
        elif analysis['size_bytes'] < 1000:
            score += 0.2
        elif analysis['size_bytes'] < 10000:
            score += 0.3
        else:
            score += 0.4
        
        # Entropy factor (lower entropy = more compressible)
        entropy_score = max(0, 1.0 - analysis['entropy'] / 8.0)  # Normalize to 0-1
        score += entropy_score * 0.3
        
        # Repetition factor
        if analysis['repetition_patterns']['has_repetitions']:
            score += analysis['repetition_patterns']['repetition_ratio'] * 0.2
        
        # Text ratio factor (text is generally more compressible)
        text_score = analysis['text_ratio'] * 0.1
        score += text_score
        
        return min(1.0, score)
    
    def _select_optimal_compression(self, 
                                  data_analysis: Dict[str, Any], 
                                  profile: OptimizationProfile,
                                  preserve_anomaly_features: bool) -> Tuple[CompressionAlgorithm, CompressionLevel]:
        """Select optimal compression algorithm and level based on analysis and profile"""
        
        # Filter available algorithms based on profile preferences
        available_algos = [alg for alg in profile.algorithm_preferences 
                          if alg in self.available_algorithms]
        
        if not available_algos:
            available_algos = self.available_algorithms
        
        # Select algorithm based on strategy
        if profile.strategy == OptimizationStrategy.SPEED_OPTIMIZED:
            # Prefer fast algorithms
            if CompressionAlgorithm.LZ4 in available_algos:
                algorithm = CompressionAlgorithm.LZ4
            elif CompressionAlgorithm.GZIP in available_algos:
                algorithm = CompressionAlgorithm.GZIP
            else:
                algorithm = available_algos[0]
            level = CompressionLevel.FASTEST
        
        elif profile.strategy == OptimizationStrategy.RATIO_OPTIMIZED:
            # Prefer high compression algorithms
            if CompressionAlgorithm.LZMA in available_algos:
                algorithm = CompressionAlgorithm.LZMA
            elif CompressionAlgorithm.BZIP2 in available_algos:
                algorithm = CompressionAlgorithm.BZIP2
            else:
                algorithm = available_algos[0]
            level = CompressionLevel.MAXIMUM
        
        elif profile.strategy == OptimizationStrategy.ANOMALY_PRESERVING:
            # Balance compression with anomaly preservation
            if preserve_anomaly_features:
                # Use algorithms that preserve data structure
                if CompressionAlgorithm.ZSTD in available_algos:
                    algorithm = CompressionAlgorithm.ZSTD
                elif CompressionAlgorithm.GZIP in available_algos:
                    algorithm = CompressionAlgorithm.GZIP
                else:
                    algorithm = available_algos[0]
                level = CompressionLevel.BALANCED
            else:
                # Can use more aggressive compression
                algorithm = available_algos[0]
                level = CompressionLevel.HIGH
        
        else:  # BALANCED or ADAPTIVE
            # Use adaptive selection based on data characteristics
            if data_analysis['compressibility_score'] > 0.7:
                # Highly compressible data - use high compression
                if CompressionAlgorithm.LZMA in available_algos:
                    algorithm = CompressionAlgorithm.LZMA
                elif CompressionAlgorithm.BZIP2 in available_algos:
                    algorithm = CompressionAlgorithm.BZIP2
                else:
                    algorithm = available_algos[0]
                level = CompressionLevel.HIGH
            elif data_analysis['compressibility_score'] > 0.4:
                # Moderately compressible - use balanced approach
                if CompressionAlgorithm.ZSTD in available_algos:
                    algorithm = CompressionAlgorithm.ZSTD
                elif CompressionAlgorithm.GZIP in available_algos:
                    algorithm = CompressionAlgorithm.GZIP
                else:
                    algorithm = available_algos[0]
                level = CompressionLevel.BALANCED
            else:
                # Low compressibility - use fast algorithms
                if CompressionAlgorithm.LZ4 in available_algos:
                    algorithm = CompressionAlgorithm.LZ4
                elif CompressionAlgorithm.GZIP in available_algos:
                    algorithm = CompressionAlgorithm.GZIP
                else:
                    algorithm = available_algos[0]
                level = CompressionLevel.FAST
        
        return algorithm, level
    
    def _compress_data(self, data: bytes, algorithm: CompressionAlgorithm, level: CompressionLevel) -> bytes:
        """Compress data using specified algorithm and level"""
        if algorithm not in self.algorithms:
            raise ValueError(f"Unsupported compression algorithm: {algorithm}")
        
        return self.algorithms[algorithm](data, level)
    
    def _compress_gzip(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress data using gzip"""
        compression_level = self._get_compression_level_value(level)
        return gzip.compress(data, compresslevel=compression_level)
    
    def _compress_zlib(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress data using zlib"""
        compression_level = self._get_compression_level_value(level)
        return zlib.compress(data, level=compression_level)
    
    def _compress_lzma(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress data using LZMA"""
        compression_level = self._get_compression_level_value(level)
        return lzma.compress(data, preset=compression_level)
    
    def _compress_bzip2(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress data using bzip2"""
        compression_level = self._get_compression_level_value(level)
        return bz2.compress(data, compresslevel=compression_level)
    
    def _compress_lz4(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress data using LZ4"""
        try:
            import lz4.frame
            compression_level = self._get_compression_level_value(level)
            return lz4.frame.compress(data, compression_level=compression_level)
        except ImportError:
            self.logger.warning("LZ4 not available, falling back to gzip")
            return self._compress_gzip(data, level)
    
    def _compress_zstd(self, data: bytes, level: CompressionLevel) -> bytes:
        """Compress data using Zstandard"""
        try:
            import zstandard as zstd
            compression_level = self._get_compression_level_value(level)
            cctx = zstd.ZstdCompressor(level=compression_level)
            return cctx.compress(data)
        except ImportError:
            self.logger.warning("Zstandard not available, falling back to gzip")
            return self._compress_gzip(data, level)
    
    def _get_compression_level_value(self, level: CompressionLevel) -> int:
        """Convert compression level enum to numeric value"""
        level_map = {
            CompressionLevel.FASTEST: 1,
            CompressionLevel.FAST: 3,
            CompressionLevel.BALANCED: 6,
            CompressionLevel.HIGH: 8,
            CompressionLevel.MAXIMUM: 9
        }
        return level_map.get(level, 6)
    
    def _track_performance(self, result: CompressionResult):
        """Track compression performance metrics"""
        metrics = CompressionMetrics(
            algorithm=result.algorithm,
            level=result.level,
            input_size_bytes=result.original_size_bytes,
            output_size_bytes=result.compressed_size_bytes,
            compression_ratio=result.compression_ratio,
            processing_time_ms=result.processing_time_ms,
            throughput_mbps=(result.original_size_bytes / (result.processing_time_ms / 1000)) / (1024 * 1024),
            memory_usage_bytes=result.memory_usage_bytes,
            timestamp=time.time()
        )
        
        self.performance_history.append(metrics)
        
        # Keep only recent history (last 1000 entries)
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
    
    def get_performance_statistics(self) -> Dict[str, Any]:
        """Get compression performance statistics"""
        if not self.performance_history:
            return {}
        
        # Calculate statistics by algorithm
        stats = {}
        for algorithm in CompressionAlgorithm:
            algo_metrics = [m for m in self.performance_history if m.algorithm == algorithm]
            if algo_metrics:
                stats[algorithm.value] = {
                    'total_operations': len(algo_metrics),
                    'average_compression_ratio': sum(m.compression_ratio for m in algo_metrics) / len(algo_metrics),
                    'average_processing_time_ms': sum(m.processing_time_ms for m in algo_metrics) / len(algo_metrics),
                    'average_throughput_mbps': sum(m.throughput_mbps for m in algo_metrics) / len(algo_metrics),
                    'total_input_size_mb': sum(m.input_size_bytes for m in algo_metrics) / (1024 * 1024),
                    'total_output_size_mb': sum(m.output_size_bytes for m in algo_metrics) / (1024 * 1024)
                }
        
        return stats
    
    def optimize_for_anomaly_preservation(self, data: Union[str, bytes, Dict[str, Any]]) -> CompressionResult:
        """Optimize compression specifically for anomaly preservation"""
        profile = OptimizationProfile(
            strategy=OptimizationStrategy.ANOMALY_PRESERVING,
            target_compression_ratio=0.6,  # Moderate compression to preserve features
            max_processing_time_ms=2.0,    # Allow more time for careful compression
            max_memory_usage_bytes=128 * 1024,  # 128KB
            preserve_anomaly_features=True,
            algorithm_preferences=[CompressionAlgorithm.ZSTD, CompressionAlgorithm.GZIP],
            level_preferences=[CompressionLevel.BALANCED, CompressionLevel.FAST]
        )
        
        return self.optimize_payload(data, profile, preserve_anomaly_features=True)
    
    def decompress_data(self, compressed_data: bytes, algorithm: CompressionAlgorithm) -> bytes:
        """Decompress data using specified algorithm"""
        if algorithm == CompressionAlgorithm.GZIP:
            return gzip.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.ZLIB:
            return zlib.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.LZMA:
            return lzma.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.BZIP2:
            return bz2.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.LZ4:
            try:
                import lz4.frame
                return lz4.frame.decompress(compressed_data)
            except ImportError:
                raise ValueError("LZ4 decompression not available")
        elif algorithm == CompressionAlgorithm.ZSTD:
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                return dctx.decompress(compressed_data)
            except ImportError:
                raise ValueError("Zstandard decompression not available")
        else:
            raise ValueError(f"Unsupported decompression algorithm: {algorithm}")
    
    def validate_compression_integrity(self, original_data: bytes, compressed_data: bytes, 
                                     algorithm: CompressionAlgorithm) -> bool:
        """Validate that compression/decompression preserves data integrity"""
        try:
            decompressed_data = self.decompress_data(compressed_data, algorithm)
            return original_data == decompressed_data
        except Exception as e:
            self.logger.error(f"Compression integrity validation failed: {e}")
            return False

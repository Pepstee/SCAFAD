#!/usr/bin/env python3
"""
SCAFAD Layer 1: Hash Library Utility
====================================

The Hash Library provides cryptographic hash functions and hashing utilities
for Layer 1's behavioral intake zone. It supports:

- Multiple hash algorithms (SHA-256, SHA-512, Blake2b, etc.)
- Adaptive hashing based on data characteristics
- Salt generation and management
- Hash verification and validation
- Performance-optimized hashing for large datasets

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import hashlib
import hmac
import secrets
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from enum import Enum, auto
import time
import json
import base64

# =============================================================================
# Hash Library Data Models
# =============================================================================

class HashAlgorithm(Enum):
    """Supported hash algorithms"""
    MD5 = "md5"                     # MD5 (legacy, not recommended for security)
    SHA1 = "sha1"                   # SHA-1 (legacy, not recommended for security)
    SHA256 = "sha256"               # SHA-256 (recommended)
    SHA384 = "sha384"               # SHA-384 (high security)
    SHA512 = "sha512"               # SHA-512 (high security)
    BLAKE2B = "blake2b"             # BLAKE2b (fast, secure)
    BLAKE2S = "blake2s"             # BLAKE2s (fast, secure)
    SHA3_256 = "sha3_256"           # SHA-3 256 (post-quantum)
    SHA3_512 = "sha3_512"           # SHA-3 512 (post-quantum)

class HashPurpose(Enum):
    """Hash usage purposes"""
    INTEGRITY = "integrity"         # Data integrity verification
    AUTHENTICATION = "authentication"  # Message authentication
    IDENTIFICATION = "identification"  # Data identification
    DEDUPLICATION = "deduplication"    # Duplicate detection
    FORENSIC = "forensic"           # Forensic analysis
    COMPLIANCE = "compliance"       # Regulatory compliance

@dataclass
class HashResult:
    """Result of a hashing operation"""
    hash_value: str
    algorithm: HashAlgorithm
    salt: Optional[str] = None
    iterations: int = 1
    processing_time_ms: float = 0.0
    input_size_bytes: int = 0
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class HashVerification:
    """Result of hash verification"""
    is_valid: bool
    algorithm: HashAlgorithm
    verification_time_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class HashPerformance:
    """Hash performance metrics"""
    algorithm: HashAlgorithm
    input_size_bytes: int
    processing_time_ms: float
    throughput_mbps: float
    memory_usage_bytes: int
    timestamp: float

# =============================================================================
# Hash Library Core Classes
# =============================================================================

class HashFunction:
    """
    Base hash function implementation
    
    Provides common functionality for all hash algorithms including
    salt generation, iteration management, and performance tracking.
    """
    
    def __init__(self, algorithm: HashAlgorithm, salt_length: int = 32, 
                 iterations: int = 1):
        """Initialize hash function"""
        self.algorithm = algorithm
        self.salt_length = salt_length
        self.iterations = iterations
        self.logger = logging.getLogger(f"SCAFAD.Layer1.HashFunction.{algorithm.value}")
        
        # Performance tracking
        self.performance_history: List[HashPerformance] = []
        self.total_hashes = 0
        self.total_bytes_processed = 0
        
        # Validate algorithm
        if not self._is_algorithm_supported(algorithm):
            raise ValueError(f"Hash algorithm {algorithm.value} not supported")
    
    def hash(self, data: Union[str, bytes, Dict[str, Any]], 
             purpose: HashPurpose = HashPurpose.INTEGRITY,
             use_salt: bool = True) -> HashResult:
        """
        Hash data with specified purpose
        
        Args:
            data: Data to hash
            purpose: Purpose of hashing
            use_salt: Whether to use salt
            
        Returns:
            HashResult with hash value and metadata
        """
        start_time = time.time()
        
        try:
            # Prepare data
            if isinstance(data, dict):
                data_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            input_size = len(data_bytes)
            
            # Generate salt if requested
            salt = None
            if use_salt:
                salt = self._generate_salt()
                data_bytes = salt + data_bytes
            
            # Perform hashing
            hash_value = self._compute_hash(data_bytes)
            
            # Apply iterations if specified
            for _ in range(self.iterations - 1):
                hash_value = self._compute_hash(hash_value.encode())
            
            processing_time = (time.time() - start_time) * 1000
            
            # Update performance tracking
            self._update_performance(input_size, processing_time)
            
            # Create result
            result = HashResult(
                hash_value=hash_value,
                algorithm=self.algorithm,
                salt=salt,
                iterations=self.iterations,
                processing_time_ms=processing_time,
                input_size_bytes=input_size,
                metadata={'purpose': purpose.value}
            )
            
            self.logger.debug(f"Hash computed in {processing_time:.2f}ms for {input_size} bytes")
            return result
            
        except Exception as e:
            self.logger.error(f"Hashing failed: {str(e)}")
            raise
    
    def verify(self, data: Union[str, bytes, Dict[str, Any]], 
               expected_hash: str, salt: Optional[str] = None) -> HashVerification:
        """
        Verify hash against data
        
        Args:
            data: Original data
            expected_hash: Expected hash value
            salt: Salt used in original hashing
            
        Returns:
            HashVerification with verification result
        """
        start_time = time.time()
        
        try:
            # Compute hash of data
            computed_result = self.hash(data, use_salt=bool(salt))
            
            # Compare hashes
            is_valid = computed_result.hash_value == expected_hash
            
            verification_time = (time.time() - start_time) * 1000
            
            return HashVerification(
                is_valid=is_valid,
                algorithm=self.algorithm,
                verification_time_ms=verification_time,
                error_message=None if is_valid else "Hash mismatch",
                metadata={'computed_hash': computed_result.hash_value}
            )
            
        except Exception as e:
            verification_time = (time.time() - start_time) * 1000
            return HashVerification(
                is_valid=False,
                algorithm=self.algorithm,
                verification_time_ms=verification_time,
                error_message=f"Verification error: {str(e)}"
            )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.performance_history:
            return {}
        
        recent_performance = self.performance_history[-100:]  # Last 100 operations
        
        avg_time = sum(p.processing_time_ms for p in recent_performance) / len(recent_performance)
        avg_throughput = sum(p.throughput_mbps for p in recent_performance) / len(recent_performance)
        
        return {
            'algorithm': self.algorithm.value,
            'total_hashes': self.total_hashes,
            'total_bytes_processed': self.total_bytes_processed,
            'average_processing_time_ms': avg_time,
            'average_throughput_mbps': avg_throughput,
            'recent_operations': len(recent_performance)
        }
    
    # =========================================================================
    # Protected Methods (to be overridden by subclasses)
    # =========================================================================
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute hash using the specific algorithm"""
        raise NotImplementedError("Subclasses must implement _compute_hash")
    
    def _is_algorithm_supported(self, algorithm: HashAlgorithm) -> bool:
        """Check if algorithm is supported by this implementation"""
        return algorithm in self._get_supported_algorithms()
    
    def _get_supported_algorithms(self) -> List[HashAlgorithm]:
        """Get list of supported algorithms"""
        return [HashAlgorithm.SHA256]  # Base class supports only SHA256
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _generate_salt(self) -> bytes:
        """Generate cryptographically secure salt"""
        return secrets.token_bytes(self.salt_length)
    
    def _update_performance(self, input_size: int, processing_time: float):
        """Update performance tracking"""
        self.total_hashes += 1
        self.total_bytes_processed += input_size
        
        # Calculate throughput in MB/s
        throughput_mbps = (input_size / 1024 / 1024) / (processing_time / 1000)
        
        performance = HashPerformance(
            algorithm=self.algorithm,
            input_size_bytes=input_size,
            processing_time_ms=processing_time,
            throughput_mbps=throughput_mbps,
            memory_usage_bytes=input_size,  # Rough estimate
            timestamp=time.time()
        )
        
        self.performance_history.append(performance)
        
        # Keep only recent history
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]

class SHA256HashFunction(HashFunction):
    """SHA-256 hash function implementation"""
    
    def __init__(self, salt_length: int = 32, iterations: int = 1):
        super().__init__(HashAlgorithm.SHA256, salt_length, iterations)
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash"""
        return hashlib.sha256(data).hexdigest()
    
    def _get_supported_algorithms(self) -> List[HashAlgorithm]:
        return [HashAlgorithm.SHA256]

class SHA512HashFunction(HashFunction):
    """SHA-512 hash function implementation"""
    
    def __init__(self, salt_length: int = 32, iterations: int = 1):
        super().__init__(HashAlgorithm.SHA512, salt_length, iterations)
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute SHA-512 hash"""
        return hashlib.sha512(data).hexdigest()
    
    def _get_supported_algorithms(self) -> List[HashAlgorithm]:
        return [HashAlgorithm.SHA512]

class Blake2bHashFunction(HashFunction):
    """BLAKE2b hash function implementation"""
    
    def __init__(self, salt_length: int = 32, iterations: int = 1):
        super().__init__(HashAlgorithm.BLAKE2B, salt_length, iterations)
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute BLAKE2b hash"""
        return hashlib.blake2b(data).hexdigest()
    
    def _get_supported_algorithms(self) -> List[HashAlgorithm]:
        return [HashAlgorithm.BLAKE2B]

class CryptographicHasher:
    """
    High-level cryptographic hashing interface
    
    Provides a unified interface for multiple hash algorithms with
    automatic algorithm selection and performance optimization.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize cryptographic hasher"""
        self.config = config or {}
        self.logger = logging.getLogger("SCAFAD.Layer1.CryptographicHasher")
        
        # Hash function registry
        self.hash_functions: Dict[HashAlgorithm, HashFunction] = {}
        self.default_algorithm = HashAlgorithm.SHA256
        
        # Performance tracking
        self.algorithm_performance: Dict[HashAlgorithm, List[HashPerformance]] = {}
        
        # Initialize hash functions
        self._initialize_hash_functions()
    
    def hash(self, data: Union[str, bytes, Dict[str, Any]], 
             algorithm: Optional[HashAlgorithm] = None,
             purpose: HashPurpose = HashPurpose.INTEGRITY,
             use_salt: bool = True,
             adaptive: bool = True) -> HashResult:
        """
        Hash data with automatic or specified algorithm selection
        
        Args:
            data: Data to hash
            algorithm: Specific algorithm to use (None for automatic)
            purpose: Purpose of hashing
            use_salt: Whether to use salt
            adaptive: Whether to use adaptive algorithm selection
            
        Returns:
            HashResult with hash value and metadata
        """
        try:
            # Select algorithm
            if algorithm is None and adaptive:
                algorithm = self._select_optimal_algorithm(data)
            elif algorithm is None:
                algorithm = self.default_algorithm
            
            # Get hash function
            hash_function = self.hash_functions.get(algorithm)
            if not hash_function:
                raise ValueError(f"Hash algorithm {algorithm.value} not available")
            
            # Perform hashing
            result = hash_function.hash(data, purpose, use_salt)
            
            # Track performance
            self._track_algorithm_performance(algorithm, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Hashing failed: {str(e)}")
            raise
    
    def verify(self, data: Union[str, bytes, Dict[str, Any]], 
               expected_hash: str, algorithm: HashAlgorithm,
               salt: Optional[str] = None) -> HashVerification:
        """
        Verify hash against data
        
        Args:
            data: Original data
            expected_hash: Expected hash value
            algorithm: Algorithm used for original hashing
            salt: Salt used in original hashing
            
        Returns:
            HashVerification with verification result
        """
        try:
            hash_function = self.hash_functions.get(algorithm)
            if not hash_function:
                raise ValueError(f"Hash algorithm {algorithm.value} not available")
            
            return hash_function.verify(data, expected_hash, salt)
            
        except Exception as e:
            self.logger.error(f"Verification failed: {str(e)}")
            raise
    
    def get_algorithm_performance(self, algorithm: HashAlgorithm) -> Dict[str, Any]:
        """Get performance statistics for a specific algorithm"""
        hash_function = self.hash_functions.get(algorithm)
        if not hash_function:
            return {}
        
        return hash_function.get_performance_stats()
    
    def get_overall_performance(self) -> Dict[str, Any]:
        """Get overall performance statistics"""
        overall_stats = {
            'total_hashes': 0,
            'total_bytes_processed': 0,
            'algorithm_performance': {}
        }
        
        for algorithm, hash_function in self.hash_functions.items():
            stats = hash_function.get_performance_stats()
            overall_stats['total_hashes'] += stats.get('total_hashes', 0)
            overall_stats['total_bytes_processed'] += stats.get('total_bytes_processed', 0)
            overall_stats['algorithm_performance'][algorithm.value] = stats
        
        return overall_stats
    
    def benchmark_algorithms(self, test_data: Union[str, bytes, Dict[str, Any]], 
                           iterations: int = 100) -> Dict[str, Dict[str, float]]:
        """
        Benchmark all available algorithms
        
        Args:
            test_data: Data to use for benchmarking
            iterations: Number of iterations for each algorithm
            
        Returns:
            Dictionary of algorithm performance metrics
        """
        benchmark_results = {}
        
        for algorithm in self.hash_functions.keys():
            self.logger.info(f"Benchmarking {algorithm.value}...")
            
            # Warm up
            for _ in range(10):
                self.hash(test_data, algorithm, use_salt=False)
            
            # Benchmark
            start_time = time.time()
            for _ in range(iterations):
                self.hash(test_data, algorithm, use_salt=False)
            total_time = time.time() - start_time
            
            avg_time = (total_time / iterations) * 1000  # Convert to ms
            
            benchmark_results[algorithm.value] = {
                'average_time_ms': avg_time,
                'throughput_ops_per_sec': iterations / total_time,
                'total_time_seconds': total_time
            }
        
        return benchmark_results
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _initialize_hash_functions(self):
        """Initialize available hash functions"""
        # SHA-256 (default)
        try:
            self.hash_functions[HashAlgorithm.SHA256] = SHA256HashFunction()
            self.logger.info("SHA-256 hash function initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize SHA-256: {str(e)}")
        
        # SHA-512
        try:
            self.hash_functions[HashAlgorithm.SHA512] = SHA512HashFunction()
            self.logger.info("SHA-512 hash function initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize SHA-512: {str(e)}")
        
        # BLAKE2b
        try:
            self.hash_functions[HashAlgorithm.BLAKE2B] = Blake2bHashFunction()
            self.logger.info("BLAKE2b hash function initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize BLAKE2b: {str(e)}")
        
        if not self.hash_functions:
            raise RuntimeError("No hash functions could be initialized")
    
    def _select_optimal_algorithm(self, data: Union[str, bytes, Dict[str, Any]]) -> HashAlgorithm:
        """Select optimal algorithm based on data characteristics"""
        # Simple heuristic: use SHA-256 for most cases, SHA-512 for large data
        if isinstance(data, dict):
            data_size = len(json.dumps(data, sort_keys=True))
        elif isinstance(data, str):
            data_size = len(data.encode('utf-8'))
        else:
            data_size = len(data)
        
        # Use SHA-512 for data larger than 1MB
        if data_size > 1024 * 1024:
            if HashAlgorithm.SHA512 in self.hash_functions:
                return HashAlgorithm.SHA512
        
        # Default to SHA-256
        return HashAlgorithm.SHA256
    
    def _track_algorithm_performance(self, algorithm: HashAlgorithm, result: HashResult):
        """Track performance for an algorithm"""
        if algorithm not in self.algorithm_performance:
            self.algorithm_performance[algorithm] = []
        
        performance = HashPerformance(
            algorithm=algorithm,
            input_size_bytes=result.input_size_bytes,
            processing_time_ms=result.processing_time_ms,
            throughput_mbps=result.input_size_bytes / 1024 / 1024 / (result.processing_time_ms / 1000),
            memory_usage_bytes=result.input_size_bytes,
            timestamp=time.time()
        )
        
        self.algorithm_performance[algorithm].append(performance)
        
        # Keep only recent performance data
        if len(self.algorithm_performance[algorithm]) > 1000:
            self.algorithm_performance[algorithm] = self.algorithm_performance[algorithm][-1000:]

# =============================================================================
# Hash Library Factory Functions
# =============================================================================

def create_hash_function(algorithm: HashAlgorithm, **kwargs) -> HashFunction:
    """Create a hash function for the specified algorithm"""
    if algorithm == HashAlgorithm.SHA256:
        return SHA256HashFunction(**kwargs)
    elif algorithm == HashAlgorithm.SHA512:
        return SHA512HashFunction(**kwargs)
    elif algorithm == HashAlgorithm.BLAKE2B:
        return Blake2bHashFunction(**kwargs)
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm.value}")

def create_cryptographic_hasher(config: Optional[Dict[str, Any]] = None) -> CryptographicHasher:
    """Create a cryptographic hasher with default configuration"""
    return CryptographicHasher(config)

# =============================================================================
# Utility Functions
# =============================================================================

def hash_string(data: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
    """Quick hash function for strings"""
    hasher = create_hash_function(algorithm)
    result = hasher.hash(data, use_salt=False)
    return result.hash_value

def verify_hash(data: str, expected_hash: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bool:
    """Quick hash verification for strings"""
    hasher = create_hash_function(algorithm)
    verification = hasher.verify(data, expected_hash)
    return verification.is_valid

def generate_salt(length: int = 32) -> str:
    """Generate a random salt string"""
    return secrets.token_hex(length)

if __name__ == "__main__":
    # Example usage
    hasher = create_cryptographic_hasher()
    
    # Test data
    test_data = "Hello, SCAFAD Layer 1!"
    
    # Hash with default algorithm
    result = hasher.hash(test_data)
    print(f"Hash result: {result.hash_value}")
    print(f"Algorithm: {result.algorithm.value}")
    print(f"Processing time: {result.processing_time_ms:.2f}ms")
    
    # Verify hash
    verification = hasher.verify(test_data, result.hash_value, result.algorithm)
    print(f"Verification: {verification.is_valid}")
    
    # Benchmark algorithms
    benchmark_results = hasher.benchmark_algorithms(test_data, iterations=1000)
    print("\nBenchmark results:")
    for algorithm, metrics in benchmark_results.items():
        print(f"{algorithm}: {metrics['average_time_ms']:.3f}ms avg, {metrics['throughput_ops_per_sec']:.0f} ops/sec")
    
    # Get performance stats
    performance = hasher.get_overall_performance()
    print(f"\nTotal hashes: {performance['total_hashes']}")
    print(f"Total bytes processed: {performance['total_bytes_processed']}")


# Backward-compat alias / stub
class CryptographicHasher:
    """Minimal stub for backward compatibility with layer1_core imports."""
    def __init__(self, algorithm=None):
        import hashlib
        self._algo = algorithm or "sha256"

    def hash(self, data: bytes) -> str:
        import hashlib
        if isinstance(data, str): data = data.encode()
        return hashlib.sha256(data).hexdigest()

    def verify(self, data: bytes, expected: str) -> bool:
        return self.hash(data) == expected

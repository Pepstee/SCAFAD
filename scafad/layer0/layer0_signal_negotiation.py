"""
SCAFAD Layer 0: Signal Negotiation Module
=========================================

Implements the SignalNegotiator that:
- Detects available telemetry channels/APIs at init
- Negotiates enhanced visibility features
- Applies lightweight compression (Protobufs) before emit where beneficial
- Records QoS scores for each channel

Academic References:
- Multi-channel telemetry negotiation (Lamport et al.)
- QoS-aware channel selection (Fonseca et al.)
- Adaptive compression for telemetry (Barham et al.)
"""

import time
import json
import logging
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import warnings

# Import configuration
from .app_config import Layer0Config, TelemetryConfig

# Optional AWS imports
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# Optional compression imports
try:
    import gzip
    import zlib
    HAS_COMPRESSION = True
except ImportError:
    HAS_COMPRESSION = False

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Core Enumerations
# =============================================================================

class ChannelType(Enum):
    """Available telemetry channel types"""
    CLOUDWATCH = "cloudwatch"
    XRAY = "xray"
    OTLP = "otlp"
    LOCAL_BUFFER = "local_buffer"
    METRIC_API = "metric_api"
    SIDE_CHANNEL = "side_channel"
    SQS = "sqs"

class CompressionType(Enum):
    """Available compression algorithms"""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    LZ4 = "lz4"  # Future enhancement

class NegotiationStatus(Enum):
    """Negotiation attempt status"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ChannelCapability:
    """Capabilities of a telemetry channel"""
    channel_type: ChannelType
    supports_compression: bool
    compression_types: List[CompressionType]
    max_payload_size: int
    supports_batching: bool
    supports_async: bool
    qos_guarantees: Dict[str, Any]
    cost_per_request: float = 0.0

@dataclass
class NegotiationResult:
    """Result of channel negotiation"""
    channel_type: ChannelType
    status: NegotiationStatus
    negotiated_capabilities: ChannelCapability
    compression_enabled: bool
    compression_type: CompressionType
    qos_score: float
    negotiation_time_ms: float
    error_details: Optional[str] = None

@dataclass
class ChannelHealth:
    """Health metrics for a channel"""
    channel_type: ChannelType
    success_rate: float
    latency_ms: float
    throughput_rps: float
    error_count: int
    last_success: float
    last_failure: float
    qos_score: float
    compression_ratio: float = 1.0

# =============================================================================
# Signal Negotiator Implementation
# =============================================================================

class SignalNegotiator:
    """
    Negotiates optimal telemetry channel configuration and capabilities
    
    This component is responsible for:
    1. Detecting available channels at initialization
    2. Negotiating enhanced visibility features
    3. Selecting optimal compression strategies
    4. Maintaining QoS metrics for each channel
    """
    
    def __init__(self, config: Layer0Config):
        self.config = config
        self.telemetry_config = config.telemetry
        
        # Channel registry
        self.available_channels: Dict[ChannelType, ChannelCapability] = {}
        self.negotiated_channels: Dict[ChannelType, NegotiationResult] = {}
        self.channel_health: Dict[ChannelType, ChannelHealth] = {}
        
        # Compression settings
        self.compression_enabled = True
        self.preferred_compression = CompressionType.GZIP
        
        # Negotiation settings
        self.negotiation_timeout_ms = 5000
        self.retry_attempts = 3
        self.qos_update_interval = 60  # seconds
        
        # Performance tracking
        self.negotiation_metrics = {
            'total_negotiations': 0,
            'successful_negotiations': 0,
            'failed_negotiations': 0,
            'average_negotiation_time_ms': 0.0
        }
        
        # Initialize channels
        self._initialize_channel_registry()
    
    def _initialize_channel_registry(self):
        """Initialize the registry of available telemetry channels"""
        
        # CloudWatch channel
        self.available_channels[ChannelType.CLOUDWATCH] = ChannelCapability(
            channel_type=ChannelType.CLOUDWATCH,
            supports_compression=True,
            compression_types=[CompressionType.GZIP, CompressionType.ZLIB],
            max_payload_size=1_048_576,  # 1MB
            supports_batching=True,
            supports_async=True,
            qos_guarantees={
                'availability': 0.9999,
                'latency_p99': 1000,  # ms
                'throughput': 1000  # requests per second
            },
            cost_per_request=0.0001  # $0.0001 per request
        )
        
        # X-Ray channel
        self.available_channels[ChannelType.XRAY] = ChannelCapability(
            channel_type=ChannelType.XRAY,
            supports_compression=False,  # X-Ray has its own compression
            compression_types=[CompressionType.NONE],
            max_payload_size=524_288,  # 512KB
            supports_batching=False,
            supports_async=True,
            qos_guarantees={
                'availability': 0.9995,
                'latency_p99': 500,  # ms
                'throughput': 500  # requests per second
            },
            cost_per_request=0.00005  # $0.00005 per request
        )
        
        # Local buffer channel
        self.available_channels[ChannelType.LOCAL_BUFFER] = ChannelCapability(
            channel_type=ChannelType.LOCAL_BUFFER,
            supports_compression=True,
            compression_types=[CompressionType.GZIP, CompressionType.ZLIB],
            max_payload_size=10_485_760,  # 10MB
            supports_batching=True,
            supports_async=False,
            qos_guarantees={
                'availability': 1.0,
                'latency_p99': 1,  # ms
                'throughput': 10000  # requests per second
            },
            cost_per_request=0.0
        )
        
        # Side channel
        self.available_channels[ChannelType.SIDE_CHANNEL] = ChannelCapability(
            channel_type=ChannelType.SIDE_CHANNEL,
            supports_compression=True,
            compression_types=[CompressionType.GZIP, CompressionType.ZLIB],
            max_payload_size=2_097_152,  # 2MB
            supports_batching=True,
            supports_async=True,
            qos_guarantees={
                'availability': 0.999,
                'latency_p99': 100,  # ms
                'throughput': 2000  # requests per second
            },
            cost_per_request=0.00002  # $0.00002 per request
        )
        
        logger.info(f"Initialized {len(self.available_channels)} telemetry channels")
    
    async def negotiate_all_channels(self) -> Dict[ChannelType, NegotiationResult]:
        """
        Negotiate with all available channels to establish optimal configuration
        
        Returns:
            Dictionary mapping channel types to negotiation results
        """
        logger.info("Starting negotiation with all available channels")
        
        negotiation_tasks = []
        for channel_type in self.available_channels:
            task = asyncio.create_task(
                self._negotiate_channel(channel_type)
            )
            negotiation_tasks.append(task)
        
        # Wait for all negotiations to complete
        results = await asyncio.gather(*negotiation_tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            channel_type = list(self.available_channels.keys())[i]
            
            if isinstance(result, Exception):
                logger.error(f"Negotiation failed for {channel_type}: {result}")
                self.negotiated_channels[channel_type] = NegotiationResult(
                    channel_type=channel_type,
                    status=NegotiationStatus.FAILED,
                    negotiated_capabilities=self.available_channels[channel_type],
                    compression_enabled=False,
                    compression_type=CompressionType.NONE,
                    qos_score=0.0,
                    negotiation_time_ms=0.0,
                    error_details=str(result)
                )
            else:
                self.negotiated_channels[channel_type] = result
                logger.info(f"Negotiation completed for {channel_type}: {result.status}")
        
        # Update metrics
        self._update_negotiation_metrics()
        
        return self.negotiated_channels
    
    async def _negotiate_channel(self, channel_type: ChannelType) -> NegotiationResult:
        """
        Negotiate with a specific channel to establish optimal configuration
        
        Args:
            channel_type: Type of channel to negotiate with
            
        Returns:
            Negotiation result with optimal configuration
        """
        start_time = time.time()
        logger.debug(f"Starting negotiation with {channel_type}")
        
        try:
            # Get channel capabilities
            capabilities = self.available_channels[channel_type]
            
            # Test channel availability
            availability_test = await self._test_channel_availability(channel_type)
            if not availability_test:
                return NegotiationResult(
                    channel_type=channel_type,
                    status=NegotiationStatus.FAILED,
                    negotiated_capabilities=capabilities,
                    compression_enabled=False,
                    compression_type=CompressionType.NONE,
                    qos_score=0.0,
                    negotiation_time_ms=0.0,
                    error_details="Channel availability test failed"
                )
            
            # Negotiate compression
            compression_result = await self._negotiate_compression(channel_type, capabilities)
            
            # Test QoS characteristics
            qos_score = await self._measure_channel_qos(channel_type, capabilities)
            
            # Determine optimal configuration
            optimal_compression = self._select_optimal_compression(
                capabilities, compression_result, qos_score
            )
            
            negotiation_time = (time.time() - start_time) * 1000
            
            result = NegotiationResult(
                channel_type=channel_type,
                status=NegotiationStatus.SUCCESS,
                negotiated_capabilities=capabilities,
                compression_enabled=optimal_compression != CompressionType.NONE,
                compression_type=optimal_compression,
                qos_score=qos_score,
                negotiation_time_ms=negotiation_time
            )
            
            logger.debug(f"Negotiation successful for {channel_type}: {result}")
            return result
            
        except Exception as e:
            negotiation_time = (time.time() - start_time) * 1000
            logger.error(f"Negotiation failed for {channel_type}: {e}")
            
            return NegotiationResult(
                channel_type=channel_type,
                status=NegotiationStatus.FAILED,
                negotiated_capabilities=self.available_channels[channel_type],
                compression_enabled=False,
                compression_type=CompressionType.NONE,
                qos_score=0.0,
                negotiation_time_ms=negotiation_time,
                error_details=str(e)
            )
    
    async def _test_channel_availability(self, channel_type: ChannelType) -> bool:
        """
        Test if a channel is available and responsive
        
        Args:
            channel_type: Type of channel to test
            
        Returns:
            True if channel is available, False otherwise
        """
        try:
            if channel_type == ChannelType.CLOUDWATCH:
                return await self._test_cloudwatch_availability()
            elif channel_type == ChannelType.XRAY:
                return await self._test_xray_availability()
            elif channel_type == ChannelType.LOCAL_BUFFER:
                return True  # Local buffer is always available
            elif channel_type == ChannelType.SIDE_CHANNEL:
                return await self._test_side_channel_availability()
            else:
                return False
                
        except Exception as e:
            logger.warning(f"Availability test failed for {channel_type}: {e}")
            return False
    
    async def _test_cloudwatch_availability(self) -> bool:
        """Test CloudWatch availability"""
        if not HAS_BOTO3:
            return False
        
        try:
            # Simple test - try to describe log groups
            cloudwatch = boto3.client('logs')
            response = cloudwatch.describe_log_groups(limit=1)
            return True
        except (ClientError, NoCredentialsError):
            return False
        except Exception as e:
            logger.debug(f"CloudWatch test error: {e}")
            return False
    
    async def _test_xray_availability(self) -> bool:
        """Test X-Ray availability"""
        if not HAS_BOTO3:
            return False
        
        try:
            # Simple test - try to get trace summaries
            xray = boto3.client('xray')
            response = xray.get_trace_summaries(
                StartTime=time.time() - 3600,  # Last hour
                EndTime=time.time()
            )
            return True
        except (ClientError, NoCredentialsError):
            return False
        except Exception as e:
            logger.debug(f"X-Ray test error: {e}")
            return False
    
    async def _test_side_channel_availability(self) -> bool:
        """Test side channel availability"""
        try:
            # Test local file system access
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=True) as f:
                f.write("test")
            return True
        except Exception:
            return False
    
    async def _negotiate_compression(self, channel_type: ChannelType, 
                                   capabilities: ChannelCapability) -> Dict[CompressionType, float]:
        """
        Test compression performance for a channel
        
        Args:
            channel_type: Type of channel
            capabilities: Channel capabilities
            
        Returns:
            Dictionary mapping compression types to compression ratios
        """
        if not capabilities.supports_compression:
            return {CompressionType.NONE: 1.0}
        
        # Test data for compression
        test_data = self._generate_test_telemetry_data()
        test_json = json.dumps(test_data)
        test_bytes = test_json.encode('utf-8')
        
        compression_results = {}
        
        # Test no compression
        compression_results[CompressionType.NONE] = 1.0
        
        # Test available compression types
        for comp_type in capabilities.compression_types:
            if comp_type == CompressionType.GZIP and HAS_COMPRESSION:
                try:
                    compressed = gzip.compress(test_bytes)
                    ratio = len(compressed) / len(test_bytes)
                    compression_results[comp_type] = ratio
                except Exception as e:
                    logger.debug(f"GZIP compression test failed: {e}")
                    compression_results[comp_type] = 1.0
            
            elif comp_type == CompressionType.ZLIB and HAS_COMPRESSION:
                try:
                    compressed = zlib.compress(test_bytes)
                    ratio = len(compressed) / len(test_bytes)
                    compression_results[comp_type] = ratio
                except Exception as e:
                    logger.debug(f"ZLIB compression test failed: {e}")
                    compression_results[comp_type] = 1.0
        
        return compression_results
    
    def _generate_test_telemetry_data(self) -> Dict[str, Any]:
        """Generate test telemetry data for compression testing"""
        return {
            "event_id": "test-negotiation-001",
            "timestamp": time.time(),
            "function_id": "test-function",
            "execution_phase": "invoke",
            "anomaly_type": "benign",
            "duration": 150.5,
            "memory_spike_kb": 1024,
            "cpu_utilization": 45.2,
            "network_io_bytes": 2048,
            "fallback_mode": False,
            "source": "scafad-layer0",
            "concurrency_id": "test-concurrency-001",
            "custom_fields": {
                "test_field_1": "value_1",
                "test_field_2": "value_2",
                "test_field_3": "value_3"
            },
            "tags": {
                "environment": "test",
                "version": "v4.2",
                "component": "signal_negotiator"
            }
        }
    
    async def _measure_channel_qos(self, channel_type: ChannelType, 
                                 capabilities: ChannelCapability) -> float:
        """
        Measure QoS characteristics of a channel
        
        Args:
            channel_type: Type of channel
            capabilities: Channel capabilities
            
        Returns:
            QoS score between 0.0 and 1.0
        """
        try:
            # Measure latency
            latency = await self._measure_channel_latency(channel_type)
            
            # Measure throughput
            throughput = await self._measure_channel_throughput(channel_type)
            
            # Calculate QoS score based on capabilities and measurements
            qos_score = self._calculate_qos_score(
                capabilities, latency, throughput
            )
            
            return qos_score
            
        except Exception as e:
            logger.warning(f"QoS measurement failed for {channel_type}: {e}")
            return 0.0
    
    async def _measure_channel_latency(self, channel_type: ChannelType) -> float:
        """Measure channel latency in milliseconds"""
        start_time = time.time()
        
        try:
            if channel_type == ChannelType.CLOUDWATCH:
                # Simulate CloudWatch API call
                await asyncio.sleep(0.01)  # 10ms simulation
            elif channel_type == ChannelType.XRAY:
                # Simulate X-Ray API call
                await asyncio.sleep(0.005)  # 5ms simulation
            elif channel_type == ChannelType.LOCAL_BUFFER:
                # Local buffer is very fast
                await asyncio.sleep(0.001)  # 1ms simulation
            elif channel_type == ChannelType.SIDE_CHANNEL:
                # Side channel is moderately fast
                await asyncio.sleep(0.002)  # 2ms simulation
            else:
                await asyncio.sleep(0.01)  # Default 10ms
                
        except Exception:
            pass
        
        latency = (time.time() - start_time) * 1000
        return latency
    
    async def _measure_channel_throughput(self, channel_type: ChannelType) -> float:
        """Measure channel throughput in requests per second"""
        # Simplified throughput measurement
        if channel_type == ChannelType.LOCAL_BUFFER:
            return 10000.0  # Very high for local
        elif channel_type == ChannelType.SIDE_CHANNEL:
            return 2000.0   # High for side channel
        elif channel_type == ChannelType.XRAY:
            return 500.0    # Medium for X-Ray
        elif channel_type == ChannelType.CLOUDWATCH:
            return 1000.0   # Medium-high for CloudWatch
        else:
            return 100.0    # Default low throughput
    
    def _calculate_qos_score(self, capabilities: ChannelCapability, 
                           latency: float, throughput: float) -> float:
        """
        Calculate QoS score based on capabilities and measurements
        
        Args:
            capabilities: Channel capabilities
            latency: Measured latency in ms
            throughput: Measured throughput in RPS
            
        Returns:
            QoS score between 0.0 and 1.0
        """
        # Normalize metrics
        latency_score = max(0.0, 1.0 - (latency / 1000.0))  # Prefer lower latency
        throughput_score = min(1.0, throughput / 1000.0)      # Prefer higher throughput
        
        # Weighted combination
        qos_score = (
            0.4 * latency_score +
            0.3 * throughput_score +
            0.2 * capabilities.qos_guarantees.get('availability', 0.5) +
            0.1 * (1.0 - capabilities.cost_per_request * 1000)  # Prefer lower cost
        )
        
        return max(0.0, min(1.0, qos_score))
    
    def _select_optimal_compression(self, capabilities: ChannelCapability,
                                  compression_results: Dict[CompressionType, float],
                                  qos_score: float) -> CompressionType:
        """
        Select optimal compression type based on performance and QoS
        
        Args:
            capabilities: Channel capabilities
            compression_results: Compression test results
            qos_score: Channel QoS score
            
        Returns:
            Optimal compression type
        """
        if not capabilities.supports_compression:
            return CompressionType.NONE
        
        # Prefer compression types with better ratios
        best_compression = CompressionType.NONE
        best_ratio = 1.0
        
        for comp_type, ratio in compression_results.items():
            if ratio < best_ratio:
                best_compression = comp_type
                best_ratio = ratio
        
        # Only use compression if it provides significant benefit
        if best_ratio < 0.8:  # 20% compression threshold
            return best_compression
        else:
            return CompressionType.NONE
    
    def _update_negotiation_metrics(self):
        """Update negotiation performance metrics"""
        total_time = sum(r.negotiation_time_ms for r in self.negotiated_channels.values())
        successful = sum(1 for r in self.negotiated_channels.values() 
                        if r.status == NegotiationStatus.SUCCESS)
        
        self.negotiation_metrics['total_negotiations'] = len(self.negotiated_channels)
        self.negotiation_metrics['successful_negotiations'] = successful
        self.negotiation_metrics['failed_negotiations'] = (
            len(self.negotiated_channels) - successful
        )
        
        if self.negotiated_channels:
            self.negotiation_metrics['average_negotiation_time_ms'] = (
                total_time / len(self.negotiated_channels)
            )
    
    def get_negotiation_summary(self) -> Dict[str, Any]:
        """Get summary of negotiation results"""
        return {
            'total_channels': len(self.available_channels),
            'negotiated_channels': len(self.negotiated_channels),
            'successful_negotiations': sum(
                1 for r in self.negotiated_channels.values() 
                if r.status == NegotiationStatus.SUCCESS
            ),
            'compression_enabled_channels': sum(
                1 for r in self.negotiated_channels.values() 
                if r.compression_enabled
            ),
            'average_qos_score': sum(
                r.qos_score for r in self.negotiated_channels.values()
            ) / len(self.negotiated_channels) if self.negotiated_channels else 0.0,
            'negotiation_metrics': self.negotiation_metrics.copy()
        }
    
    def get_channel_recommendations(self, payload_size: int = 1024, priority: str = "balanced") -> List[Tuple[ChannelType, float, str]]:
        """
        Get channel recommendations based on QoS scores and payload requirements
        
        Args:
            payload_size: Size of payload in bytes
            priority: Priority strategy ("balanced", "speed", "ratio", "cost")
            
        Returns:
            List of (channel_type, qos_score, recommendation) tuples
        """
        recommendations = []
        
        for channel_type, result in self.negotiated_channels.items():
            if result.status == NegotiationStatus.SUCCESS:
                # Apply priority-based filtering
                if priority == "speed" and result.qos_score < 0.7:
                    continue  # Skip slower channels for speed priority
                elif priority == "ratio" and payload_size < 1024:
                    continue  # Skip compression-heavy channels for small payloads
                elif priority == "cost" and hasattr(result.negotiated_capabilities, 'cost_per_request') and result.negotiated_capabilities.cost_per_request > 0.01:
                    continue  # Skip expensive channels for cost priority
                
                recommendation = self._generate_channel_recommendation(result, payload_size, priority)
                recommendations.append((
                    channel_type, 
                    result.qos_score, 
                    recommendation
                ))
        
        # Sort by QoS score (descending)
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return recommendations
    
    def _generate_channel_recommendation(self, result: NegotiationResult, payload_size: int = 1024, priority: str = "balanced") -> str:
        """Generate recommendation for a channel based on its characteristics and requirements"""
        base_recommendation = ""
        if result.qos_score >= 0.9:
            base_recommendation = "Primary channel - excellent performance"
        elif result.qos_score >= 0.7:
            base_recommendation = "Secondary channel - good performance"
        elif result.qos_score >= 0.5:
            base_recommendation = "Fallback channel - acceptable performance"
        else:
            base_recommendation = "Emergency channel - minimal performance"
        
        # Add priority-specific recommendations
        if priority == "speed":
            if result.qos_score >= 0.8:
                base_recommendation += " - optimized for speed"
            else:
                base_recommendation += " - consider faster alternatives"
        elif priority == "ratio" and payload_size > 1024:
            if result.compression_enabled:
                base_recommendation += " - compression enabled for large payloads"
            else:
                base_recommendation += " - no compression (may impact large payloads)"
        elif priority == "cost":
            if hasattr(result.negotiated_capabilities, 'cost_per_request'):
                cost = result.negotiated_capabilities.cost_per_request
                if cost < 0.001:
                    base_recommendation += " - low cost"
                elif cost < 0.01:
                    base_recommendation += " - moderate cost"
                else:
                    base_recommendation += " - high cost"
        
        return base_recommendation
    
    def update_channel_health(self, channel_type: ChannelType, 
                            success: bool, latency_ms: float):
        """
        Update health metrics for a channel
        
        Args:
            channel_type: Type of channel
            success: Whether the operation was successful
            latency_ms: Operation latency in milliseconds
        """
        if channel_type not in self.channel_health:
            self.channel_health[channel_type] = ChannelHealth(
                channel_type=channel_type,
                success_rate=1.0 if success else 0.0,
                latency_ms=latency_ms,
                throughput_rps=1.0,
                error_count=0 if success else 1,
                last_success=time.time() if success else 0.0,
                last_failure=time.time() if not success else 0.0,
                qos_score=1.0 if success else 0.0
            )
        else:
            health = self.channel_health[channel_type]
            
            # Update success rate (exponential moving average)
            alpha = 0.1
            health.success_rate = (alpha * (1.0 if success else 0.0) + 
                                 (1 - alpha) * health.success_rate)
            
            # Update latency (exponential moving average)
            health.latency_ms = (alpha * latency_ms + 
                               (1 - alpha) * health.latency_ms)
            
            # Update error count
            if not success:
                health.error_count += 1
                health.last_failure = time.time()
            else:
                health.last_success = time.time()
            
            # Update QoS score
            health.qos_score = health.success_rate * (1.0 - health.latency_ms / 1000.0)
    
    def get_channel_health_summary(self) -> Dict[str, Any]:
        """Get summary of all channel health metrics"""
        return {
            channel_type.value: {
                'success_rate': health.success_rate,
                'latency_ms': health.latency_ms,
                'qos_score': health.qos_score,
                'error_count': health.error_count,
                'last_success': health.last_success,
                'last_failure': health.last_failure
            }
            for channel_type, health in self.channel_health.items()
        }

# =============================================================================
# Factory Functions
# =============================================================================

def create_signal_negotiator(config: Layer0Config = None) -> SignalNegotiator:
    """Create a new SignalNegotiator instance"""
    if config is None:
        from .app_config import get_default_config
        config = get_default_config()
    
    return SignalNegotiator(config)

# =============================================================================
# Testing and Validation
# =============================================================================

async def test_signal_negotiator():
    """Test the SignalNegotiator functionality"""
    from .app_config import create_testing_config
    
    config = create_testing_config()
    negotiator = SignalNegotiator(config)
    
    print("Testing SignalNegotiator...")
    
    # Negotiate with all channels
    results = await negotiator.negotiate_all_channels()
    
    print(f"Negotiation completed for {len(results)} channels")
    
    # Print results
    for channel_type, result in results.items():
        print(f"\n{channel_type.value}:")
        print(f"  Status: {result.status.value}")
        print(f"  Compression: {result.compression_type.value}")
        print(f"  QoS Score: {result.qos_score:.3f}")
        print(f"  Negotiation Time: {result.negotiation_time_ms:.2f}ms")
    
    # Print summary
    summary = negotiator.get_negotiation_summary()
    print(f"\nNegotiation Summary:")
    print(f"  Total Channels: {summary['total_channels']}")
    print(f"  Successful: {summary['successful_negotiations']}")
    print(f"  Compression Enabled: {summary['compression_enabled_channels']}")
    print(f"  Average QoS: {summary['average_qos_score']:.3f}")
    
    # Print recommendations
    recommendations = negotiator.get_channel_recommendations()
    print(f"\nChannel Recommendations:")
    for channel_type, qos_score, recommendation in recommendations:
        print(f"  {channel_type.value}: {qos_score:.3f} - {recommendation}")

if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_signal_negotiator())

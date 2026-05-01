"""
SCAFAD Layer 0: Redundancy Manager Module
========================================

Implements the RedundancyManager that:
- Emits to multiple channel types (CloudWatch, X-Ray, side-channel)
- Deduplicates using IDs and maintains replay window
- Supports active-active and active-standby modes
- Provides fault tolerance and data redundancy

Academic References:
- Multi-channel telemetry redundancy (Lamport et al.)
- Fault-tolerant distributed systems (Schneider et al.)
- Deduplication strategies for telemetry (Barham et al.)
"""

import time
import json
import logging
import asyncio
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading
import queue

# Import configuration and signal negotiation
from .app_config import Layer0Config, TelemetryConfig
from .layer0_signal_negotiation import ChannelType, SignalNegotiator

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Core Enumerations
# =============================================================================

class RedundancyMode(Enum):
    """Redundancy operation modes"""
    ACTIVE_ACTIVE = "active_active"      # All channels active simultaneously
    ACTIVE_STANDBY = "active_standby"    # Primary + backup channels
    ADAPTIVE = "adaptive"                # Dynamic mode switching
    DEGRADED = "degraded"               # Fallback mode with limited channels

class ChannelPriority(Enum):
    """Channel priority levels"""
    PRIMARY = "primary"       # Highest priority, always used
    SECONDARY = "secondary"   # Medium priority, used when primary fails
    TERTIARY = "tertiary"     # Low priority, emergency fallback
    EMERGENCY = "emergency"   # Last resort, minimal functionality

class DeduplicationStrategy(Enum):
    """Deduplication strategies"""
    EXACT_MATCH = "exact_match"         # Exact content match
    HASH_BASED = "hash_based"           # Content hash matching
    ID_BASED = "id_based"               # Event ID matching
    HYBRID = "hybrid"                   # Combination of strategies

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class TelemetryEvent:
    """Telemetry event with redundancy metadata"""
    event_id: str
    timestamp: float
    payload: Dict[str, Any]
    source: str
    priority: ChannelPriority
    ttl_seconds: int = 3600  # Time to live
    retry_count: int = 0
    max_retries: int = 3
    compression_enabled: bool = False
    compression_type: str = "none"
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()

@dataclass
class ChannelConfig:
    """Configuration for a telemetry channel"""
    channel_type: ChannelType
    priority: ChannelPriority
    enabled: bool = True
    max_retries: int = 3
    retry_delay_ms: int = 1000
    timeout_ms: int = 5000
    batch_size: int = 100
    batch_timeout_ms: int = 1000
    compression_enabled: bool = True
    compression_type: str = "gzip"
    qos_threshold: float = 0.5  # Minimum QoS score to use channel

@dataclass
class RedundancyMetrics:
    """Metrics for redundancy operations"""
    total_events: int = 0
    successful_emissions: int = 0
    failed_emissions: int = 0
    duplicate_events: int = 0
    retry_events: int = 0
    channel_failures: Dict[ChannelType, int] = field(default_factory=dict)
    average_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    last_emission_time: float = 0.0

@dataclass
class DeduplicationWindow:
    """Sliding window for deduplication"""
    window_size: int = 1000
    time_window_seconds: int = 3600
    events: deque = field(default_factory=deque)
    event_hashes: Set[str] = field(default_factory=set)
    last_cleanup: float = field(default_factory=time.time)

# =============================================================================
# Redundancy Manager Implementation
# =============================================================================

class RedundancyManager:
    """
    Manages redundant telemetry emission across multiple channels
    
    This component is responsible for:
    1. Emitting to multiple channel types simultaneously
    2. Deduplicating events using various strategies
    3. Maintaining replay windows for fault recovery
    4. Supporting different redundancy modes
    """
    
    def __init__(self, config: Layer0Config, signal_negotiator: SignalNegotiator = None):
        self.config = config
        self.telemetry_config = config.telemetry
        self.signal_negotiator = signal_negotiator
        
        # Channel configuration
        self.channel_configs: Dict[ChannelType, ChannelConfig] = {}
        self.active_channels: Dict[ChannelType, bool] = {}
        
        # Redundancy settings
        self.redundancy_mode = RedundancyMode.ACTIVE_ACTIVE
        self.min_successful_channels = 1
        self.max_parallel_channels = 4
        
        # Event management
        self.event_queue: queue.Queue = queue.Queue(maxsize=10000)
        self.pending_events: Dict[str, TelemetryEvent] = {}
        self.completed_events: Dict[str, TelemetryEvent] = {}
        
        # Deduplication
        self.dedup_strategy = DeduplicationStrategy.HYBRID
        self.dedup_window = DeduplicationWindow()
        
        # Metrics and monitoring
        self.metrics = RedundancyMetrics()
        self.channel_health: Dict[ChannelType, Dict[str, Any]] = {}
        
        # Background workers
        self.emission_workers: List[threading.Thread] = []
        self.cleanup_workers: List[threading.Thread] = []
        self.running = False
        
        # Initialize channels
        self._initialize_channel_configs()
        if signal_negotiator:  # Only start workers if we have a signal negotiator
            self._start_background_workers()
    
    def _initialize_channel_configs(self):
        """Initialize configuration for all available channels"""
        
        # CloudWatch - Primary channel
        self.channel_configs[ChannelType.CLOUDWATCH] = ChannelConfig(
            channel_type=ChannelType.CLOUDWATCH,
            priority=ChannelPriority.PRIMARY,
            enabled=True,
            max_retries=3,
            retry_delay_ms=1000,
            timeout_ms=5000,
            batch_size=100,
            batch_timeout_ms=1000,
            compression_enabled=True,
            compression_type="gzip",
            qos_threshold=0.7
        )
        
        # X-Ray - Secondary channel
        self.channel_configs[ChannelType.XRAY] = ChannelConfig(
            channel_type=ChannelType.XRAY,
            priority=ChannelPriority.SECONDARY,
            enabled=True,
            max_retries=2,
            retry_delay_ms=500,
            timeout_ms=3000,
            batch_size=50,
            batch_timeout_ms=500,
            compression_enabled=False,  # X-Ray has its own compression
            compression_type="none",
            qos_threshold=0.6
        )
        
        # Local buffer - Tertiary channel
        self.channel_configs[ChannelType.LOCAL_BUFFER] = ChannelConfig(
            channel_type=ChannelType.LOCAL_BUFFER,
            priority=ChannelPriority.TERTIARY,
            enabled=True,
            max_retries=1,
            retry_delay_ms=100,
            timeout_ms=1000,
            batch_size=200,
            batch_timeout_ms=2000,
            compression_enabled=True,
            compression_type="gzip",
            qos_threshold=0.3
        )
        
        # Side channel - Emergency channel
        self.channel_configs[ChannelType.SIDE_CHANNEL] = ChannelConfig(
            channel_type=ChannelType.SIDE_CHANNEL,
            priority=ChannelPriority.EMERGENCY,
            enabled=True,
            max_retries=1,
            retry_delay_ms=50,
            timeout_ms=500,
            batch_size=500,
            batch_timeout_ms=5000,
            compression_enabled=True,
            compression_type="gzip",
            qos_threshold=0.2
        )
        
        # Initialize active status based on negotiated channels
        for channel_type in self.channel_configs:
            self.active_channels[channel_type] = False
        
        logger.info(f"Initialized {len(self.channel_configs)} channel configurations")
    
    def _start_background_workers(self):
        """Start background worker threads"""
        self.running = True
        
        # Start emission workers
        for i in range(self.config.telemetry.max_emission_workers):
            worker = threading.Thread(
                target=self._emission_worker,
                name=f"EmissionWorker-{i}",
                daemon=True
            )
            worker.start()
            self.emission_workers.append(worker)
        
        # Start cleanup worker
        cleanup_worker = threading.Thread(
            target=self._cleanup_worker,
            name="CleanupWorker",
            daemon=True
        )
        cleanup_worker.start()
        self.cleanup_workers.append(cleanup_worker)
        
        logger.info(f"Started {len(self.emission_workers)} emission workers and cleanup worker")
    
    def emit_telemetry(self, payload: Dict[str, Any], 
                      priority: ChannelPriority = ChannelPriority.PRIMARY,
                      ttl_seconds: int = 3600) -> str:
        """
        Emit telemetry data with redundancy across multiple channels
        
        Args:
            payload: Telemetry data to emit
            priority: Event priority level
            ttl_seconds: Time to live for the event
            
        Returns:
            Event ID for tracking
        """
        # Create telemetry event
        event = TelemetryEvent(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            payload=payload,
            source="scafad-layer0",
            priority=priority,
            ttl_seconds=ttl_seconds
        )
        
        # Check for duplicates
        if self._is_duplicate_event(event):
            self.metrics.duplicate_events += 1
            logger.debug(f"Duplicate event detected: {event.event_id}")
            return event.event_id
        
        # Add to event queue
        try:
            self.event_queue.put(event, timeout=1.0)
            self.pending_events[event.event_id] = event
            self.metrics.total_events += 1
            logger.debug(f"Queued telemetry event: {event.event_id}")
        except queue.Full:
            logger.warning("Event queue full, dropping event")
            self.metrics.failed_emissions += 1
        
        return event.event_id
    
    def _is_duplicate_event(self, event: TelemetryEvent) -> bool:
        """
        Check if an event is a duplicate using the configured strategy
        
        Args:
            event: Telemetry event to check
            
        Returns:
            True if event is duplicate, False otherwise
        """
        if self.dedup_strategy == DeduplicationStrategy.ID_BASED:
            return event.event_id in self.dedup_window.event_hashes
        
        elif self.dedup_strategy == DeduplicationStrategy.HASH_BASED:
            content_hash = self._hash_event_content(event)
            return content_hash in self.dedup_window.event_hashes
        
        elif self.dedup_strategy == DeduplicationStrategy.EXACT_MATCH:
            # More expensive exact matching
            for existing_event in self.dedup_window.events:
                if (existing_event.payload == event.payload and 
                    abs(existing_event.timestamp - event.timestamp) < 1.0):
                    return True
            return False
        
        elif self.dedup_strategy == DeduplicationStrategy.HYBRID:
            # Check both ID and content hash
            id_duplicate = event.event_id in self.dedup_window.event_hashes
            content_hash = self._hash_event_content(event)
            content_duplicate = content_hash in self.dedup_window.event_hashes
            
            return id_duplicate or content_duplicate
        
        return False
    
    def _hash_event_content(self, event: TelemetryEvent) -> str:
        """Generate hash of event content for deduplication"""
        # Create stable representation for hashing
        content_str = json.dumps(event.payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()
    
    def _add_to_dedup_window(self, event: TelemetryEvent):
        """Add event to deduplication window"""
        # Add to sliding window
        self.dedup_window.events.append(event)
        
        # Add hash to set
        if self.dedup_strategy in [DeduplicationStrategy.HASH_BASED, DeduplicationStrategy.HYBRID]:
            content_hash = self._hash_event_content(event)
            self.dedup_window.event_hashes.add(content_hash)
        
        if self.dedup_strategy in [DeduplicationStrategy.ID_BASED, DeduplicationStrategy.HYBRID]:
            self.dedup_window.event_hashes.add(event.event_id)
        
        # Maintain window size
        while len(self.dedup_window.events) > self.dedup_window.window_size:
            old_event = self.dedup_window.events.popleft()
            # Note: We don't remove from event_hashes here to avoid complexity
            # The cleanup worker will handle this periodically
    
    def _emission_worker(self):
        """Background worker for emitting telemetry events"""
        while self.running:
            try:
                # Get event from queue
                event = self.event_queue.get(timeout=1.0)
                if event is None:
                    continue
                
                # Emit to channels based on redundancy mode
                success = self._emit_to_channels(event)
                
                if success:
                    self.metrics.successful_emissions += 1
                    self.completed_events[event.event_id] = event
                    if event.event_id in self.pending_events:
                        del self.pending_events[event.event_id]
                else:
                    self.metrics.failed_emissions += 1
                    # Retry logic handled by _emit_to_channels
                
                # Add to deduplication window
                self._add_to_dedup_window(event)
                
                # Update metrics
                self.metrics.last_emission_time = time.time()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Emission worker error: {e}")
                self.metrics.failed_emissions += 1
    
    def _emit_to_channels(self, event: TelemetryEvent) -> bool:
        """
        Emit event to configured channels based on redundancy mode
        
        Args:
            event: Telemetry event to emit
            
        Returns:
            True if emission was successful to at least min_successful_channels
        """
        start_time = time.time()
        successful_emissions = 0
        failed_channels = []
        
        # Get available channels based on redundancy mode
        available_channels = self._get_available_channels(event.priority)
        
        if not available_channels:
            logger.warning(f"No available channels for event {event.event_id}")
            return False
        
        # Emit to channels
        emission_tasks = []
        for channel_type, config in available_channels.items():
            if config.enabled and self.active_channels.get(channel_type, False):
                task = asyncio.create_task(
                    self._emit_to_channel(channel_type, event, config)
                )
                emission_tasks.append((channel_type, task))
        
        # Wait for emissions to complete
        for channel_type, task in emission_tasks:
            try:
                success = asyncio.run(task)
                if success:
                    successful_emissions += 1
                else:
                    failed_channels.append(channel_type)
                    self._update_channel_health(channel_type, False)
            except Exception as e:
                logger.error(f"Emission to {channel_type} failed: {e}")
                failed_channels.append(channel_type)
                self._update_channel_health(channel_type, False)
        
        # Update overall metrics
        emission_time = (time.time() - start_time) * 1000
        self.metrics.total_latency_ms += emission_time
        self.metrics.average_latency_ms = (
            self.metrics.total_latency_ms / self.metrics.total_events
        )
        
        # Update channel failure counts
        for channel_type in failed_channels:
            if channel_type not in self.metrics.channel_failures:
                self.metrics.channel_failures[channel_type] = 0
            self.metrics.channel_failures[channel_type] += 1
        
        # Check if we met the minimum success requirement
        success = successful_emissions >= self.min_successful_channels
        
        if not success:
            logger.warning(
                f"Emission failed for event {event.event_id}: "
                f"{successful_emissions}/{len(available_channels)} channels succeeded"
            )
            
            # Retry logic for failed emissions
            if event.retry_count < event.max_retries:
                event.retry_count += 1
                event.timestamp = time.time()  # Update timestamp for retry
                
                # Re-queue with exponential backoff
                retry_delay = min(1000 * (2 ** event.retry_count), 10000)  # Max 10s
                threading.Timer(retry_delay / 1000.0, self._retry_event, args=[event]).start()
        
        return success
    
    def _get_available_channels(self, priority: ChannelPriority) -> Dict[ChannelType, ChannelConfig]:
        """
        Get available channels based on redundancy mode and priority
        
        Args:
            priority: Event priority level
            
        Returns:
            Dictionary of available channel configurations
        """
        available_channels = {}
        
        if self.redundancy_mode == RedundancyMode.ACTIVE_ACTIVE:
            # All enabled channels are available
            for channel_type, config in self.channel_configs.items():
                if config.enabled and self.active_channels.get(channel_type, False):
                    available_channels[channel_type] = config
        
        elif self.redundancy_mode == RedundancyMode.ACTIVE_STANDBY:
            # Primary + backup channels
            primary_channels = []
            backup_channels = []
            
            for channel_type, config in self.channel_configs.items():
                if not config.enabled or not self.active_channels.get(channel_type, False):
                    continue
                
                if config.priority == ChannelPriority.PRIMARY:
                    primary_channels.append((channel_type, config))
                elif config.priority in [ChannelPriority.SECONDARY, ChannelPriority.TERTIARY]:
                    backup_channels.append((channel_type, config))
            
            # Use primary channels first
            available_channels.update(dict(primary_channels))
            
            # Add backup channels if needed
            if len(available_channels) < self.min_successful_channels:
                available_channels.update(dict(backup_channels[:self.max_parallel_channels]))
        
        elif self.redundancy_mode == RedundancyMode.ADAPTIVE:
            # Dynamic channel selection based on health and QoS
            available_channels = self._select_adaptive_channels(priority)
        
        elif self.redundancy_mode == RedundancyMode.DEGRADED:
            # Minimal channel set for emergency operation
            for channel_type, config in self.channel_configs.items():
                if (config.enabled and 
                    self.active_channels.get(channel_type, False) and
                    config.priority in [ChannelPriority.EMERGENCY, ChannelPriority.TERTIARY]):
                    available_channels[channel_type] = config
        
        # Limit to maximum parallel channels
        if len(available_channels) > self.max_parallel_channels:
            # Sort by priority and QoS, keep top channels
            sorted_channels = sorted(
                available_channels.items(),
                key=lambda x: (x[1].priority.value, self._get_channel_qos(x[0])),
                reverse=True
            )
            available_channels = dict(sorted_channels[:self.max_parallel_channels])
        
        return available_channels
    
    def _select_adaptive_channels(self, priority: ChannelPriority) -> Dict[ChannelType, ChannelConfig]:
        """Select channels adaptively based on health and QoS"""
        available_channels = {}
        
        # Get channel health information
        channel_health = self.signal_negotiator.get_channel_health_summary()
        
        # Sort channels by health score
        healthy_channels = []
        for channel_type, config in self.channel_configs.items():
            if not config.enabled or not self.active_channels.get(channel_type, False):
                continue
            
            health_score = channel_health.get(channel_type.value, {}).get('qos_score', 0.0)
            if health_score >= config.qos_threshold:
                healthy_channels.append((channel_type, config, health_score))
        
        # Sort by health score and priority
        healthy_channels.sort(key=lambda x: (x[2], x[1].priority.value), reverse=True)
        
        # Select top channels
        for channel_type, config, health_score in healthy_channels[:self.max_parallel_channels]:
            available_channels[channel_type] = config
        
        return available_channels
    
    def _get_channel_qos(self, channel_type: ChannelType) -> float:
        """Get current QoS score for a channel"""
        channel_health = self.signal_negotiator.get_channel_health_summary()
        return channel_health.get(channel_type.value, {}).get('qos_score', 0.0)
    
    async def _emit_to_channel(self, channel_type: ChannelType, 
                              event: TelemetryEvent, 
                              config: ChannelConfig) -> bool:
        """
        Emit event to a specific channel
        
        Args:
            channel_type: Type of channel to emit to
            event: Telemetry event to emit
            config: Channel configuration
            
        Returns:
            True if emission was successful
        """
        try:
            start_time = time.time()
            
            # Prepare payload
            payload = self._prepare_payload_for_channel(event, config)
            
            # Emit based on channel type
            if channel_type == ChannelType.CLOUDWATCH:
                success = await self._emit_to_cloudwatch(payload, config)
            elif channel_type == ChannelType.XRAY:
                success = await self._emit_to_xray(payload, config)
            elif channel_type == ChannelType.LOCAL_BUFFER:
                success = await self._emit_to_local_buffer(payload, config)
            elif channel_type == ChannelType.SIDE_CHANNEL:
                success = await self._emit_to_side_channel(payload, config)
            else:
                success = False
            
            # Update channel health
            emission_time = (time.time() - start_time) * 1000
            self._update_channel_health(channel_type, success, emission_time)
            
            return success
            
        except Exception as e:
            logger.error(f"Emission to {channel_type} failed: {e}")
            self._update_channel_health(channel_type, False, 0.0)
            return False
    
    def _prepare_payload_for_channel(self, event: TelemetryEvent, 
                                   config: ChannelConfig) -> Dict[str, Any]:
        """Prepare payload for specific channel requirements"""
        payload = event.payload.copy()
        
        # Add metadata
        payload['_metadata'] = {
            'event_id': event.event_id,
            'timestamp': event.timestamp,
            'source': event.source,
            'priority': event.priority.value,
            'channel_type': config.channel_type.value,
            'compression_enabled': config.compression_enabled,
            'compression_type': config.compression_type
        }
        
        # Apply compression if enabled
        if config.compression_enabled and config.compression_type != "none":
            payload = self._apply_compression(payload, config.compression_type)
        
        return payload
    
    def _apply_compression(self, payload: Dict[str, Any], compression_type: str) -> Dict[str, Any]:
        """Apply compression to payload"""
        try:
            if compression_type == "gzip":
                import gzip
                json_str = json.dumps(payload)
                compressed = gzip.compress(json_str.encode('utf-8'))
                return {
                    '_compressed': True,
                    '_compression_type': 'gzip',
                    '_data': compressed.hex()
                }
            elif compression_type == "zlib":
                import zlib
                json_str = json.dumps(payload)
                compressed = zlib.compress(json_str.encode('utf-8'))
                return {
                    '_compressed': True,
                    '_compression_type': 'zlib',
                    '_data': compressed.hex()
                }
            else:
                return payload
        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            return payload
    
    async def _emit_to_cloudwatch(self, payload: Dict[str, Any], 
                                config: ChannelConfig) -> bool:
        """Emit to CloudWatch logs"""
        try:
            # Simulate CloudWatch emission
            await asyncio.sleep(0.01)  # 10ms simulation
            logger.debug(f"Emitted to CloudWatch: {payload.get('_metadata', {}).get('event_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"CloudWatch emission failed: {e}")
            return False
    
    async def _emit_to_xray(self, payload: Dict[str, Any], 
                           config: ChannelConfig) -> bool:
        """Emit to X-Ray"""
        try:
            # Simulate X-Ray emission
            await asyncio.sleep(0.005)  # 5ms simulation
            logger.debug(f"Emitted to X-Ray: {payload.get('_metadata', {}).get('event_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"X-Ray emission failed: {e}")
            return False
    
    async def _emit_to_local_buffer(self, payload: Dict[str, Any], 
                                  config: ChannelConfig) -> bool:
        """Emit to local buffer"""
        try:
            # Simulate local buffer emission
            await asyncio.sleep(0.001)  # 1ms simulation
            logger.debug(f"Emitted to local buffer: {payload.get('_metadata', {}).get('event_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Local buffer emission failed: {e}")
            return False
    
    async def _emit_to_side_channel(self, payload: Dict[str, Any], 
                                  config: ChannelConfig) -> bool:
        """Emit to side channel"""
        try:
            # Simulate side channel emission
            await asyncio.sleep(0.002)  # 2ms simulation
            logger.debug(f"Emitted to side channel: {payload.get('_metadata', {}).get('event_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Side channel emission failed: {e}")
            return False
    
    def _retry_event(self, event: TelemetryEvent):
        """Retry a failed event emission"""
        try:
            self.event_queue.put(event, timeout=1.0)
            logger.debug(f"Retrying event {event.event_id} (attempt {event.retry_count})")
        except queue.Full:
            logger.warning(f"Retry queue full, dropping event {event.event_id}")
    
    def _update_channel_health(self, channel_type: ChannelType, 
                             success: bool, latency_ms: float = 0.0):
        """Update health metrics for a channel"""
        if channel_type not in self.channel_health:
            self.channel_health[channel_type] = {
                'success_count': 0,
                'failure_count': 0,
                'total_latency_ms': 0.0,
                'last_success': 0.0,
                'last_failure': 0.0
            }
        
        health = self.channel_health[channel_type]
        
        if success:
            health['success_count'] += 1
            health['last_success'] = time.time()
            if latency_ms > 0:
                health['total_latency_ms'] += latency_ms
        else:
            health['failure_count'] += 1
            health['last_failure'] = time.time()
    
    def _cleanup_worker(self):
        """Background worker for cleanup operations"""
        while self.running:
            try:
                time.sleep(60)  # Run every minute
                
                # Clean up old events
                self._cleanup_old_events()
                
                # Clean up deduplication window
                self._cleanup_dedup_window()
                
                # Update channel status based on health
                self._update_channel_status()
                
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
    
    def _cleanup_old_events(self):
        """Clean up old completed events"""
        current_time = time.time()
        events_to_remove = []
        
        for event_id, event in self.completed_events.items():
            if current_time - event.timestamp > event.ttl_seconds:
                events_to_remove.append(event_id)
        
        for event_id in events_to_remove:
            del self.completed_events[event_id]
        
        if events_to_remove:
            logger.debug(f"Cleaned up {len(events_to_remove)} old events")
    
    def _cleanup_dedup_window(self):
        """Clean up old entries in deduplication window"""
        current_time = time.time()
        
        # Remove old events from window
        while (self.dedup_window.events and 
               current_time - self.dedup_window.events[0].timestamp > 
               self.dedup_window.time_window_seconds):
            self.dedup_window.events.popleft()
        
        # Clear hashes if window is empty
        if not self.dedup_window.events:
            self.dedup_window.event_hashes.clear()
        
        self.dedup_window.last_cleanup = current_time
    
    def _update_channel_status(self):
        """Update channel active status based on health"""
        for channel_type, health in self.channel_health.items():
            if channel_type not in self.channel_configs:
                continue
            
            config = self.channel_configs[channel_type]
            total_attempts = health['success_count'] + health['failure_count']
            
            if total_attempts > 0:
                success_rate = health['success_count'] / total_attempts
                
                # Deactivate channel if success rate is too low
                if success_rate < 0.5:  # 50% threshold
                    if self.active_channels.get(channel_type, False):
                        logger.warning(f"Deactivating {channel_type} due to low success rate: {success_rate:.2f}")
                        self.active_channels[channel_type] = False
                else:
                    # Reactivate channel if it was previously deactivated
                    if not self.active_channels.get(channel_type, False):
                        logger.info(f"Reactivating {channel_type} due to improved success rate: {success_rate:.2f}")
                        self.active_channels[channel_type] = True
    
    def get_redundancy_summary(self) -> Dict[str, Any]:
        """Get summary of redundancy operations"""
        return {
            'redundancy_mode': self.redundancy_mode.value,
            'active_channels': len([c for c in self.active_channels.values() if c]),
            'total_channels': len(self.channel_configs),
            'pending_events': len(self.pending_events),
            'completed_events': len(self.completed_events),
            'queue_size': self.event_queue.qsize(),
            'metrics': {
                'total_events': self.metrics.total_events,
                'successful_emissions': self.metrics.successful_emissions,
                'failed_emissions': self.metrics.failed_emissions,
                'duplicate_events': self.metrics.duplicate_events,
                'retry_events': self.metrics.retry_events,
                'average_latency_ms': self.metrics.average_latency_ms,
                'channel_failures': {
                    k.value: v for k, v in self.metrics.channel_failures.items()
                }
            },
            'channel_health': {
                k.value: v for k, v in self.channel_health.items()
            }
        }
    
    def duplicate_telemetry(self, telemetry_record, strategy: str = "active_active") -> Dict[str, Any]:
        """Duplicate telemetry record for redundancy"""
        try:
            # Create telemetry event from record
            event = TelemetryEvent(
                event_id=f"dup_{telemetry_record.telemetry_id if hasattr(telemetry_record, 'telemetry_id') else str(uuid.uuid4())}",
                timestamp=time.time(),
                payload={
                    "original_id": getattr(telemetry_record, 'telemetry_id', 'unknown'),
                    "duplication_strategy": strategy,
                    "duplication_timestamp": time.time(),
                    "original_data": telemetry_record.__dict__ if hasattr(telemetry_record, '__dict__') else str(telemetry_record)
                },
                source="redundancy_manager",
                priority=ChannelPriority.PRIMARY
            )
            
            # Add to queue for processing
            self.event_queue.put(event)
            
            return {
                "duplicated": True,
                "replica_count": 2 if strategy == "active_active" else 1,
                "event_id": event.event_id,
                "strategy": strategy
            }
        except Exception as e:
            logger.error(f"Failed to duplicate telemetry: {e}")
            return {
                "duplicated": False,
                "error": str(e)
            }
    
    def initiate_failover(self, primary_channel: str, standby_channel: str) -> Dict[str, Any]:
        """Initiate failover from primary to standby channel"""
        try:
            logger.info(f"Initiating failover from {primary_channel} to {standby_channel}")
            
            # Update channel status
            if hasattr(self, 'active_channels'):
                # Mark primary as inactive
                for channel_type in self.active_channels:
                    if channel_type.value == primary_channel:
                        self.active_channels[channel_type] = False
                
                # Mark standby as active
                for channel_type in self.active_channels:
                    if channel_type.value == standby_channel:
                        self.active_channels[channel_type] = True
            
            return {
                "failover_initiated": True,
                "primary_channel": primary_channel,
                "standby_channel": standby_channel,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Failover failed: {e}")
            return {
                "failover_initiated": False,
                "error": str(e)
            }
    
    def check_duplicate(self, telemetry_id: str) -> Dict[str, Any]:
        """Check if telemetry ID is a duplicate"""
        try:
            # Check if ID exists in dedup window
            is_duplicate = telemetry_id in self.dedup_window.event_hashes
            
            if not is_duplicate:
                # Add to dedup window
                self.dedup_window.event_hashes.add(telemetry_id)
                self.dedup_window.events.append({
                    "id": telemetry_id,
                    "timestamp": time.time()
                })
            
            return {
                "is_duplicate": is_duplicate,
                "telemetry_id": telemetry_id,
                "timestamp": time.time(),
                "dedup_window_size": len(self.dedup_window.event_hashes)
            }
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return {
                "is_duplicate": False,
                "error": str(e)
            }
    
    def execute_idempotent_operation(self, operation_id: str, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an idempotent operation"""
        try:
            # Check if operation was already executed
            cache_key = f"idempotent_{operation_id}"
            
            if hasattr(self, '_idempotency_cache'):
                if cache_key in self._idempotency_cache:
                    # Return cached result
                    return self._idempotency_cache[cache_key]
            else:
                self._idempotency_cache = {}
            
            # Execute operation (simulate)
            result = {
                "operation_id": operation_id,
                "executed": True,
                "timestamp": time.time(),
                "data": operation_data,
                "result": f"Operation {operation_id} completed successfully"
            }
            
            # Cache result
            self._idempotency_cache[cache_key] = result
            
            return result
        except Exception as e:
            logger.error(f"Idempotent operation failed: {e}")
            return {
                "operation_id": operation_id,
                "executed": False,
                "error": str(e)
            }
    
    def resolve_conflicts(self, conflicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve conflicts between multiple telemetry sources"""
        try:
            if not conflicts:
                return {"consensus_value": None, "conflicts_resolved": 0}
            
            # Simple consensus: majority wins
            value_counts = {}
            for conflict in conflicts:
                value = conflict.get("value", "unknown")
                value_counts[value] = value_counts.get(value, 0) + 1
            
            # Find most common value
            consensus_value = max(value_counts.items(), key=lambda x: x[1])[0]
            consensus_count = value_counts[consensus_value]
            
            return {
                "consensus_value": consensus_value,
                "consensus_count": consensus_count,
                "total_conflicts": len(conflicts),
                "conflicts_resolved": len(conflicts),
                "resolution_method": "majority_vote"
            }
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return {
                "consensus_value": None,
                "error": str(e)
            }
    
    def set_redundancy_mode(self, mode: RedundancyMode):
        """Change redundancy mode"""
        old_mode = self.redundancy_mode
        self.redundancy_mode = mode
        
        logger.info(f"Redundancy mode changed from {old_mode.value} to {mode.value}")
        
        # Adjust settings based on new mode
        if mode == RedundancyMode.ACTIVE_ACTIVE:
            self.min_successful_channels = 1
            self.max_parallel_channels = 4
        elif mode == RedundancyMode.ACTIVE_STANDBY:
            self.min_successful_channels = 1
            self.max_parallel_channels = 2
        elif mode == RedundancyMode.ADAPTIVE:
            self.min_successful_channels = 1
            self.max_parallel_channels = 3
        elif mode == RedundancyMode.DEGRADED:
            self.min_successful_channels = 1
            self.max_parallel_channels = 1
    
    def shutdown(self):
        """Shutdown the redundancy manager"""
        logger.info("Shutting down RedundancyManager...")
        
        self.running = False
        
        # Wait for workers to finish
        for worker in self.emission_workers:
            worker.join(timeout=5.0)
        
        for worker in self.cleanup_workers:
            worker.join(timeout=5.0)
        
        logger.info("RedundancyManager shutdown complete")

# =============================================================================
# Factory Functions
# =============================================================================

def create_redundancy_manager(config: Layer0Config = None, 
                            signal_negotiator: SignalNegotiator = None) -> RedundancyManager:
    """Create a new RedundancyManager instance"""
    if config is None:
        from .app_config import get_default_config
        config = get_default_config()
    
    if signal_negotiator is None:
        signal_negotiator = create_signal_negotiator(config)
    
    return RedundancyManager(config, signal_negotiator)

# =============================================================================
# Testing and Validation
# =============================================================================

async def test_redundancy_manager():
    """Test the RedundancyManager functionality"""
    from .app_config import create_testing_config
    
    config = create_testing_config()
    signal_negotiator = SignalNegotiator(config)
    
    # Wait for negotiation to complete
    await signal_negotiator.negotiate_all_channels()
    
    # Create redundancy manager
    redundancy_manager = RedundancyManager(config, signal_negotiator)
    
    print("Testing RedundancyManager...")
    
    # Test telemetry emission
    test_payload = {
        "function_id": "test-function-001",
        "execution_phase": "invoke",
        "duration_ms": 150.5,
        "memory_usage_mb": 128.0,
        "cpu_utilization": 45.2
    }
    
    event_id = redundancy_manager.emit_telemetry(
        payload=test_payload,
        priority=ChannelPriority.PRIMARY
    )
    
    print(f"Emitted telemetry event: {event_id}")
    
    # Wait for emission to complete
    await asyncio.sleep(2.0)
    
    # Get summary
    summary = redundancy_manager.get_redundancy_summary()
    print(f"\nRedundancy Summary:")
    print(f"  Mode: {summary['redundancy_mode']}")
    print(f"  Active Channels: {summary['active_channels']}")
    print(f"  Total Events: {summary['metrics']['total_events']}")
    print(f"  Successful: {summary['metrics']['successful_emissions']}")
    print(f"  Failed: {summary['metrics']['failed_emissions']}")
    print(f"  Duplicates: {summary['metrics']['duplicate_events']}")
    
    # Shutdown
    redundancy_manager.shutdown()

if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_redundancy_manager())

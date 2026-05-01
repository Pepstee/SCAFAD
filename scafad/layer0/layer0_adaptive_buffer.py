"""
SCAFAD Layer 0: Adaptive Buffer and Backpressure System
=======================================================

Implements adaptive buffer management with sophisticated backpressure mechanisms:
- Queue watermarks (low/mid/high) with dynamic triggering
- Backpressure signal propagation throughout the pipeline
- Batch resizing under pressure with adaptive algorithms
- LOSS_POLICY handling (lossy_tail vs lossless_block vs hybrid)
- Bounded memory enforcement with intelligent eviction
- Shed accounting under chaos conditions (packet loss/slow sinks)

Academic References:
- Flow control algorithms (Ramakrishnan & Jain, RFC 2309)
- Adaptive buffering strategies (Floyd & Jacobson, RED)
- Backpressure propagation (Akidau et al., Dataflow Model)
- Memory-bounded stream processing (Arasu et al., Stream Systems)
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Deque
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import weakref

# Import configuration
from .app_config import Layer0Config

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Enumerations and Data Structures
# =============================================================================

class LossPolicy(Enum):
    """Loss policies for buffer overflow handling"""
    LOSSLESS_BLOCK = "lossless_block"      # Block when full (default)
    LOSSY_TAIL = "lossy_tail"              # Drop oldest items
    HYBRID = "hybrid"                       # Smart hybrid approach

class BackpressureLevel(Enum):
    """Backpressure severity levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class WatermarkType(Enum):
    """Watermark trigger types"""
    LOW = "low"
    MID = "mid"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class BufferConfig:
    """Configuration for adaptive buffer"""
    max_queue_size: int = 1000
    max_memory_bytes: int = 100 * 1024 * 1024  # 100MB
    low_watermark: float = 0.2      # 20%
    mid_watermark: float = 0.5      # 50%
    high_watermark: float = 0.8     # 80%
    critical_watermark: float = 0.95 # 95%
    
    base_batch_size: int = 100
    min_batch_size: int = 10
    max_batch_size: int = 500
    
    loss_policy: LossPolicy = LossPolicy.LOSSLESS_BLOCK
    enable_adaptive_batching: bool = True
    enable_backpressure: bool = True
    
    # Memory management
    item_size_estimate_bytes: int = 1024
    memory_check_interval: int = 100  # Check every N items
    
    # Metrics retention
    metrics_retention_count: int = 1000

@dataclass
class WatermarkEvent:
    """Watermark trigger event"""
    timestamp: float
    watermark_type: WatermarkType
    queue_ratio: float
    queue_size: int
    memory_usage_bytes: int
    backpressure_level: BackpressureLevel

@dataclass
class BackpressureEvent:
    """Backpressure event record"""
    timestamp: float
    level: BackpressureLevel
    trigger: str
    queue_ratio: float
    memory_ratio: float
    shed_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BufferMetrics:
    """Comprehensive buffer metrics"""
    items_enqueued: int = 0
    items_dequeued: int = 0
    items_shed: int = 0
    bytes_enqueued: int = 0
    bytes_dequeued: int = 0
    bytes_shed: int = 0
    
    enqueue_blocked_count: int = 0
    backpressure_events: int = 0
    watermark_triggers: int = 0
    batch_resizes: int = 0
    
    avg_queue_size: float = 0.0
    max_queue_size_reached: int = 0
    avg_memory_usage: float = 0.0
    max_memory_usage: int = 0

# =============================================================================
# Core Adaptive Buffer Implementation  
# =============================================================================

class AdaptiveBuffer:
    """
    Adaptive buffer with sophisticated backpressure and watermark management
    
    Features:
    - Dynamic watermark-based backpressure
    - Multiple loss policies with intelligent switching
    - Adaptive batch sizing based on pressure
    - Bounded memory management with eviction
    - Comprehensive metrics and monitoring
    - Thread-safe operations
    """
    
    def __init__(self, config: BufferConfig, name: str = "adaptive_buffer"):
        self.config = config
        self.name = name
        
        # Core buffer state
        self.queue: Deque[Tuple[Any, int, float]] = deque()  # (item, size, timestamp)
        self.current_size = 0
        self.memory_usage_bytes = 0
        
        # Adaptive state
        self.current_batch_size = config.base_batch_size
        self.current_loss_policy = config.loss_policy
        self.backpressure_level = BackpressureLevel.NONE
        
        # Event tracking
        self.watermark_events: Deque[WatermarkEvent] = deque(maxlen=config.metrics_retention_count)
        self.backpressure_events: Deque[BackpressureEvent] = deque(maxlen=config.metrics_retention_count)
        
        # Metrics
        self.metrics = BufferMetrics()
        self.last_metrics_time = time.time()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Backpressure subscribers
        self._backpressure_subscribers: List[Callable] = []
        
        # Background monitoring
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        logger.info(f"AdaptiveBuffer '{name}' initialized with config: {config}")
        
        # Start monitoring
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start background monitoring thread"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitoring_worker, daemon=True)
        self._monitor_thread.start()
        logger.info(f"AdaptiveBuffer '{self.name}' monitoring started")
    
    def _monitoring_worker(self):
        """Background monitoring worker"""
        while self._monitoring_active:
            try:
                with self._lock:
                    self._update_metrics()
                    self._check_memory_pressure()
                    self._adapt_batch_size()
                time.sleep(0.1)  # 100ms monitoring interval
            except Exception as e:
                logger.error(f"AdaptiveBuffer monitoring error: {e}")
                time.sleep(1.0)
    
    def enqueue(self, item: Any, size_bytes: Optional[int] = None, 
                timestamp: Optional[float] = None) -> bool:
        """
        Enqueue item with comprehensive handling
        
        Returns:
            True if enqueued successfully, False if blocked
        """
        if size_bytes is None:
            size_bytes = self.config.item_size_estimate_bytes
        
        if timestamp is None:
            timestamp = time.time()
        
        with self._lock:
            # Check if we can enqueue
            if not self._can_enqueue(size_bytes):
                self.metrics.enqueue_blocked_count += 1
                
                # Try to make space according to loss policy
                if not self._make_space_for_item(size_bytes):
                    return False  # Blocked
            
            # Enqueue the item
            self.queue.append((item, size_bytes, timestamp))
            self.current_size += 1
            self.memory_usage_bytes += size_bytes
            
            # Update metrics
            self.metrics.items_enqueued += 1
            self.metrics.bytes_enqueued += size_bytes
            
            # Check watermarks
            self._check_watermarks()
            
            return True
    
    def dequeue(self, batch_size: Optional[int] = None) -> List[Any]:
        """
        Dequeue items with adaptive batching
        
        Returns:
            List of dequeued items
        """
        if batch_size is None:
            batch_size = self.current_batch_size
        
        with self._lock:
            items = []
            actual_batch_size = min(batch_size, len(self.queue))
            
            for _ in range(actual_batch_size):
                if self.queue:
                    item, size_bytes, timestamp = self.queue.popleft()
                    items.append(item)
                    self.current_size -= 1
                    self.memory_usage_bytes -= size_bytes
                    
                    # Update metrics
                    self.metrics.items_dequeued += 1
                    self.metrics.bytes_dequeued += size_bytes
            
            # Check watermarks after dequeue
            self._check_watermarks()
            
            return items
    
    def _can_enqueue(self, size_bytes: int) -> bool:
        """Check if item can be enqueued"""
        # Size check
        if self.current_size >= self.config.max_queue_size:
            return False
        
        # Memory check
        if self.memory_usage_bytes + size_bytes > self.config.max_memory_bytes:
            return False
        
        return True
    
    def _make_space_for_item(self, size_bytes: int) -> bool:
        """Make space for new item according to loss policy"""
        if self.current_loss_policy == LossPolicy.LOSSLESS_BLOCK:
            return False  # Block, don't make space
        
        elif self.current_loss_policy == LossPolicy.LOSSY_TAIL:
            # Drop oldest items until we have space
            space_made = False
            while (self.queue and 
                   (self.current_size >= self.config.max_queue_size or
                    self.memory_usage_bytes + size_bytes > self.config.max_memory_bytes)):
                
                dropped_item, dropped_size, dropped_timestamp = self.queue.popleft()
                self.current_size -= 1
                self.memory_usage_bytes -= dropped_size
                
                # Track shedding
                self.metrics.items_shed += 1
                self.metrics.bytes_shed += dropped_size
                
                space_made = True
            
            return space_made
        
        elif self.current_loss_policy == LossPolicy.HYBRID:
            # Smart hybrid approach
            queue_ratio = self.current_size / self.config.max_queue_size
            
            if queue_ratio > self.config.high_watermark:
                # Above high watermark - act like lossy_tail
                return self._make_space_for_item_lossy(size_bytes)
            else:
                # Below high watermark - act like lossless_block
                return False
        
        return False
    
    def _make_space_for_item_lossy(self, size_bytes: int) -> bool:
        """Make space using lossy approach"""
        space_made = False
        while (self.queue and 
               (self.current_size >= self.config.max_queue_size or
                self.memory_usage_bytes + size_bytes > self.config.max_memory_bytes)):
            
            dropped_item, dropped_size, dropped_timestamp = self.queue.popleft()
            self.current_size -= 1
            self.memory_usage_bytes -= dropped_size
            
            # Track shedding
            self.metrics.items_shed += 1
            self.metrics.bytes_shed += dropped_size
            
            space_made = True
        
        return space_made
    
    def _check_watermarks(self):
        """Check queue watermarks and trigger appropriate actions"""
        queue_ratio = self.current_size / self.config.max_queue_size if self.config.max_queue_size > 0 else 0
        memory_ratio = self.memory_usage_bytes / self.config.max_memory_bytes if self.config.max_memory_bytes > 0 else 0
        
        # Determine watermark level
        if queue_ratio >= self.config.critical_watermark or memory_ratio >= 0.95:
            self._trigger_watermark(WatermarkType.CRITICAL, queue_ratio)
        elif queue_ratio >= self.config.high_watermark or memory_ratio >= 0.8:
            self._trigger_watermark(WatermarkType.HIGH, queue_ratio)
        elif queue_ratio >= self.config.mid_watermark or memory_ratio >= 0.5:
            self._trigger_watermark(WatermarkType.MID, queue_ratio)
        elif queue_ratio <= self.config.low_watermark and memory_ratio <= 0.2:
            self._trigger_watermark(WatermarkType.LOW, queue_ratio)
    
    def _trigger_watermark(self, watermark_type: WatermarkType, queue_ratio: float):
        """Trigger watermark-specific actions"""
        timestamp = time.time()
        
        # Create watermark event
        event = WatermarkEvent(
            timestamp=timestamp,
            watermark_type=watermark_type,
            queue_ratio=queue_ratio,
            queue_size=self.current_size,
            memory_usage_bytes=self.memory_usage_bytes,
            backpressure_level=self._determine_backpressure_level(queue_ratio)
        )
        
        self.watermark_events.append(event)
        self.metrics.watermark_triggers += 1
        
        # Execute watermark-specific actions
        if watermark_type == WatermarkType.CRITICAL:
            self._trigger_critical_watermark(event)
        elif watermark_type == WatermarkType.HIGH:
            self._trigger_high_watermark(event)
        elif watermark_type == WatermarkType.MID:
            self._trigger_mid_watermark(event)
        elif watermark_type == WatermarkType.LOW:
            self._trigger_low_watermark(event)
        
        logger.debug(f"AdaptiveBuffer '{self.name}' watermark triggered: {watermark_type.value} (ratio={queue_ratio:.3f})")
    
    def _trigger_critical_watermark(self, event: WatermarkEvent):
        """Handle critical watermark"""
        # Switch to aggressive lossy policy
        self.current_loss_policy = LossPolicy.LOSSY_TAIL
        
        # Minimize batch size
        self.current_batch_size = self.config.min_batch_size
        
        # Trigger critical backpressure
        self._trigger_backpressure(BackpressureLevel.CRITICAL, "critical_watermark", event)
    
    def _trigger_high_watermark(self, event: WatermarkEvent):
        """Handle high watermark"""
        # Reduce batch size aggressively
        self.current_batch_size = max(self.config.min_batch_size, self.current_batch_size // 2)
        
        # Switch to hybrid policy if needed
        if self.current_loss_policy == LossPolicy.LOSSLESS_BLOCK:
            self.current_loss_policy = LossPolicy.HYBRID
        
        # Trigger high backpressure
        self._trigger_backpressure(BackpressureLevel.HIGH, "high_watermark", event)
    
    def _trigger_mid_watermark(self, event: WatermarkEvent):
        """Handle mid watermark"""
        # Moderate batch size reduction
        self.current_batch_size = max(self.config.min_batch_size, int(self.current_batch_size * 0.8))
        
        # Trigger medium backpressure
        self._trigger_backpressure(BackpressureLevel.MEDIUM, "mid_watermark", event)
    
    def _trigger_low_watermark(self, event: WatermarkEvent):
        """Handle low watermark"""
        # Gradually increase batch size
        self.current_batch_size = min(self.config.max_batch_size, int(self.current_batch_size * 1.2))
        
        # Return to lossless policy
        if self.current_loss_policy != LossPolicy.LOSSLESS_BLOCK:
            self.current_loss_policy = self.config.loss_policy
        
        # Reduce backpressure
        self._trigger_backpressure(BackpressureLevel.LOW, "low_watermark", event)
    
    def _determine_backpressure_level(self, queue_ratio: float) -> BackpressureLevel:
        """Determine backpressure level based on queue state"""
        if queue_ratio >= self.config.critical_watermark:
            return BackpressureLevel.CRITICAL
        elif queue_ratio >= self.config.high_watermark:
            return BackpressureLevel.HIGH
        elif queue_ratio >= self.config.mid_watermark:
            return BackpressureLevel.MEDIUM
        elif queue_ratio >= self.config.low_watermark:
            return BackpressureLevel.LOW
        else:
            return BackpressureLevel.NONE
    
    def _trigger_backpressure(self, level: BackpressureLevel, trigger: str, event: WatermarkEvent):
        """Trigger backpressure with notification"""
        if level != self.backpressure_level:
            self.backpressure_level = level
            
            # Create backpressure event
            bp_event = BackpressureEvent(
                timestamp=time.time(),
                level=level,
                trigger=trigger,
                queue_ratio=event.queue_ratio,
                memory_ratio=self.memory_usage_bytes / self.config.max_memory_bytes,
                shed_count=self.metrics.items_shed,
                metadata={
                    'watermark_type': event.watermark_type.value,
                    'queue_size': event.queue_size,
                    'memory_usage_bytes': event.memory_usage_bytes
                }
            )
            
            self.backpressure_events.append(bp_event)
            self.metrics.backpressure_events += 1
            
            # Notify subscribers
            self._notify_backpressure_subscribers(bp_event)
            
            logger.info(f"AdaptiveBuffer '{self.name}' backpressure: {level.value} (trigger: {trigger})")
    
    def _notify_backpressure_subscribers(self, event: BackpressureEvent):
        """Notify backpressure subscribers"""
        for subscriber in self._backpressure_subscribers[:]:  # Copy to avoid modification during iteration
            try:
                subscriber(event)
            except Exception as e:
                logger.warning(f"Backpressure subscriber notification failed: {e}")
    
    def subscribe_backpressure(self, callback: Callable[[BackpressureEvent], None]):
        """Subscribe to backpressure events"""
        self._backpressure_subscribers.append(callback)
    
    def unsubscribe_backpressure(self, callback: Callable[[BackpressureEvent], None]):
        """Unsubscribe from backpressure events"""
        if callback in self._backpressure_subscribers:
            self._backpressure_subscribers.remove(callback)
    
    def _check_memory_pressure(self):
        """Check and handle memory pressure"""
        memory_ratio = self.memory_usage_bytes / self.config.max_memory_bytes
        
        if memory_ratio > 0.9:
            # Critical memory pressure - emergency cleanup
            items_to_drop = max(1, self.current_size // 10)  # Drop 10%
            for _ in range(min(items_to_drop, len(self.queue))):
                if self.queue:
                    dropped_item, dropped_size, dropped_timestamp = self.queue.popleft()
                    self.current_size -= 1
                    self.memory_usage_bytes -= dropped_size
                    self.metrics.items_shed += 1
                    self.metrics.bytes_shed += dropped_size
    
    def _adapt_batch_size(self):
        """Adapt batch size based on current conditions"""
        if not self.config.enable_adaptive_batching:
            return
        
        queue_ratio = self.current_size / self.config.max_queue_size if self.config.max_queue_size > 0 else 0
        
        # Adaptive batch sizing algorithm
        if queue_ratio > 0.8:
            # High pressure - reduce batch size
            new_batch_size = max(self.config.min_batch_size, int(self.current_batch_size * 0.9))
        elif queue_ratio < 0.3:
            # Low pressure - increase batch size
            new_batch_size = min(self.config.max_batch_size, int(self.current_batch_size * 1.1))
        else:
            # Stable - no change
            new_batch_size = self.current_batch_size
        
        if new_batch_size != self.current_batch_size:
            self.current_batch_size = new_batch_size
            self.metrics.batch_resizes += 1
            logger.debug(f"AdaptiveBuffer '{self.name}' batch size adapted: {self.current_batch_size}")
    
    def _update_metrics(self):
        """Update internal metrics"""
        current_time = time.time()
        elapsed = current_time - self.last_metrics_time
        
        if elapsed > 0:
            # Update rolling averages
            alpha = 0.1  # Smoothing factor
            self.metrics.avg_queue_size = (alpha * self.current_size + 
                                          (1 - alpha) * self.metrics.avg_queue_size)
            self.metrics.avg_memory_usage = (alpha * self.memory_usage_bytes + 
                                            (1 - alpha) * self.metrics.avg_memory_usage)
            
            # Update maximums
            self.metrics.max_queue_size_reached = max(self.metrics.max_queue_size_reached, self.current_size)
            self.metrics.max_memory_usage = max(self.metrics.max_memory_usage, self.memory_usage_bytes)
        
        self.last_metrics_time = current_time
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive buffer status"""
        with self._lock:
            queue_ratio = self.current_size / self.config.max_queue_size if self.config.max_queue_size > 0 else 0
            memory_ratio = self.memory_usage_bytes / self.config.max_memory_bytes if self.config.max_memory_bytes > 0 else 0
            
            return {
                'name': self.name,
                'current_size': self.current_size,
                'max_size': self.config.max_queue_size,
                'queue_ratio': queue_ratio,
                'memory_usage_bytes': self.memory_usage_bytes,
                'max_memory_bytes': self.config.max_memory_bytes,
                'memory_ratio': memory_ratio,
                'current_batch_size': self.current_batch_size,
                'backpressure_active': self.backpressure_level != BackpressureLevel.NONE,
                'backpressure_level': self.backpressure_level.value,
                'loss_policy': self.current_loss_policy.value,
                'metrics': {
                    'items_enqueued': self.metrics.items_enqueued,
                    'items_dequeued': self.metrics.items_dequeued,
                    'items_shed': self.metrics.items_shed,
                    'bytes_enqueued': self.metrics.bytes_enqueued,
                    'bytes_dequeued': self.metrics.bytes_dequeued,
                    'bytes_shed': self.metrics.bytes_shed,
                    'enqueue_blocked_count': self.metrics.enqueue_blocked_count,
                    'backpressure_events': self.metrics.backpressure_events,
                    'watermark_triggers': self.metrics.watermark_triggers,
                    'batch_resizes': self.metrics.batch_resizes,
                    'avg_queue_size': self.metrics.avg_queue_size,
                    'max_queue_size_reached': self.metrics.max_queue_size_reached,
                    'avg_memory_usage': self.metrics.avg_memory_usage,
                    'max_memory_usage': self.metrics.max_memory_usage
                }
            }
    
    def get_watermark_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent watermark events"""
        with self._lock:
            events = []
            for event in list(self.watermark_events)[-limit:]:
                events.append({
                    'timestamp': event.timestamp,
                    'watermark_type': event.watermark_type.value,
                    'queue_ratio': event.queue_ratio,
                    'queue_size': event.queue_size,
                    'memory_usage_bytes': event.memory_usage_bytes,
                    'backpressure_level': event.backpressure_level.value
                })
            return events
    
    def get_backpressure_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent backpressure events"""
        with self._lock:
            events = []
            for event in list(self.backpressure_events)[-limit:]:
                events.append({
                    'timestamp': event.timestamp,
                    'level': event.level.value,
                    'trigger': event.trigger,
                    'queue_ratio': event.queue_ratio,
                    'memory_ratio': event.memory_ratio,
                    'shed_count': event.shed_count,
                    'metadata': event.metadata
                })
            return events
    
    def shutdown(self):
        """Shutdown the buffer"""
        logger.info(f"AdaptiveBuffer '{self.name}' shutting down")
        
        self._monitoring_active = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.info("Waiting for monitoring thread to finish...")
            self._monitor_thread.join(timeout=2.0)
        
        # Final metrics
        final_status = self.get_status()
        logger.info(f"AdaptiveBuffer '{self.name}' final status: {json.dumps(final_status, indent=2)}")
        
        logger.info(f"AdaptiveBuffer '{self.name}' shutdown complete")

# =============================================================================
# Factory Functions
# =============================================================================

def create_adaptive_buffer(config: BufferConfig = None, name: str = "adaptive_buffer") -> AdaptiveBuffer:
    """Create a new AdaptiveBuffer instance"""
    if config is None:
        config = BufferConfig()
    
    return AdaptiveBuffer(config, name)

# =============================================================================
# Testing Functions
# =============================================================================

async def test_adaptive_buffer():
    """Test the adaptive buffer functionality"""
    print("🧪 Testing AdaptiveBuffer...")
    
    config = BufferConfig(
        max_queue_size=100,
        max_memory_bytes=10 * 1024,  # 10KB for testing
        low_watermark=0.2,
        mid_watermark=0.5,
        high_watermark=0.8,
        base_batch_size=10
    )
    
    buffer = AdaptiveBuffer(config, "test_buffer")
    
    # Test normal operation
    print("Testing normal enqueue/dequeue...")
    for i in range(30):
        success = buffer.enqueue(f"item_{i}", size_bytes=100)
        assert success, f"Failed to enqueue item {i}"
    
    items = buffer.dequeue(10)
    assert len(items) == 10, f"Expected 10 items, got {len(items)}"
    
    # Test watermark triggering
    print("Testing watermark triggering...")
    for i in range(70):  # Should trigger high watermark
        buffer.enqueue(f"watermark_item_{i}", size_bytes=100)
    
    status = buffer.get_status()
    assert status['backpressure_active'], "Backpressure should be active"
    
    # Test backpressure events
    bp_events = buffer.get_backpressure_events()
    assert len(bp_events) > 0, "Should have backpressure events"
    
    # Test watermark events
    wm_events = buffer.get_watermark_events()
    assert len(wm_events) > 0, "Should have watermark events"
    
    print(f"Final status: {json.dumps(status, indent=2)}")
    
    buffer.shutdown()
    
    return "AdaptiveBuffer test completed successfully"

if __name__ == "__main__":
    asyncio.run(test_adaptive_buffer())
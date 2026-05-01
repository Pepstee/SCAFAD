"""
SCAFAD Layer 0: Real-Time Stream Processing Pipeline
===================================================

Implements continuous telemetry stream processing with:
- Real-time anomaly detection on streaming telemetry
- Windowed analysis with temporal correlation
- Backpressure handling and flow control
- Stream partitioning and parallel processing
- Adaptive batch sizing based on load

Academic References:
- Stream processing frameworks (Dean et al., MapReduce)
- Temporal window analysis (Li et al., StreamMiner)
- Backpressure algorithms (Akidau et al., Dataflow)
- Real-time anomaly detection (Chandola et al., Anomaly Survey)
"""

import time
import asyncio
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
import weakref

# Import core components
from .app_config import Layer0Config, TelemetryConfig
from .app_telemetry import TelemetryRecord

# Optional performance imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Core Enumerations and Data Structures
# =============================================================================

class StreamState(Enum):
    """Stream processing states"""
    IDLE = "idle"
    PROCESSING = "processing"
    BACKPRESSURE = "backpressure"
    ERROR = "error"
    SHUTDOWN = "shutdown"

class WindowType(Enum):
    """Temporal window types"""
    TUMBLING = "tumbling"      # Non-overlapping fixed windows
    SLIDING = "sliding"        # Overlapping fixed windows
    SESSION = "session"        # Variable windows based on activity
    GLOBAL = "global"          # Single global window

class ProcessingMode(Enum):
    """Stream processing modes"""
    EXACTLY_ONCE = "exactly_once"
    AT_LEAST_ONCE = "at_least_once"
    AT_MOST_ONCE = "at_most_once"

@dataclass
class StreamMetrics:
    """Stream processing performance metrics"""
    records_processed: int = 0
    records_per_second: float = 0.0
    processing_latency_ms: float = 0.0
    backpressure_events: int = 0
    error_count: int = 0
    memory_usage_mb: float = 0.0
    cpu_utilization: float = 0.0
    queue_depth: int = 0
    last_update: float = field(default_factory=time.time)

@dataclass
class WindowConfiguration:
    """Temporal window configuration"""
    window_type: WindowType
    window_size_ms: int
    slide_interval_ms: Optional[int] = None  # For sliding windows
    session_timeout_ms: Optional[int] = None  # For session windows
    max_lateness_ms: int = 5000
    watermark_interval_ms: int = 1000

@dataclass
class StreamRecord:
    """Individual stream record with metadata"""
    telemetry: TelemetryRecord
    timestamp_ms: int
    partition_key: str
    sequence_number: int
    processing_time_ms: int
    watermark_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WindowResult:
    """Result of window processing"""
    window_id: str
    window_start_ms: int
    window_end_ms: int
    record_count: int
    anomaly_results: List[Dict[str, Any]]
    processing_metrics: StreamMetrics
    window_metadata: Dict[str, Any] = field(default_factory=dict)

# =============================================================================
# Stream Processing Pipeline Implementation
# =============================================================================

class StreamProcessor:
    """
    Real-time stream processing pipeline for continuous telemetry analysis
    
    Key features:
    - Asynchronous stream ingestion with backpressure handling
    - Windowed processing with configurable temporal windows
    - Parallel processing with adaptive worker pool
    - Real-time anomaly detection integration
    - Comprehensive metrics and monitoring
    """
    
    def __init__(self, config: Layer0Config):
        self.config = config
        
        # Stream configuration
        self.processing_mode = ProcessingMode.AT_LEAST_ONCE
        self.max_queue_size = 10000
        self.batch_size = 100
        self.worker_pool_size = 4
        self.max_processing_latency_ms = 1000
        
        # Window configuration
        self.window_config = WindowConfiguration(
            window_type=WindowType.TUMBLING,
            window_size_ms=30000,  # 30 second windows
            watermark_interval_ms=1000
        )
        
        # Stream state
        self.state = StreamState.IDLE
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # Processing queues
        self.ingestion_queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.processing_queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.output_queue = asyncio.Queue(maxsize=self.max_queue_size)
        
        # Window management
        self.active_windows: Dict[str, List[StreamRecord]] = {}
        self.window_watermarks: Dict[str, int] = {}
        self.completed_windows: deque = deque(maxlen=1000)
        
        # Worker management
        self.worker_pool = ThreadPoolExecutor(max_workers=self.worker_pool_size)
        self.processing_tasks: List[asyncio.Task] = []
        
        # Metrics and monitoring
        self.stream_metrics = StreamMetrics()
        self.partition_metrics: Dict[str, StreamMetrics] = defaultdict(StreamMetrics)
        self.metrics_lock = threading.Lock()
        
        # Event handlers
        self.anomaly_handlers: List[Callable] = []
        self.error_handlers: List[Callable] = []
        self.watermark_handlers: List[Callable] = []
        
        # Performance optimization
        self.adaptive_batching = True
        self.dynamic_worker_scaling = True
        self.backpressure_threshold = 0.8  # 80% queue capacity
        
        # Sequence tracking
        self.sequence_counter = 0
        self.sequence_lock = threading.Lock()
        
        logger.info(f"StreamProcessor initialized with {self.worker_pool_size} workers")
    
    async def start(self) -> bool:
        """
        Start the stream processing pipeline
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("StreamProcessor is already running")
            return True
        
        try:
            logger.info("Starting StreamProcessor pipeline")
            self.is_running = True
            self.state = StreamState.PROCESSING
            self.shutdown_event.clear()
            
            # Start processing tasks
            await self._start_processing_tasks()
            
            # Start metrics collection
            asyncio.create_task(self._metrics_collection_loop())
            
            # Start watermark generation
            asyncio.create_task(self._watermark_generation_loop())
            
            logger.info("StreamProcessor pipeline started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start StreamProcessor: {e}")
            self.is_running = False
            self.state = StreamState.ERROR
            return False
    
    async def stop(self, timeout_ms: int = 30000) -> bool:
        """
        Stop the stream processing pipeline gracefully
        
        Args:
            timeout_ms: Maximum time to wait for shutdown
            
        Returns:
            True if stopped successfully, False if timeout
        """
        if not self.is_running:
            return True
        
        logger.info("Stopping StreamProcessor pipeline")
        
        try:
            # Signal shutdown
            self.shutdown_event.set()
            self.state = StreamState.SHUTDOWN
            
            # Wait for processing tasks to complete
            if self.processing_tasks:
                await asyncio.wait_for(
                    asyncio.gather(*self.processing_tasks, return_exceptions=True),
                    timeout=timeout_ms / 1000
                )
            
            # Shutdown worker pool
            self.worker_pool.shutdown(wait=True, timeout=timeout_ms / 1000)
            
            # Process remaining queued items
            await self._drain_queues()
            
            self.is_running = False
            self.state = StreamState.IDLE
            
            logger.info("StreamProcessor pipeline stopped successfully")
            return True
            
        except asyncio.TimeoutError:
            logger.warning("StreamProcessor shutdown timed out")
            self.is_running = False
            self.state = StreamState.ERROR
            return False
        except Exception as e:
            logger.error(f"Error during StreamProcessor shutdown: {e}")
            self.is_running = False
            self.state = StreamState.ERROR
            return False
    
    async def ingest_telemetry(self, telemetry: TelemetryRecord) -> bool:
        """
        Ingest a telemetry record into the stream
        
        Args:
            telemetry: Telemetry record to process
            
        Returns:
            True if ingested successfully, False if backpressure
        """
        if not self.is_running:
            logger.warning("Cannot ingest telemetry - StreamProcessor not running")
            return False
        
        try:
            # Check for backpressure
            if self._is_backpressure_active():
                self.state = StreamState.BACKPRESSURE
                logger.debug("Backpressure active - dropping telemetry record")
                return False
            
            # Create stream record
            stream_record = await self._create_stream_record(telemetry)
            
            # Add to ingestion queue
            await asyncio.wait_for(
                self.ingestion_queue.put(stream_record),
                timeout=1.0  # 1 second timeout
            )
            
            # Update metrics
            with self.metrics_lock:
                self.stream_metrics.records_processed += 1
            
            return True
            
        except asyncio.TimeoutError:
            logger.debug("Ingestion queue timeout - activating backpressure")
            self.state = StreamState.BACKPRESSURE
            return False
        except Exception as e:
            logger.error(f"Error ingesting telemetry: {e}")
            return False
    
    async def ingest_telemetry_batch(self, telemetry_batch: List[TelemetryRecord]) -> int:
        """
        Ingest a batch of telemetry records
        
        Args:
            telemetry_batch: List of telemetry records
            
        Returns:
            Number of records successfully ingested
        """
        if not telemetry_batch:
            return 0
        
        successful_ingestions = 0
        
        for telemetry in telemetry_batch:
            if await self.ingest_telemetry(telemetry):
                successful_ingestions += 1
            else:
                # Stop on first backpressure event
                break
        
        return successful_ingestions
    
    async def get_processing_results(self, timeout_ms: int = 1000) -> Optional[WindowResult]:
        """
        Get the next processing result from output queue
        
        Args:
            timeout_ms: Timeout for getting result
            
        Returns:
            WindowResult if available, None if timeout or empty
        """
        try:
            result = await asyncio.wait_for(
                self.output_queue.get(),
                timeout=timeout_ms / 1000
            )
            return result
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error getting processing result: {e}")
            return None
    
    def register_anomaly_handler(self, handler: Callable[[List[Dict[str, Any]]], None]):
        """Register handler for anomaly detection results"""
        self.anomaly_handlers.append(handler)
    
    def register_error_handler(self, handler: Callable[[Exception], None]):
        """Register handler for processing errors"""
        self.error_handlers.append(handler)
    
    def register_watermark_handler(self, handler: Callable[[int], None]):
        """Register handler for watermark updates"""
        self.watermark_handlers.append(handler)
    
    def get_stream_metrics(self) -> StreamMetrics:
        """Get current stream processing metrics"""
        with self.metrics_lock:
            return StreamMetrics(
                records_processed=self.stream_metrics.records_processed,
                records_per_second=self.stream_metrics.records_per_second,
                processing_latency_ms=self.stream_metrics.processing_latency_ms,
                backpressure_events=self.stream_metrics.backpressure_events,
                error_count=self.stream_metrics.error_count,
                memory_usage_mb=self.stream_metrics.memory_usage_mb,
                cpu_utilization=self.stream_metrics.cpu_utilization,
                queue_depth=self.ingestion_queue.qsize(),
                last_update=time.time()
            )
    
    def get_partition_metrics(self) -> Dict[str, StreamMetrics]:
        """Get per-partition processing metrics"""
        with self.metrics_lock:
            return dict(self.partition_metrics)
    
    # =============================================================================
    # Internal Processing Methods
    # =============================================================================
    
    async def _start_processing_tasks(self):
        """Start all processing tasks"""
        # Ingestion processing task
        self.processing_tasks.append(
            asyncio.create_task(self._ingestion_processing_loop())
        )
        
        # Window processing tasks (multiple for parallelism)
        for i in range(self.worker_pool_size):
            self.processing_tasks.append(
                asyncio.create_task(self._window_processing_loop(worker_id=i))
            )
        
        # Output processing task
        self.processing_tasks.append(
            asyncio.create_task(self._output_processing_loop())
        )
        
        # Adaptive batch sizing task
        if self.adaptive_batching:
            self.processing_tasks.append(
                asyncio.create_task(self._adaptive_batching_loop())
            )
    
    async def _ingestion_processing_loop(self):
        """Main ingestion processing loop"""
        logger.debug("Starting ingestion processing loop")
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Get record from ingestion queue
                    stream_record = await asyncio.wait_for(
                        self.ingestion_queue.get(),
                        timeout=1.0
                    )
                    
                    # Assign to appropriate window
                    await self._assign_to_window(stream_record)
                    
                    # Add to processing queue
                    await self.processing_queue.put(stream_record)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in ingestion processing loop: {e}")
                    await self._handle_processing_error(e)
        
        except asyncio.CancelledError:
            logger.debug("Ingestion processing loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in ingestion processing loop: {e}")
    
    async def _window_processing_loop(self, worker_id: int):
        """Window processing loop for a specific worker"""
        logger.debug(f"Starting window processing loop for worker {worker_id}")
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Get batch of records for processing
                    batch = await self._get_processing_batch()
                    
                    if not batch:
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Process batch in window context
                    results = await self._process_window_batch(batch, worker_id)
                    
                    # Send results to output queue
                    for result in results:
                        await self.output_queue.put(result)
                    
                    # Update processing metrics
                    await self._update_processing_metrics(len(batch), worker_id)
                    
                except Exception as e:
                    logger.error(f"Error in window processing loop (worker {worker_id}): {e}")
                    await self._handle_processing_error(e)
        
        except asyncio.CancelledError:
            logger.debug(f"Window processing loop cancelled for worker {worker_id}")
        except Exception as e:
            logger.error(f"Fatal error in window processing loop (worker {worker_id}): {e}")
    
    async def _output_processing_loop(self):
        """Output processing and result handling loop"""
        logger.debug("Starting output processing loop")
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Get result from output queue
                    window_result = await asyncio.wait_for(
                        self.output_queue.get(),
                        timeout=1.0
                    )
                    
                    # Process anomaly results
                    if window_result.anomaly_results:
                        await self._handle_anomaly_results(window_result.anomaly_results)
                    
                    # Store completed window
                    self.completed_windows.append(window_result)
                    
                    # Clean up old windows
                    await self._cleanup_completed_windows(window_result)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in output processing loop: {e}")
                    await self._handle_processing_error(e)
        
        except asyncio.CancelledError:
            logger.debug("Output processing loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in output processing loop: {e}")
    
    async def _create_stream_record(self, telemetry: TelemetryRecord) -> StreamRecord:
        """Create a stream record from telemetry"""
        current_time = int(time.time() * 1000)
        
        # Generate partition key based on telemetry characteristics
        partition_key = self._generate_partition_key(telemetry)
        
        # Get next sequence number
        with self.sequence_lock:
            sequence_number = self.sequence_counter
            self.sequence_counter += 1
        
        return StreamRecord(
            telemetry=telemetry,
            timestamp_ms=current_time,
            partition_key=partition_key,
            sequence_number=sequence_number,
            processing_time_ms=current_time,
            watermark_ms=current_time,
            metadata={
                'ingestion_time': current_time,
                'source_component': 'stream_processor'
            }
        )
    
    def _generate_partition_key(self, telemetry: TelemetryRecord) -> str:
        """Generate partition key for load balancing"""
        # Use function_id for partitioning to group related telemetry
        if hasattr(telemetry, 'function_id') and telemetry.function_id:
            base_key = str(telemetry.function_id)
        else:
            base_key = "default"
        
        # Hash to distribute evenly
        hash_value = hashlib.md5(base_key.encode()).hexdigest()
        partition_id = int(hash_value[:8], 16) % self.worker_pool_size
        
        return f"partition_{partition_id}"
    
    async def _assign_to_window(self, stream_record: StreamRecord):
        """Assign stream record to appropriate temporal window"""
        window_id = self._calculate_window_id(stream_record)
        
        if window_id not in self.active_windows:
            self.active_windows[window_id] = []
            self.window_watermarks[window_id] = stream_record.timestamp_ms
        
        self.active_windows[window_id].append(stream_record)
        
        # Update watermark
        self.window_watermarks[window_id] = max(
            self.window_watermarks[window_id],
            stream_record.watermark_ms
        )
    
    def _calculate_window_id(self, stream_record: StreamRecord) -> str:
        """Calculate window ID based on timestamp and window configuration"""
        timestamp = stream_record.timestamp_ms
        
        if self.window_config.window_type == WindowType.TUMBLING:
            window_start = (timestamp // self.window_config.window_size_ms) * self.window_config.window_size_ms
            return f"tumbling_{window_start}_{stream_record.partition_key}"
        
        elif self.window_config.window_type == WindowType.SLIDING:
            slide_interval = self.window_config.slide_interval_ms or self.window_config.window_size_ms
            window_start = (timestamp // slide_interval) * slide_interval
            return f"sliding_{window_start}_{stream_record.partition_key}"
        
        elif self.window_config.window_type == WindowType.SESSION:
            # Session windows require more complex logic - simplified here
            return f"session_{stream_record.partition_key}_{timestamp}"
        
        else:  # GLOBAL
            return f"global_{stream_record.partition_key}"
    
    async def _get_processing_batch(self) -> List[StreamRecord]:
        """Get a batch of records for processing"""
        batch = []
        batch_timeout = 0.1  # 100ms batch timeout
        
        try:
            # Get first record (blocking)
            first_record = await asyncio.wait_for(
                self.processing_queue.get(),
                timeout=batch_timeout
            )
            batch.append(first_record)
            
            # Get additional records up to batch size (non-blocking)
            while len(batch) < self.batch_size:
                try:
                    record = await asyncio.wait_for(
                        self.processing_queue.get(),
                        timeout=0.001  # 1ms timeout for additional records
                    )
                    batch.append(record)
                except asyncio.TimeoutError:
                    break
        
        except asyncio.TimeoutError:
            # No records available
            pass
        
        return batch
    
    async def _process_window_batch(self, batch: List[StreamRecord], worker_id: int) -> List[WindowResult]:
        """Process a batch of records within their window context"""
        if not batch:
            return []
        
        results = []
        start_time = time.time()
        
        try:
            # Group records by window
            window_groups = defaultdict(list)
            for record in batch:
                window_id = self._calculate_window_id(record)
                window_groups[window_id].append(record)
            
            # Process each window group
            for window_id, window_records in window_groups.items():
                try:
                    # Check if window is ready for processing
                    if self._is_window_ready(window_id, window_records):
                        result = await self._process_window_records(window_id, window_records, worker_id)
                        if result:
                            results.append(result)
                
                except Exception as e:
                    logger.error(f"Error processing window {window_id}: {e}")
            
            # Update processing metrics
            processing_time = (time.time() - start_time) * 1000
            with self.metrics_lock:
                self.stream_metrics.processing_latency_ms = (
                    0.9 * self.stream_metrics.processing_latency_ms + 0.1 * processing_time
                )
        
        except Exception as e:
            logger.error(f"Error in window batch processing: {e}")
            await self._handle_processing_error(e)
        
        return results
    
    def _is_window_ready(self, window_id: str, window_records: List[StreamRecord]) -> bool:
        """Check if window is ready for processing based on watermarks"""
        if not window_records:
            return False
        
        # Get window bounds
        window_start, window_end = self._get_window_bounds(window_id)
        
        # Check if watermark has passed window end + max lateness
        current_watermark = max(record.watermark_ms for record in window_records)
        window_deadline = window_end + self.window_config.max_lateness_ms
        
        return current_watermark >= window_deadline
    
    def _get_window_bounds(self, window_id: str) -> Tuple[int, int]:
        """Get window start and end times from window ID"""
        parts = window_id.split('_')
        
        if parts[0] == 'tumbling':
            window_start = int(parts[1])
            window_end = window_start + self.window_config.window_size_ms
            return window_start, window_end
        
        elif parts[0] == 'sliding':
            window_start = int(parts[1])
            window_end = window_start + self.window_config.window_size_ms
            return window_start, window_end
        
        else:
            # Default bounds
            current_time = int(time.time() * 1000)
            return current_time - self.window_config.window_size_ms, current_time
    
    async def _process_window_records(self, window_id: str, 
                                    window_records: List[StreamRecord], 
                                    worker_id: int) -> Optional[WindowResult]:
        """Process records within a specific window"""
        if not window_records:
            return None
        
        start_time = time.time()
        
        try:
            # Extract telemetry records
            telemetry_records = [record.telemetry for record in window_records]
            
            # Perform anomaly detection on window batch
            anomaly_results = await self._detect_anomalies_batch(telemetry_records, window_id)
            
            # Calculate window bounds
            window_start, window_end = self._get_window_bounds(window_id)
            
            # Create processing metrics for this window
            processing_time = (time.time() - start_time) * 1000
            window_metrics = StreamMetrics(
                records_processed=len(window_records),
                processing_latency_ms=processing_time,
                last_update=time.time()
            )
            
            # Create window result
            result = WindowResult(
                window_id=window_id,
                window_start_ms=window_start,
                window_end_ms=window_end,
                record_count=len(window_records),
                anomaly_results=anomaly_results,
                processing_metrics=window_metrics,
                window_metadata={
                    'worker_id': worker_id,
                    'processing_time_ms': processing_time,
                    'earliest_record': min(r.timestamp_ms for r in window_records),
                    'latest_record': max(r.timestamp_ms for r in window_records),
                    'partition_keys': list(set(r.partition_key for r in window_records))
                }
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing window {window_id}: {e}")
            return None
    
    async def _detect_anomalies_batch(self, telemetry_records: List[TelemetryRecord], 
                                    window_id: str) -> List[Dict[str, Any]]:
        """Detect anomalies in a batch of telemetry records"""
        try:
            # Import anomaly detection engine
            from .layer0_core import AnomalyDetectionEngine
            
            # Create engine instance (could be cached/reused)
            engine = AnomalyDetectionEngine(self.config)
            
            # Process each record
            anomaly_results = []
            for telemetry in telemetry_records:
                try:
                    result = engine.detect_anomalies(telemetry)
                    
                    # Convert to serializable format
                    anomaly_data = {
                        'telemetry_id': getattr(telemetry, 'telemetry_id', 'unknown'),
                        'anomaly_score': result.overall_confidence,
                        'anomaly_types': [a.anomaly_type for a in result.detections if a.confidence > 0.5],
                        'detection_details': [
                            {
                                'type': detection.anomaly_type,
                                'confidence': detection.confidence,
                                'algorithm': detection.algorithm_name
                            }
                            for detection in result.detections[:5]  # Top 5 detections
                        ],
                        'window_id': window_id,
                        'processing_timestamp': time.time()
                    }
                    
                    anomaly_results.append(anomaly_data)
                
                except Exception as e:
                    logger.error(f"Error detecting anomalies for telemetry record: {e}")
            
            return anomaly_results
        
        except Exception as e:
            logger.error(f"Error in batch anomaly detection: {e}")
            return []
    
    def _is_backpressure_active(self) -> bool:
        """Check if backpressure should be activated"""
        ingestion_ratio = self.ingestion_queue.qsize() / self.max_queue_size
        processing_ratio = self.processing_queue.qsize() / self.max_queue_size
        
        return (ingestion_ratio > self.backpressure_threshold or 
                processing_ratio > self.backpressure_threshold)
    
    async def _handle_anomaly_results(self, anomaly_results: List[Dict[str, Any]]):
        """Handle detected anomaly results"""
        if not anomaly_results:
            return
        
        # Call registered anomaly handlers
        for handler in self.anomaly_handlers:
            try:
                handler(anomaly_results)
            except Exception as e:
                logger.error(f"Error in anomaly handler: {e}")
    
    async def _handle_processing_error(self, error: Exception):
        """Handle processing errors"""
        with self.metrics_lock:
            self.stream_metrics.error_count += 1
        
        # Call registered error handlers
        for handler in self.error_handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(f"Error in error handler: {e}")
    
    async def _update_processing_metrics(self, processed_count: int, worker_id: int):
        """Update processing performance metrics"""
        current_time = time.time()
        
        with self.metrics_lock:
            # Update global metrics
            self.stream_metrics.records_processed += processed_count
            
            # Calculate records per second
            time_delta = current_time - self.stream_metrics.last_update
            if time_delta > 0:
                self.stream_metrics.records_per_second = (
                    0.8 * self.stream_metrics.records_per_second + 
                    0.2 * (processed_count / time_delta)
                )
            
            self.stream_metrics.last_update = current_time
    
    async def _metrics_collection_loop(self):
        """Collect and update stream metrics periodically"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(5.0)  # Update every 5 seconds
                
                with self.metrics_lock:
                    # Update queue depths
                    self.stream_metrics.queue_depth = self.ingestion_queue.qsize()
                    
                    # Update memory usage (simplified)
                    self.stream_metrics.memory_usage_mb = len(self.active_windows) * 0.1
                    
                    # Update CPU utilization (simplified)
                    self.stream_metrics.cpu_utilization = min(95.0, self.stream_metrics.records_per_second / 10.0)
        
        except asyncio.CancelledError:
            logger.debug("Metrics collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in metrics collection loop: {e}")
    
    async def _watermark_generation_loop(self):
        """Generate and advance watermarks periodically"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(self.window_config.watermark_interval_ms / 1000.0)
                
                current_time = int(time.time() * 1000)
                
                # Update watermarks for all active windows
                for window_id in list(self.window_watermarks.keys()):
                    self.window_watermarks[window_id] = current_time
                
                # Call watermark handlers
                for handler in self.watermark_handlers:
                    try:
                        handler(current_time)
                    except Exception as e:
                        logger.error(f"Error in watermark handler: {e}")
        
        except asyncio.CancelledError:
            logger.debug("Watermark generation loop cancelled")
        except Exception as e:
            logger.error(f"Error in watermark generation loop: {e}")
    
    async def _adaptive_batching_loop(self):
        """Dynamically adjust batch size based on performance"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(10.0)  # Adjust every 10 seconds
                
                # Analyze performance metrics
                if self.stream_metrics.processing_latency_ms > self.max_processing_latency_ms:
                    # Reduce batch size to improve latency
                    self.batch_size = max(10, int(self.batch_size * 0.8))
                    logger.debug(f"Reduced batch size to {self.batch_size} due to high latency")
                
                elif (self.stream_metrics.processing_latency_ms < self.max_processing_latency_ms / 2 and
                      self.stream_metrics.records_per_second > 0):
                    # Increase batch size to improve throughput
                    self.batch_size = min(1000, int(self.batch_size * 1.2))
                    logger.debug(f"Increased batch size to {self.batch_size} for better throughput")
        
        except asyncio.CancelledError:
            logger.debug("Adaptive batching loop cancelled")
        except Exception as e:
            logger.error(f"Error in adaptive batching loop: {e}")
    
    async def _cleanup_completed_windows(self, latest_result: WindowResult):
        """Clean up old completed windows to manage memory"""
        # Remove windows older than 1 hour
        cutoff_time = latest_result.window_end_ms - (60 * 60 * 1000)
        
        windows_to_remove = []
        for window_id in self.active_windows:
            window_start, _ = self._get_window_bounds(window_id)
            if window_start < cutoff_time:
                windows_to_remove.append(window_id)
        
        for window_id in windows_to_remove:
            self.active_windows.pop(window_id, None)
            self.window_watermarks.pop(window_id, None)
    
    async def _drain_queues(self):
        """Drain remaining items from queues during shutdown"""
        try:
            # Drain ingestion queue
            while not self.ingestion_queue.empty():
                try:
                    self.ingestion_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            # Drain processing queue
            while not self.processing_queue.empty():
                try:
                    self.processing_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            # Drain output queue
            while not self.output_queue.empty():
                try:
                    result = self.output_queue.get_nowait()
                    # Process any final anomaly results
                    if result.anomaly_results:
                        await self._handle_anomaly_results(result.anomaly_results)
                except asyncio.QueueEmpty:
                    break
        
        except Exception as e:
            logger.error(f"Error draining queues: {e}")

# =============================================================================
# Factory Functions and Utilities
# =============================================================================

def create_stream_processor(config: Layer0Config = None) -> StreamProcessor:
    """Create a new StreamProcessor instance"""
    if config is None:
        from .app_config import get_default_config
        config = get_default_config()
    
    return StreamProcessor(config)

async def test_stream_processor():
    """Test the StreamProcessor functionality"""
    from .app_config import create_testing_config
    from utils.test_data_generator import generate_test_payloads
    
    config = create_testing_config()
    processor = StreamProcessor(config)
    
    print("Testing StreamProcessor...")
    
    # Start processor
    started = await processor.start()
    if not started:
        print("❌ Failed to start processor")
        return
    
    print("✅ Processor started")
    
    # Generate test telemetry
    test_payloads = generate_test_payloads(50)
    
    # Convert to telemetry records
    telemetry_records = []
    for payload in test_payloads:
        from .app_telemetry import TelemetryRecord
        telemetry = TelemetryRecord(
            telemetry_id=payload.get('telemetry_id', 'test'),
            function_id=payload.get('function_id', 'test-function'),
            execution_phase=payload.get('execution_phase', 'invoke'),
            anomaly_type=payload.get('anomaly_type', 'benign'),
            duration=payload.get('duration', 100.0),
            memory_spike_kb=payload.get('memory_spike_kb', 1024),
            cpu_utilization=payload.get('cpu_utilization', 50.0),
            custom_fields=payload.get('custom_fields', {})
        )
        telemetry_records.append(telemetry)
    
    # Ingest telemetry
    print(f"Ingesting {len(telemetry_records)} telemetry records...")
    
    ingested_count = await processor.ingest_telemetry_batch(telemetry_records)
    print(f"✅ Ingested {ingested_count} records")
    
    # Wait for processing results
    print("Waiting for processing results...")
    results_count = 0
    
    for _ in range(10):  # Wait up to 10 seconds
        result = await processor.get_processing_results(timeout_ms=1000)
        if result:
            results_count += 1
            print(f"📊 Window result: {result.record_count} records, "
                  f"{len(result.anomaly_results)} anomalies detected")
        else:
            break
    
    # Get metrics
    metrics = processor.get_stream_metrics()
    print(f"📈 Stream metrics:")
    print(f"  Records processed: {metrics.records_processed}")
    print(f"  Records/sec: {metrics.records_per_second:.2f}")
    print(f"  Processing latency: {metrics.processing_latency_ms:.2f}ms")
    print(f"  Queue depth: {metrics.queue_depth}")
    print(f"  Error count: {metrics.error_count}")
    
    # Stop processor
    stopped = await processor.stop()
    if stopped:
        print("✅ Processor stopped cleanly")
    else:
        print("⚠️ Processor shutdown timed out")

if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_stream_processor())
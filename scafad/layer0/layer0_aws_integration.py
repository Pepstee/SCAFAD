"""
SCAFAD Layer 0: AWS Production Integration
==========================================

Native AWS Lambda integration with:
- CloudWatch Logs and Metrics integration
- AWS X-Ray distributed tracing
- Lambda runtime API optimization
- AWS Systems Manager parameter integration
- CloudFormation deployment templates
- Performance insights and monitoring

Academic References:
- Serverless computing architectures (Castro et al.)
- AWS Lambda performance optimization (Baldini et al.)
- Distributed tracing systems (Fonseca et al.)
- Cloud-native monitoring (Chen et al.)
"""

import os
import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor
import gzip
import uuid

# AWS SDK imports with graceful fallbacks
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None

# AWS X-Ray imports
try:
    from aws_xray_sdk.core import xray_recorder, patch_all
    from aws_xray_sdk.core.context import Context
    from aws_xray_sdk.core.sampling import SamplingRule
    HAS_XRAY = True
except ImportError:
    HAS_XRAY = False
    xray_recorder = None  # type: ignore[assignment]
    patch_all = None  # type: ignore[assignment]


def _xray_capture(name: str):
    """Decorator factory — delegates to xray_recorder.capture() when the SDK
    is present, otherwise returns an identity decorator so the decorated method
    is unchanged at runtime.

    Using this wrapper instead of @xray_recorder.capture() directly avoids a
    NameError / AttributeError when aws_xray_sdk is not installed.
    """
    if HAS_XRAY and xray_recorder is not None:
        return xray_recorder.capture(name)

    def _noop(fn):
        return fn

    return _noop


# Lambda runtime imports
try:
    import awslambdaric
    HAS_LAMBDA_RIC = True
except ImportError:
    HAS_LAMBDA_RIC = False

# Core components
from .app_config import Layer0Config
from .app_telemetry import TelemetryRecord

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# AWS Configuration and Data Structures
# =============================================================================

class AWSServiceType(Enum):
    """AWS service types for integration"""
    CLOUDWATCH_LOGS = "cloudwatch_logs"
    CLOUDWATCH_METRICS = "cloudwatch_metrics"
    XRAY = "xray"
    LAMBDA = "lambda"
    SSM = "ssm"
    S3 = "s3"
    DYNAMODB = "dynamodb"

class IntegrationStatus(Enum):
    """AWS integration status"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"

@dataclass
class AWSCredentials:
    """AWS credentials configuration"""
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    role_arn: Optional[str] = None
    region: str = "us-east-1"
    profile_name: Optional[str] = None

@dataclass
class CloudWatchConfig:
    """CloudWatch integration configuration"""
    log_group_name: str = "/aws/lambda/scafad-layer0"
    log_stream_prefix: str = "layer0"
    metrics_namespace: str = "SCAFAD/Layer0"
    retention_days: int = 14
    batch_size: int = 100
    flush_interval_ms: int = 5000
    compression_enabled: bool = True

@dataclass
class XRayConfig:
    """X-Ray tracing configuration"""
    tracing_enabled: bool = True
    sampling_rate: float = 0.1
    service_name: str = "scafad-layer0"
    custom_annotations: Dict[str, str] = field(default_factory=dict)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    plugins: List[str] = field(default_factory=lambda: ["EC2Plugin", "ECSPlugin"])

@dataclass
class LambdaConfig:
    """Lambda runtime configuration"""
    function_name: str = "scafad-layer0-detector"
    runtime_api_optimization: bool = True
    cold_start_optimization: bool = True
    memory_optimization: bool = True
    timeout_ms: int = 300000  # 5 minutes
    reserved_concurrency: Optional[int] = None

@dataclass
class AWSIntegrationMetrics:
    """AWS integration performance metrics"""
    cloudwatch_requests: int = 0
    cloudwatch_failures: int = 0
    xray_traces: int = 0
    xray_errors: int = 0
    lambda_invocations: int = 0
    lambda_cold_starts: int = 0
    api_latency_ms: float = 0.0
    cost_estimate_usd: float = 0.0
    last_update: float = field(default_factory=time.time)

# =============================================================================
# AWS Integration Manager
# =============================================================================

class AWSIntegrationManager:
    """
    Manages AWS service integrations for production deployment
    
    Features:
    - CloudWatch Logs and Metrics integration
    - X-Ray distributed tracing
    - Lambda runtime optimization
    - Cost monitoring and optimization
    - Error handling and retry logic
    """
    
    def __init__(self, config: Layer0Config, aws_credentials: Optional[AWSCredentials] = None):
        self.config = config
        self.aws_credentials = aws_credentials or self._detect_aws_credentials()
        
        # Service configurations
        self.cloudwatch_config = CloudWatchConfig()
        self.xray_config = XRayConfig()
        self.lambda_config = LambdaConfig()
        
        # AWS clients
        self.aws_clients: Dict[AWSServiceType, Any] = {}
        self.client_status: Dict[AWSServiceType, IntegrationStatus] = {}
        
        # Integration state
        self.integration_active = False
        self.metrics = AWSIntegrationMetrics()
        self.metrics_lock = threading.Lock()
        
        # Background processing
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="aws-integration")
        self.log_buffer: List[Dict[str, Any]] = []
        self.metrics_buffer: List[Dict[str, Any]] = []
        self.buffer_lock = threading.Lock()
        
        # Async tasks
        self.background_tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
        
        logger.info("AWSIntegrationManager initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize AWS service integrations
        
        Returns:
            True if initialization successful, False otherwise
        """
        if not HAS_BOTO3:
            logger.warning("boto3 not available - AWS integration disabled")
            return False
        
        try:
            logger.info("Initializing AWS service integrations")
            
            # Initialize AWS clients
            await self._initialize_aws_clients()
            
            # Configure X-Ray tracing
            if HAS_XRAY and self.xray_config.tracing_enabled:
                await self._initialize_xray_tracing()
            
            # Start background processing tasks
            await self._start_background_tasks()
            
            self.integration_active = True
            logger.info("AWS service integrations initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS integrations: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """
        Shutdown AWS integrations gracefully
        
        Returns:
            True if shutdown successful, False otherwise
        """
        try:
            logger.info("Shutting down AWS integrations")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Wait for background tasks
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            # Flush any remaining data
            await self._flush_all_buffers()
            
            # Shutdown executor
            self.executor.shutdown(wait=True, timeout=30)
            
            self.integration_active = False
            logger.info("AWS integrations shut down successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during AWS integration shutdown: {e}")
            return False
    
    # =============================================================================
    # CloudWatch Integration
    # =============================================================================
    
    async def log_telemetry_to_cloudwatch(self, telemetry: TelemetryRecord, 
                                        anomaly_results: Optional[List[Dict[str, Any]]] = None):
        """
        Log telemetry data to CloudWatch Logs
        
        Args:
            telemetry: Telemetry record to log
            anomaly_results: Optional anomaly detection results
        """
        if not self._is_service_active(AWSServiceType.CLOUDWATCH_LOGS):
            return
        
        try:
            # Create log entry
            log_entry = {
                'timestamp': int(time.time() * 1000),
                'level': 'INFO',
                'source': 'scafad-layer0',
                'telemetry_id': getattr(telemetry, 'telemetry_id', 'unknown'),
                'function_id': getattr(telemetry, 'function_id', 'unknown'),
                'execution_phase': getattr(telemetry, 'execution_phase', 'unknown'),
                'anomaly_type': getattr(telemetry, 'anomaly_type', 'unknown'),
                'duration_ms': getattr(telemetry, 'duration', 0.0),
                'memory_spike_kb': getattr(telemetry, 'memory_spike_kb', 0),
                'cpu_utilization': getattr(telemetry, 'cpu_utilization', 0.0)
            }
            
            # Add anomaly results if provided
            if anomaly_results:
                log_entry['anomaly_results'] = anomaly_results
            
            # Add to buffer for batch processing
            with self.buffer_lock:
                self.log_buffer.append(log_entry)
            
        except Exception as e:
            logger.error(f"Error logging telemetry to CloudWatch: {e}")
    
    async def publish_metrics_to_cloudwatch(self, metrics_data: Dict[str, float]):
        """
        Publish custom metrics to CloudWatch Metrics
        
        Args:
            metrics_data: Dictionary of metric names and values
        """
        if not self._is_service_active(AWSServiceType.CLOUDWATCH_METRICS):
            return
        
        try:
            current_time = time.time()
            
            # Create metric entries
            for metric_name, value in metrics_data.items():
                metric_entry = {
                    'MetricName': metric_name,
                    'Value': float(value),
                    'Unit': 'Count',
                    'Timestamp': current_time,
                    'Dimensions': [
                        {
                            'Name': 'FunctionName',
                            'Value': self.lambda_config.function_name
                        },
                        {
                            'Name': 'Component',
                            'Value': 'Layer0'
                        }
                    ]
                }
                
                with self.buffer_lock:
                    self.metrics_buffer.append(metric_entry)
            
        except Exception as e:
            logger.error(f"Error publishing metrics to CloudWatch: {e}")
    
    async def _flush_cloudwatch_logs(self):
        """Flush log buffer to CloudWatch Logs"""
        if not self.log_buffer:
            return
        
        try:
            cloudwatch_logs = self.aws_clients.get(AWSServiceType.CLOUDWATCH_LOGS)
            if not cloudwatch_logs:
                return
            
            # Get log entries to flush
            with self.buffer_lock:
                entries_to_flush = self.log_buffer[:self.cloudwatch_config.batch_size]
                self.log_buffer = self.log_buffer[self.cloudwatch_config.batch_size:]
            
            if not entries_to_flush:
                return
            
            # Create log stream if needed
            log_stream_name = f"{self.cloudwatch_config.log_stream_prefix}-{int(time.time())}"
            
            try:
                cloudwatch_logs.create_log_stream(
                    logGroupName=self.cloudwatch_config.log_group_name,
                    logStreamName=log_stream_name
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
            
            # Format log events
            log_events = []
            for entry in entries_to_flush:
                message = json.dumps(entry)
                if self.cloudwatch_config.compression_enabled and len(message) > 1024:
                    message = gzip.compress(message.encode()).decode('latin-1')
                
                log_events.append({
                    'timestamp': entry['timestamp'],
                    'message': message
                })
            
            # Send log events
            cloudwatch_logs.put_log_events(
                logGroupName=self.cloudwatch_config.log_group_name,
                logStreamName=log_stream_name,
                logEvents=log_events
            )
            
            # Update metrics
            with self.metrics_lock:
                self.metrics.cloudwatch_requests += 1
            
        except Exception as e:
            logger.error(f"Error flushing CloudWatch logs: {e}")
            with self.metrics_lock:
                self.metrics.cloudwatch_failures += 1
    
    async def _flush_cloudwatch_metrics(self):
        """Flush metrics buffer to CloudWatch Metrics"""
        if not self.metrics_buffer:
            return
        
        try:
            cloudwatch_metrics = self.aws_clients.get(AWSServiceType.CLOUDWATCH_METRICS)
            if not cloudwatch_metrics:
                return
            
            # Get metrics to flush
            with self.buffer_lock:
                metrics_to_flush = self.metrics_buffer[:20]  # CloudWatch limit
                self.metrics_buffer = self.metrics_buffer[20:]
            
            if not metrics_to_flush:
                return
            
            # Send metrics
            cloudwatch_metrics.put_metric_data(
                Namespace=self.cloudwatch_config.metrics_namespace,
                MetricData=metrics_to_flush
            )
            
            # Update metrics
            with self.metrics_lock:
                self.metrics.cloudwatch_requests += 1
            
        except Exception as e:
            logger.error(f"Error flushing CloudWatch metrics: {e}")
            with self.metrics_lock:
                self.metrics.cloudwatch_failures += 1
    
    # =============================================================================
    # X-Ray Integration
    # =============================================================================
    
    @_xray_capture('scafad_layer0_anomaly_detection')
    async def trace_anomaly_detection(self, telemetry: TelemetryRecord, 
                                    detection_results: Dict[str, Any]) -> str:
        """
        Create X-Ray trace for anomaly detection
        
        Args:
            telemetry: Input telemetry record
            detection_results: Anomaly detection results
            
        Returns:
            Trace ID if successful, empty string otherwise
        """
        if not HAS_XRAY or not self.xray_config.tracing_enabled:
            return ""
        
        try:
            # Get current trace
            trace = xray_recorder.current_trace()
            if not trace:
                return ""
            
            # Add custom annotations
            trace.put_annotation('telemetry_id', getattr(telemetry, 'telemetry_id', 'unknown'))
            trace.put_annotation('function_id', getattr(telemetry, 'function_id', 'unknown'))
            trace.put_annotation('anomaly_type', getattr(telemetry, 'anomaly_type', 'unknown'))
            trace.put_annotation('detection_confidence', detection_results.get('overall_confidence', 0.0))
            
            # Add custom metadata
            trace.put_metadata('telemetry_data', {
                'duration_ms': getattr(telemetry, 'duration', 0.0),
                'memory_spike_kb': getattr(telemetry, 'memory_spike_kb', 0),
                'cpu_utilization': getattr(telemetry, 'cpu_utilization', 0.0)
            })
            
            trace.put_metadata('detection_results', {
                'algorithms_used': detection_results.get('algorithms_used', []),
                'detection_count': len(detection_results.get('detections', [])),
                'processing_time_ms': detection_results.get('processing_time_ms', 0.0)
            })
            
            # Update metrics
            with self.metrics_lock:
                self.metrics.xray_traces += 1
            
            return trace.trace_id or ""
            
        except Exception as e:
            logger.error(f"Error creating X-Ray trace: {e}")
            with self.metrics_lock:
                self.metrics.xray_errors += 1
            return ""
    
    def create_subsegment(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create X-Ray subsegment for detailed tracing
        
        Args:
            name: Subsegment name
            metadata: Optional metadata to include
            
        Returns:
            Subsegment context manager or None
        """
        if not HAS_XRAY or not self.xray_config.tracing_enabled:
            return None
        
        try:
            subsegment = xray_recorder.begin_subsegment(name)
            
            if metadata:
                for key, value in metadata.items():
                    subsegment.put_metadata(key, value)
            
            return subsegment
            
        except Exception as e:
            logger.error(f"Error creating X-Ray subsegment: {e}")
            return None
    
    # =============================================================================
    # Lambda Integration
    # =============================================================================
    
    def optimize_lambda_runtime(self) -> Dict[str, Any]:
        """
        Apply Lambda runtime optimizations
        
        Returns:
            Dictionary of applied optimizations
        """
        optimizations = {}
        
        try:
            if self.lambda_config.runtime_api_optimization:
                # Optimize runtime API usage
                os.environ['AWS_LAMBDA_RUNTIME_API_OPTIMIZATION'] = '1'
                optimizations['runtime_api'] = True
            
            if self.lambda_config.cold_start_optimization:
                # Pre-initialize connections and clients
                self._pre_initialize_clients()
                optimizations['cold_start'] = True
            
            if self.lambda_config.memory_optimization:
                # Configure memory settings
                import gc
                gc.set_threshold(700, 10, 10)
                optimizations['memory'] = True
            
            logger.info(f"Applied Lambda optimizations: {optimizations}")
            
        except Exception as e:
            logger.error(f"Error applying Lambda optimizations: {e}")
        
        return optimizations
    
    def get_lambda_context_info(self, context) -> Dict[str, Any]:
        """
        Extract useful information from Lambda context
        
        Args:
            context: Lambda context object
            
        Returns:
            Dictionary of context information
        """
        try:
            return {
                'function_name': getattr(context, 'function_name', 'unknown'),
                'function_version': getattr(context, 'function_version', 'unknown'),
                'aws_request_id': getattr(context, 'aws_request_id', 'unknown'),
                'memory_limit_mb': getattr(context, 'memory_limit_in_mb', 0),
                'remaining_time_ms': getattr(context, 'get_remaining_time_in_millis', lambda: 0)(),
                'log_group_name': getattr(context, 'log_group_name', 'unknown'),
                'log_stream_name': getattr(context, 'log_stream_name', 'unknown')
            }
        except Exception as e:
            logger.error(f"Error extracting Lambda context: {e}")
            return {}
    
    # =============================================================================
    # Systems Manager Integration
    # =============================================================================
    
    async def load_parameters_from_ssm(self, parameter_prefix: str) -> Dict[str, str]:
        """
        Load configuration parameters from AWS Systems Manager
        
        Args:
            parameter_prefix: Parameter name prefix to filter
            
        Returns:
            Dictionary of parameter names and values
        """
        if not self._is_service_active(AWSServiceType.SSM):
            return {}
        
        try:
            ssm = self.aws_clients.get(AWSServiceType.SSM)
            if not ssm:
                return {}
            
            # Get parameters by prefix
            paginator = ssm.get_paginator('get_parameters_by_path')
            parameters = {}
            
            async for page in paginator.paginate(
                Path=parameter_prefix,
                Recursive=True,
                WithDecryption=True
            ):
                for param in page['Parameters']:
                    param_name = param['Name'].replace(parameter_prefix, '').lstrip('/')
                    parameters[param_name] = param['Value']
            
            logger.info(f"Loaded {len(parameters)} parameters from SSM")
            return parameters
            
        except Exception as e:
            logger.error(f"Error loading parameters from SSM: {e}")
            return {}
    
    # =============================================================================
    # Cost Monitoring and Optimization
    # =============================================================================
    
    def estimate_costs(self) -> Dict[str, float]:
        """
        Estimate AWS service costs based on usage
        
        Returns:
            Dictionary of service costs in USD
        """
        costs = {}
        
        try:
            # CloudWatch Logs costs
            logs_gb = (self.metrics.cloudwatch_requests * 0.001)  # Estimate 1KB per request
            costs['cloudwatch_logs'] = logs_gb * 0.50  # $0.50 per GB ingested
            
            # CloudWatch Metrics costs
            costs['cloudwatch_metrics'] = len(self.metrics_buffer) * 0.0001  # $0.0001 per metric
            
            # X-Ray costs
            costs['xray'] = self.metrics.xray_traces * 0.000005  # $5.00 per 1M traces
            
            # Lambda costs (estimated)
            invocation_cost = self.metrics.lambda_invocations * 0.0000002  # $0.20 per 1M requests
            duration_cost = (self.metrics.lambda_invocations * 100) * 0.0000166667  # $0.0000166667 per GB-second
            costs['lambda'] = invocation_cost + duration_cost
            
            # Total cost
            total_cost = sum(costs.values())
            costs['total'] = total_cost
            
            # Update metrics
            with self.metrics_lock:
                self.metrics.cost_estimate_usd = total_cost
            
        except Exception as e:
            logger.error(f"Error estimating costs: {e}")
        
        return costs
    
    # =============================================================================
    # Internal Helper Methods
    # =============================================================================
    
    def _detect_aws_credentials(self) -> AWSCredentials:
        """Detect AWS credentials from environment"""
        return AWSCredentials(
            access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            session_token=os.environ.get('AWS_SESSION_TOKEN'),
            region=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
            role_arn=os.environ.get('AWS_ROLE_ARN'),
            profile_name=os.environ.get('AWS_PROFILE')
        )
    
    async def _initialize_aws_clients(self):
        """Initialize AWS service clients"""
        try:
            # Create session
            session_kwargs = {'region_name': self.aws_credentials.region}
            
            if self.aws_credentials.profile_name:
                session_kwargs['profile_name'] = self.aws_credentials.profile_name
            
            session = boto3.Session(**session_kwargs)
            
            # CloudWatch Logs client
            self.aws_clients[AWSServiceType.CLOUDWATCH_LOGS] = session.client('logs')
            self.client_status[AWSServiceType.CLOUDWATCH_LOGS] = IntegrationStatus.ACTIVE
            
            # CloudWatch Metrics client
            self.aws_clients[AWSServiceType.CLOUDWATCH_METRICS] = session.client('cloudwatch')
            self.client_status[AWSServiceType.CLOUDWATCH_METRICS] = IntegrationStatus.ACTIVE
            
            # X-Ray client
            if HAS_XRAY:
                self.aws_clients[AWSServiceType.XRAY] = session.client('xray')
                self.client_status[AWSServiceType.XRAY] = IntegrationStatus.ACTIVE
            
            # Lambda client
            self.aws_clients[AWSServiceType.LAMBDA] = session.client('lambda')
            self.client_status[AWSServiceType.LAMBDA] = IntegrationStatus.ACTIVE
            
            # SSM client
            self.aws_clients[AWSServiceType.SSM] = session.client('ssm')
            self.client_status[AWSServiceType.SSM] = IntegrationStatus.ACTIVE
            
            logger.info("AWS clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing AWS clients: {e}")
            # Mark all services as failed
            for service in AWSServiceType:
                self.client_status[service] = IntegrationStatus.FAILED
    
    async def _initialize_xray_tracing(self):
        """Initialize X-Ray tracing configuration"""
        try:
            if not HAS_XRAY:
                return
            
            # Configure sampling rules
            sampling_rule = {
                'version': 2,
                'default': {
                    'fixed_target': 1,
                    'rate': self.xray_config.sampling_rate
                },
                'rules': []
            }
            
            # Configure service
            xray_recorder.configure(
                service=self.xray_config.service_name,
                sampling_rules=sampling_rule,
                plugins=tuple(self.xray_config.plugins)
            )
            
            # Patch AWS SDK calls
            patch_all()
            
            logger.info("X-Ray tracing initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing X-Ray tracing: {e}")
            self.client_status[AWSServiceType.XRAY] = IntegrationStatus.FAILED
    
    async def _start_background_tasks(self):
        """Start background processing tasks"""
        # CloudWatch flushing task
        self.background_tasks.append(
            asyncio.create_task(self._cloudwatch_flush_loop())
        )
        
        # Metrics collection task
        self.background_tasks.append(
            asyncio.create_task(self._metrics_collection_loop())
        )
        
        # Cost monitoring task
        self.background_tasks.append(
            asyncio.create_task(self._cost_monitoring_loop())
        )
    
    async def _cloudwatch_flush_loop(self):
        """Background task to flush CloudWatch data"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(self.cloudwatch_config.flush_interval_ms / 1000.0)
                
                # Flush logs and metrics
                await self._flush_cloudwatch_logs()
                await self._flush_cloudwatch_metrics()
        
        except asyncio.CancelledError:
            logger.debug("CloudWatch flush loop cancelled")
        except Exception as e:
            logger.error(f"Error in CloudWatch flush loop: {e}")
    
    async def _metrics_collection_loop(self):
        """Background task to collect integration metrics"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(30.0)  # Update every 30 seconds
                
                # Update metrics
                with self.metrics_lock:
                    self.metrics.last_update = time.time()
                    
                    # Calculate API latency (simplified)
                    if self.metrics.cloudwatch_requests > 0:
                        success_rate = (self.metrics.cloudwatch_requests - self.metrics.cloudwatch_failures) / self.metrics.cloudwatch_requests
                        self.metrics.api_latency_ms = 100.0 * (1.0 - success_rate)  # Higher latency for failures
        
        except asyncio.CancelledError:
            logger.debug("Metrics collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in metrics collection loop: {e}")
    
    async def _cost_monitoring_loop(self):
        """Background task to monitor costs"""
        try:
            while not self.shutdown_event.is_set():
                await asyncio.sleep(300.0)  # Update every 5 minutes
                
                # Update cost estimates
                costs = self.estimate_costs()
                
                # Log cost alerts if needed
                if costs.get('total', 0.0) > 1.0:  # Alert if costs exceed $1
                    logger.warning(f"AWS costs estimated at ${costs['total']:.4f}")
        
        except asyncio.CancelledError:
            logger.debug("Cost monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in cost monitoring loop: {e}")
    
    def _is_service_active(self, service_type: AWSServiceType) -> bool:
        """Check if AWS service is active and available"""
        return (self.integration_active and 
                self.client_status.get(service_type) == IntegrationStatus.ACTIVE and
                service_type in self.aws_clients)
    
    def _pre_initialize_clients(self):
        """Pre-initialize clients for cold start optimization"""
        try:
            # Pre-warm DNS and connection pools
            for client in self.aws_clients.values():
                if hasattr(client, '_client_config'):
                    client._client_config.max_pool_connections = 50
        except Exception as e:
            logger.debug(f"Error pre-initializing clients: {e}")
    
    async def _flush_all_buffers(self):
        """Flush all pending data buffers"""
        try:
            # Flush CloudWatch data
            await self._flush_cloudwatch_logs()
            await self._flush_cloudwatch_metrics()
            
            logger.info("All AWS data buffers flushed")
            
        except Exception as e:
            logger.error(f"Error flushing buffers: {e}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            'active': self.integration_active,
            'services': {
                service.value: status.value 
                for service, status in self.client_status.items()
            },
            'metrics': {
                'cloudwatch_requests': self.metrics.cloudwatch_requests,
                'cloudwatch_failures': self.metrics.cloudwatch_failures,
                'xray_traces': self.metrics.xray_traces,
                'xray_errors': self.metrics.xray_errors,
                'cost_estimate_usd': self.metrics.cost_estimate_usd,
                'api_latency_ms': self.metrics.api_latency_ms
            },
            'configuration': {
                'cloudwatch_log_group': self.cloudwatch_config.log_group_name,
                'cloudwatch_namespace': self.cloudwatch_config.metrics_namespace,
                'xray_service_name': self.xray_config.service_name,
                'lambda_function_name': self.lambda_config.function_name
            }
        }

# =============================================================================
# Factory Functions and Testing
# =============================================================================

def create_aws_integration_manager(config: Layer0Config = None, 
                                 aws_credentials: Optional[AWSCredentials] = None) -> AWSIntegrationManager:
    """Create a new AWSIntegrationManager instance"""
    if config is None:
        from .app_config import get_default_config
        config = get_default_config()
    
    return AWSIntegrationManager(config, aws_credentials)

async def test_aws_integration():
    """Test AWS integration functionality"""
    from .app_config import create_testing_config
    
    config = create_testing_config()
    aws_manager = AWSIntegrationManager(config)
    
    print("Testing AWS Integration Manager...")
    
    # Test initialization
    initialized = await aws_manager.initialize()
    if initialized:
        print("✅ AWS integration initialized")
    else:
        print("❌ AWS integration failed to initialize")
        return
    
    # Test cost estimation
    print(f"Estimated costs: ${costs.get('total_monthly_usd', 0.0):.4f}/month")

    print("AWS integration test completed.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_aws_integration())

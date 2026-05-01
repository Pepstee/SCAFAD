"""Live AWS Lambda ingestion routes.

Polls CloudWatch Logs for recent Lambda invocations and sends them
through the SCAFAD ingest pipeline.

Requires env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
(or any boto3-compatible credential source).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..store import detection_to_summary_dict

logger = logging.getLogger("scafad.gui.routes.aws_live")

router = APIRouter(prefix="/api/aws", tags=["aws-live"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AwsPullRequest(BaseModel):
    function_name: str
    minutes_back: int = 60
    max_events: int = 50


# ---------------------------------------------------------------------------
# Helper: boto3 availability check
# ---------------------------------------------------------------------------

def _get_boto3_clients(region: Optional[str] = None) -> tuple:
    """Return (lambda_client, logs_client, region_str) or raise ImportError."""
    import boto3  # type: ignore

    session = boto3.session.Session()
    effective_region = region or session.region_name or "us-east-1"
    lambda_client = session.client("lambda", region_name=effective_region)
    logs_client = session.client("logs", region_name=effective_region)
    return lambda_client, logs_client, effective_region


# ---------------------------------------------------------------------------
# GET /api/aws/functions
# ---------------------------------------------------------------------------

@router.get("/functions")
async def list_aws_functions(request: Request) -> Dict[str, Any]:
    """List all Lambda functions visible to the configured AWS credentials."""
    try:
        lambda_client, _, region = _get_boto3_clients()
    except ImportError:
        return {"available": False, "reason": "boto3 is not installed. Run: pip install boto3"}
    except Exception as exc:
        return {"available": False, "reason": f"AWS client initialisation failed: {exc}"}

    try:
        functions: List[Dict[str, Any]] = []
        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                functions.append({
                    "name": fn.get("FunctionName", ""),
                    "runtime": fn.get("Runtime", "unknown"),
                    "memory_size": fn.get("MemorySize", 128),
                    "timeout": fn.get("Timeout", 3),
                    "last_modified": fn.get("LastModified", ""),
                    "region": region,
                })
        return {
            "available": True,
            "functions": functions,
            "region": region,
            "count": len(functions),
        }
    except Exception as exc:
        logger.warning("AWS list_functions failed: %s", exc)
        return {"available": False, "reason": str(exc), "functions": [], "region": "", "count": 0}


# ---------------------------------------------------------------------------
# REPORT line parser
# ---------------------------------------------------------------------------

_REPORT_RE = re.compile(
    r"Duration:\s*([\d.]+)\s*ms"
    r".*?Billed Duration:\s*([\d.]+)\s*ms"
    r".*?Memory Size:\s*(\d+)\s*MB"
    r".*?Max Memory Used:\s*(\d+)\s*MB"
    r"(?:.*?Init Duration:\s*([\d.]+)\s*ms)?",
    re.DOTALL,
)


def _parse_report(message: str, function_name: str, region: str, timestamp_ms: int) -> Optional[Dict[str, Any]]:
    """Parse a CloudWatch REPORT line into a SCAFAD event dict."""
    m = _REPORT_RE.search(message)
    if not m:
        return None

    duration_ms = float(m.group(1))
    memory_size_mb = int(m.group(3))
    max_memory_mb = int(m.group(4))
    init_duration = m.group(5)

    memory_spike_kb = max_memory_mb * 1024
    memory_pct = max_memory_mb / memory_size_mb if memory_size_mb > 0 else 0.0

    if init_duration is not None:
        execution_phase = "init"
        anomaly = "cold-start"
    elif duration_ms > 5000:
        execution_phase = "invoke"
        anomaly = "timeout"
    elif memory_pct > 0.80:
        execution_phase = "invoke"
        anomaly = "spike"
    else:
        execution_phase = "invoke"
        anomaly = "normal"

    ts = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).isoformat()

    return {
        "event_id": f"aws-{function_name}-{uuid.uuid4().hex[:8]}",
        "function_id": function_name,
        "duration": duration_ms,
        "memory_spike_kb": memory_spike_kb,
        "execution_phase": execution_phase,
        "region": region,
        "anomaly": anomaly,
        "timestamp": ts,
    }


# ---------------------------------------------------------------------------
# POST /api/aws/pull
# ---------------------------------------------------------------------------

@router.post("/pull")
async def pull_aws_events(request: Request, body: AwsPullRequest) -> Dict[str, Any]:
    """Poll CloudWatch Logs for the given Lambda and push events through SCAFAD."""
    adapter = request.app.state.runtime_adapter
    store = request.app.state.store
    bus = request.app.state.event_bus

    try:
        _, logs_client, region = _get_boto3_clients()
    except ImportError:
        return {
            "pulled": 0, "ingested": 0, "detections": [],
            "errors": ["boto3 is not installed. Run: pip install boto3"],
        }
    except Exception as exc:
        return {
            "pulled": 0, "ingested": 0, "detections": [],
            "errors": [f"AWS client initialisation failed: {exc}"],
        }

    log_group = f"/aws/lambda/{body.function_name}"
    start_ms = int((time.time() - body.minutes_back * 60) * 1000)

    pulled_events: List[Dict[str, Any]] = []
    errors: List[str] = []

    # ── Collect log streams active in the window ─────────────────────────────
    try:
        streams_resp = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy="LastEventTime",
            descending=True,
            limit=20,
        )
        streams = streams_resp.get("logStreams", [])
    except Exception as exc:
        return {
            "pulled": 0, "ingested": 0, "detections": [],
            "errors": [f"Could not describe log streams for {log_group}: {exc}"],
        }

    # ── Collect REPORT lines from each stream ────────────────────────────────
    for stream in streams:
        if len(pulled_events) >= body.max_events:
            break
        stream_name = stream.get("logStreamName", "")
        try:
            events_resp = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                startTime=start_ms,
                startFromHead=True,
            )
            for log_event in events_resp.get("events", []):
                if len(pulled_events) >= body.max_events:
                    break
                msg: str = log_event.get("message", "")
                if "REPORT" not in msg:
                    continue
                parsed = _parse_report(
                    msg, body.function_name, region,
                    log_event.get("timestamp", int(time.time() * 1000)),
                )
                if parsed:
                    pulled_events.append(parsed)
        except Exception as exc:
            errors.append(f"Stream {stream_name}: {exc}")

    # ── Push each event through the SCAFAD pipeline ──────────────────────────
    detections: List[Dict[str, str]] = []

    for event in pulled_events:
        try:
            outcome = await asyncio.to_thread(adapter.ingest, event)

            row = store.insert_detection(
                event_id=outcome.event_id or event.get("event_id", "aws-event"),
                function_id=outcome.function_id,
                anomaly_type=outcome.anomaly_type,
                severity=outcome.severity,
                trust_score=outcome.trust_score,
                mitre_techniques=outcome.mitre_techniques,
                layer_payload=outcome.layer_payload,
                decision=outcome.decision,
                risk_band=outcome.risk_band,
                duration_ms=outcome.duration_ms,
                correlation_id=outcome.correlation_id,
            )

            try:
                await bus.publish(detection_to_summary_dict(row), event_type="detection")
            except Exception:
                logger.debug("SSE publish failed", exc_info=True)

            detections.append({
                "id": row.id,
                "severity": row.severity,
                "function_id": row.function_id,
            })
        except Exception as exc:
            logger.warning("Ingest failed for event %s: %s", event.get("event_id"), exc)
            errors.append(f"Ingest {event.get('event_id', '?')}: {exc}")

    return {
        "pulled": len(pulled_events),
        "ingested": len(detections),
        "detections": detections,
        "errors": errors,
    }


__all__ = ["router"]

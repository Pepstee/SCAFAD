#\!/usr/bin/env python3
"""
SCAFAD AWS Lambda Handler
=========================

Canonical AWS Lambda entry point for SCAFAD.

Delegates exclusively to SCAFADCanonicalRuntime (WP-1.1, DL-019, DL-039).
No legacy controller path remains in this module.
"""

import json
import logging
import os
from typing import Any, Dict

from .runtime import SCAFADCanonicalRuntime

# Configure logging for Lambda
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def initialize_scafad() -> bool:
    """
    Canonical warm-up stub (WP-1.1, DL-039).

    The legacy Layer 0 controller initialisation has been removed.
    SCAFADCanonicalRuntime is stateless and constructs itself on first
    invocation, so no explicit warm-up is required here.
    """
    logger.info(
        "initialize_scafad: canonical runtime delegation active; "
        "no legacy controller to initialise (DL-039)."
    )
    return True


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main AWS Lambda handler for SCAFAD.

    Delegates exclusively to SCAFADCanonicalRuntime (WP-1.1, DL-019).

    Args:
        event:   Lambda event data
        context: Lambda context object

    Returns:
        Response dictionary with SCAFAD analysis results
    """
    try:
        runtime = SCAFADCanonicalRuntime()
        result = runtime.process_event(
            event,
            analyst_label=event.get("analyst_label"),
        )
        return {
            "statusCode": 200,
            "body": json.dumps(result.to_dict()),
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("lambda_handler: unhandled exception: %s", exc, exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }


def warm_container() -> None:
    """
    Container pre-warm hook.

    Canonical runtime is stateless; this is a no-op placeholder retained
    for operational tooling compatibility.
    """
    logger.info(
        "warm_container: canonical runtime active; no legacy self-test path (DL-039)."
    )


# Container warm-up (executes during container initialisation)
if os.getenv("LAMBDA_TASK_ROOT"):  # Only in Lambda environment
    warm_container()


__all__ = ["lambda_handler", "initialize_scafad", "warm_container"]

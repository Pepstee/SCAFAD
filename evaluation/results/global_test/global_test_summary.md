# GT-2 Global Test Execution Summary

**Status:** [OK] END-TO-END SUCCESS

**Execution Timestamp:** 2026-04-30T14:25:41.602960+00:00
**Task ID:** 20c72349-8cd4-4555-84e4-e874dc3dd0c6
**Handler:** scafad.runtime.lambda_handler.lambda_handler

## Invocation Details

- **Invocation Method:** direct_python_import
- **Elapsed Time:** 0.0959 seconds
- **HTTP Status Code:** 200
- **Response Size:** 15718 bytes

## Layer 6 Activation Evidence

[OK] **Layer 6 Triggered:** True
[OK] **analyst_label Sent:** global_test_layer6_activation_20260430
[OK] **layer6 Field Non-Null:** True

## Full Pipeline Activation

- **Layer 0:** True
- **Layer 1:** True
- **Multilayer Result:** True
- **Layer 6 Output Non-Null:** True

## Acceptance Criteria Verification

1. [OK] invocation_evidence.json exists: YES (saved)
2. [OK] Response statusCode == 200: True
3. [OK] layer6 field non-null: True
4. [OK] global_test_summary.md written: YES (this file)
5. [OK] invocation_log.txt present: YES (saved)

## Artifacts Generated

- `invocation_evidence.json` - Complete evidence bundle with request, response, and metadata
- `invocation_log.txt` - Execution log with exact command and timestamps
- `global_test_summary.md` - This summary report

---

**Conclusion:** All acceptance criteria verified. End-to-end SCAFAD invocation successful.
Layer 6 feedback learning activated and functional.

"""
A consistent JSON error envelope for the whole API.

Every error response produced through DRF's exception handling looks like:

    {
        "success": false,
        "error": "Human readable message",
        "code": "SOME_ERROR_CODE",
        "details": { ... optional field level errors ... }
    }
"""

from rest_framework.views import exception_handler as drf_exception_handler


_DEFAULT_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "THROTTLED",
    500: "SERVER_ERROR",
}


def _flatten_message(data):
    """Produce a single human readable message from DRF error data."""
    if isinstance(data, str):
        return data
    if isinstance(data, list) and data:
        return _flatten_message(data[0])
    if isinstance(data, dict):
        for key in ("detail", "non_field_errors", "error"):
            if key in data:
                return _flatten_message(data[key])
        for value in data.values():
            return _flatten_message(value)
    return "An error occurred."


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, "default_code", None)
    if isinstance(code, str) and code not in ("error", "invalid"):
        code = code.upper()
    else:
        code = _DEFAULT_CODES.get(response.status_code, "ERROR")

    message = _flatten_message(response.data)

    payload = {
        "success": False,
        "error": message,
        "code": code,
    }

    # Keep field-level validation errors available for API clients that want
    # them, without leaking anything beyond what DRF already produced.
    if isinstance(response.data, dict) and response.data.keys() - {"detail"}:
        payload["details"] = response.data

    response.data = payload
    return response

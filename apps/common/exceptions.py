from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    details = response.data
    if isinstance(details, dict) and "detail" in details and len(details) == 1:
        message = str(details["detail"])
        details = None
    else:
        message = "Validation error" if response.status_code == 400 else "Request failed"

    response.data = {
        "error": {
            "message": message,
            "code": getattr(exc, "default_code", "error"),
            "details": details,
        }
    }
    return response

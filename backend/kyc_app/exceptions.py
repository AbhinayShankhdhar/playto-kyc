from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Returns consistent error shape:
    {
        "error": true,
        "message": "...",
        "details": {...}   (optional)
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        data = response.data

        # Flatten DRF's default structure into our shape
        if isinstance(data, dict):
            # Extract 'detail' or join list errors
            message = data.get('detail', '')
            if not message:
                # Build message from field errors
                parts = []
                for field, errors in data.items():
                    if isinstance(errors, list):
                        parts.append(f"{field}: {'; '.join(str(e) for e in errors)}")
                    else:
                        parts.append(str(errors))
                message = ' | '.join(parts)
        elif isinstance(data, list):
            message = '; '.join(str(e) for e in data)
        else:
            message = str(data)

        response.data = {
            'error': True,
            'message': str(message),
            'status_code': response.status_code,
        }

    return response

import logging
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ConflictException(APIException):
    """409: the request is valid but conflicts with the resource's current state."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict: Resource state has already been modified."
    default_code = 'conflict'


def int_query_param(request, name):
    """Parse an optional integer query parameter, raising 400 (not 500) on garbage."""
    raw = request.query_params.get(name)
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: ['A valid integer is required.']}) from None


def _message(data):
    """Flatten DRF error payloads to one human-readable string."""
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        parts = []
        for field, errs in data.items():
            text = _message(errs)
            parts.append(text if field == 'non_field_errors' else f"{field}: {text}")
        return '; '.join(parts)
    if isinstance(data, list):
        return ' '.join(_message(item) for item in data)
    return str(data)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        data = response.data
        response.data = {
            'success': False,
            'status_code': response.status_code,
            # Always a string so clients can render it directly …
            'error': _message(data),
            # … plus the structured form for field-level display.
            'details': data,
        }
        return response

    request = context.get('request')
    logger.exception("Unhandled exception in API %s %s", getattr(request, 'method', '?'), getattr(request, 'path', '?'))
    return Response(
        {
            'success': False,
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'error': 'Internal server error. Please try again later.',
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

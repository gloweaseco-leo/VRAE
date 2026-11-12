"""Safe offline refusal vocabulary and exact bounded primitives."""
import json


class GatewayError(ValueError):
    """Only locally defined codes; never remote exception/body/credential text."""


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise GatewayError('INVALID_LIMIT_OR_USAGE')
    return value

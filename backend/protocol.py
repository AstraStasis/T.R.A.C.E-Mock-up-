"""Bounded NDJSON framing shared by simulator and serial transport."""
import json

VERSION = 1
MAX_LINE = 262144


def encode(message):
    return (json.dumps(message, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(line):
    if len(line) > MAX_LINE:
        raise ValueError('Protocol line exceeds limit')
    msg = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite number')))
    if not isinstance(msg, dict) or not isinstance(msg.get('t'), str):
        raise ValueError('Message requires a string type')
    return msg

"""Portable content-hashed evidence records (not immutable storage)."""
import hashlib
import json
from datetime import datetime, timezone


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def audit_record(payload, result, settings):
    record = dict(model_version='0.1.0', created_at=datetime.now(timezone.utc).isoformat(),
                  input_sha256=digest(payload), output_sha256=digest(result), settings=settings.copy())
    return dict(record, record_sha256=digest(record))

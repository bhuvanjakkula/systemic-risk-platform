"""Strict normalized report import; not an official regulatory filing parser."""
import csv
from datetime import date
from io import StringIO
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.governance.policy import Nonnegative


class ReportRow(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    bank_id: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    as_of: date
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    liquid_assets: Nonnegative
    stressed_outflows: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    capital: Nonnegative
    rwa: float = Field(gt=0, le=1e12, allow_inf_nan=False)


def parse_reports(content: str):
    reader = csv.DictReader(StringIO(content.lstrip('\ufeff')))
    if reader.fieldnames is None or set(reader.fieldnames) != set(ReportRow.model_fields) or len(reader.fieldnames) != len(ReportRow.model_fields):
        raise ValueError('CSV columns must be bank_id,as_of,currency,liquid_assets,stressed_outflows,capital,rwa')
    result, seen = [], set()
    for line, row in enumerate(reader, 2):
        if line > 1001:
            raise ValueError('Maximum 1000 rows')
        item = ReportRow.model_validate(row)
        key = (item.bank_id, item.as_of, item.currency)
        if key in seen:
            raise ValueError(f'Duplicate bank/date/currency at row {line}')
        seen.add(key)
        result.append({**item.model_dump(mode='json'), 'lcr': item.liquid_assets/item.stressed_outflows, 'capital_rwa_ratio': item.capital/item.rwa})
    if not result:
        raise ValueError('CSV has no observations')
    return {'rows': result, 'source': 'user-provided normalized CSV', 'scope': 'Arithmetic ratios only; definitions and source evidence require independent review.'}

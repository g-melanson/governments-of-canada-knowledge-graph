"""Stage 1 adapter for Open Canada federal election contributions CSV."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterator

from ingest.adapters.base import BaseAdapter
from ingest.adapters.registry import register

FIELD_MAP = {
    "Political Entity": "political_entity",
    "Recipient ID": "recipient_id",
    "Recipient": "recipient_name",
    "Recipient last name": "recipient_last_name",
    "Recipient first name": "recipient_first_name",
    "Recipientmiddle initial": "recipient_middle_initial",
    "Political Party of Recipient": "political_party_of_recipient",
    "Electoral District": "electoral_district",
    "Electoral event": "electoral_event",
    "Fiscal/Election date": "fiscal_election_date",
    "Form ID": "form_id",
    "Financial Report": "financial_report",
    "Part Number of Return": "part_number_of_return",
    "Financial Report part": "financial_report_part",
    "Contributor type": "contributor_type",
    "Contributor name": "contributor_name",
    "Contributor last name": "contributor_last_name",
    "Contributor first name": "contributor_first_name",
    "Contributor middle initial": "contributor_middle_initial",
    "Contributor City": "contributor_city",
    "Contributor Province": "contributor_province",
    "Contributor Postal code": "contributor_postal_code",
    "Contribution Received date": "contribution_received_date",
    "Monetary amount": "monetary_amount",
    "Non-Monetary amount": "non_monetary_amount",
    "Contribution given through": "contribution_given_through",
    "Leadership contestant": "leadership_contestant",
}


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


@register
class FederalElectionContributionAdapter(BaseAdapter):
    source = "open_canada_federal_election_contribution"

    def parse(self, raw_path: Path) -> Iterator[dict]:
        import pandas as pd

        df = pd.read_csv(raw_path)
        for row in df.to_dict(orient="records"):
            yield {snake: row.get(publisher) for publisher, snake in FIELD_MAP.items()}

    def normalize(self, row: dict) -> dict:
        
        out = {k: row.get(k) for k in FIELD_MAP.values()}
        for k, v in out.items():
            if _is_missing(v):
                out[k] = None
        for k in ("recipient_id", "form_id", "part_number_of_return"):
            if out[k] is not None:
                out[k] = str(out[k]).strip()
        for k, v in out.items():
            if isinstance(v, str):
                out[k] = v.strip() or None
        return out

    def filter_row(self, row: dict, ctx) -> bool:
        if not row.get("recipient_id"):
            return False
        return True

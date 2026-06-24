
from __future__ import annotations
from typing import Iterator

from transforms.context import TransformContext
from transforms.materializers.base import FragmentMaterializer

def commons_member_of_parliament_id(person_id, from_date):
    return f"gckg:MemberOfParliament:{person_id}:{from_date}"

def commons_person_id(person_id):
    return f"gckg:Person:Commons:{person_id}"

def person_full_name(row: dict) -> str:
    return f"{row['person_official_first_name']} {row['person_official_last_name']}"

def get_materializer(ctx: TransformContext) -> CommonsMembersMaterializer:
    return CommonsMembersMaterializer(ctx)

class CommonsMembersMaterializer(FragmentMaterializer):
    def materialize(self, row, line_number) -> Iterator[dict]:

        bronze_ref = self.make_bronze_reference(line_number)
        mp_id = commons_member_of_parliament_id(row["person_id"], row["from_date_time"])
        person_id = commons_person_id(row["person_id"])
        person_name = person_full_name(row)

        yield {
            "@type": "MemberOfParliament",
            "bronze_reference": bronze_ref,
            "id": mp_id,
        }
        yield {
            "@type": "Person",
            "bronze_reference": bronze_ref,
            "id": person_id,
            "name": person_name
        }
        yield {
            "@type": "RELATIONSHIP",
            "bronze_reference": bronze_ref,
            "subject": person_id,
            "rel_type": "HAS_ROLE",
            "object": mp_id
        }

import json
import os
from typing import Literal, Optional

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ValidationError

load_dotenv()

CANONICAL_FIELDS = ["id", "name", "price", "category", "in_stock", "description"]

CanonicalField = Literal["id", "name", "price", "category", "in_stock", "description"]


class FieldMapping(BaseModel):
    source_field: str
    canonical_field: Optional[CanonicalField]
    confidence: float
    reasoning: str


class SchemaMappingResult(BaseModel):
    mappings: list[FieldMapping]


def propose_schema_mapping(sample_record: dict) -> SchemaMappingResult:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    prompt = f"""You are mapping fields from an unknown e-commerce data source to a
canonical product schema.

Canonical fields (a source field must map to one of these, or null if none fit):
{CANONICAL_FIELDS}

Sample source record:
{json.dumps(sample_record, indent=2)}

For every field in the sample source record, decide which canonical field it
represents. Respond with ONLY a JSON object of this exact shape, no extra text:

{{
  "mappings": [
    {{
      "source_field": "<name from the source record>",
      "canonical_field": "<one of the canonical fields, or null>",
      "confidence": <float between 0 and 1>,
      "reasoning": "<one short sentence>"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw_output = response.choices[0].message.content

    try:
        return SchemaMappingResult.model_validate_json(raw_output)
    except ValidationError as e:
        raise ValueError(
            f"LLM response did not match expected schema.\nRaw output:\n{raw_output}"
        ) from e


if __name__ == "__main__":
    fake_external_product = {
        "sku": "X-100",
        "title": "Blue Widget",
        "cost_usd": "19.99",
        "type": "gadgets",
        "stock_qty": 12,
        "short_desc": "A small blue widget for testing purposes.",
    }

    result = propose_schema_mapping(fake_external_product)
    for mapping in result.mappings:
        print(
            f"{mapping.source_field:12} -> {str(mapping.canonical_field):12} "
            f"(confidence={mapping.confidence:.2f})  {mapping.reasoning}"
        )

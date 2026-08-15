"""
validation.parse_and_validate — Pydantic-AI-style type-safe parsing.
Validates raw input against a named, pre-registered target schema.
No side effects — this tool only checks and coerces, never writes anything.
"""
from __future__ import annotations
from pydantic import BaseModel, ValidationError
from schemas.tool_schemas import ParseValidateInput, ParseValidateOutput
from schemas.pipeline_schemas import InvoiceFields

# Named schema registry — extend as new pipelines need validated shapes.
_TARGET_SCHEMAS: dict[str, type[BaseModel]] = {
    "invoice_fields": InvoiceFields,
}


def parse_and_validate(input_data: ParseValidateInput) -> ParseValidateOutput:
    schema = _TARGET_SCHEMAS.get(input_data.target_schema)
    if schema is None:
        return ParseValidateOutput(valid=False, parsed=None, errors=[f"Unknown target_schema: {input_data.target_schema}"])

    try:
        parsed = schema.model_validate(input_data.raw_input)
        return ParseValidateOutput(valid=True, parsed=parsed.model_dump(), errors=[])
    except ValidationError as e:
        return ParseValidateOutput(valid=False, parsed=None, errors=[str(err) for err in e.errors()])

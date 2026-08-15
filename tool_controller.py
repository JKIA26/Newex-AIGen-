from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tools.registry import (
    registry,
    ToolNotFoundError,
    ToolValidationError,
    ToolNotAllowlistedError,
)

router = APIRouter(prefix="/tools", tags=["tools"])


class InvokeToolRequest(BaseModel):
    org_id: str
    input: dict


@router.post("/{tool_name}/invoke")
def invoke_tool(tool_name: str, req: InvokeToolRequest):
    try:
        result = registry.invoke(tool_name, org_id=req.org_id, raw_input=req.input)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ToolNotAllowlistedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ToolValidationError as e:
        raise HTTPException(status_code=422, detail={"errors": e.errors})
    return result.model_dump()

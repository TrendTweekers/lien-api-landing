"""
Deprecated endpoints router
Returns 410 Gone for removed integrations
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def deprecated_endpoint(request: Request, path: str):
    """
    Catch-all handler for deprecated QuickBooks endpoints
    Returns 410 Gone to indicate the resource is permanently removed
    """
    return JSONResponse(
        status_code=410,
        content={
            "error": "QuickBooks integration removed",
            "status": 410
        }
    )


"""Explicitly granted, verified read-only observation aggregate endpoint."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from saena_forge_console.authn import RequestActor, build_request_actor
from saena_forge_console.errors import (
    ErrorCategory,
    ServiceError,
    not_found_error,
    policy_denied_error,
)

router = APIRouter()
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


@router.get("/v1/ui-observations/{collection_id}")
def observations(
    collection_id: str, request: Request, actor: RequestActor = Depends(build_request_actor)  # noqa: B008
):
    catalog = request.app.state.observation_catalog
    tenant = actor.actor.tenant_id
    if (
        request.app.state.auth_mode != "production"
        or (tenant, actor.actor.actor_id) not in catalog.readers
    ):
        raise policy_denied_error(
            "observation_read_denied", detail="observation read permission required"
        )
    entry = catalog.entries.get(collection_id)
    if entry is None or entry.tenant_id != tenant:
        raise not_found_error("resource_missing", detail="collection not found")
    try:
        return JSONResponse(catalog.read(collection_id), headers=HEADERS)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise ServiceError(
            ErrorCategory.UNAVAILABLE,
            "observation_unavailable",
            detail="observations unavailable",
            headers=HEADERS,
            retryable=False,
        ) from None

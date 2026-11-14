"""One authenticated, read-only route for approved offline report artifacts."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from saena_forge_console.authn import RequestActor, build_request_actor
from saena_forge_console.errors import (
    ErrorCategory,
    ServiceError,
    not_found_error,
    policy_denied_error,
)
from saena_forge_console.report_store import ReportCatalog

router = APIRouter()
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


@router.get("/v1/html-audit-reports/{report_id}")
def read_report(
    report_id: str,
    request: Request,
    actor: RequestActor = Depends(build_request_actor),  # noqa: B008
):
    if request.app.state.auth_mode != "production":
        raise policy_denied_error(
            "report_verified_auth_required", detail="verified authentication required"
        )
    catalog: ReportCatalog = request.app.state.report_catalog
    tenant = actor.actor.tenant_id
    if (tenant, actor.actor.actor_id) not in catalog.readers:
        raise policy_denied_error("report_read_denied", detail="report read permission required")
    entry = catalog.entries.get(report_id)
    if entry is None or entry.tenant_id != tenant:
        raise not_found_error("resource_missing", detail="report not found")
    try:
        report = catalog.read(entry)
        return JSONResponse(report, headers=HEADERS)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise ServiceError(
            ErrorCategory.UNAVAILABLE,
            "report_unavailable",
            detail="report unavailable",
            headers=HEADERS,
            retryable=False,
        ) from None

"""Opt-in empty viewer shell; report access remains enforced by the existing API."""

from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
}


def _asset(name: str, media: str) -> Response:
    data = files("saena_forge_console").joinpath("viewer", name).read_bytes()
    return Response(data, media_type=media, headers=HEADERS)


@router.get("/report-viewer", include_in_schema=False)
def index() -> Response:
    return _asset("index.html", "text/html")


@router.get("/report-viewer-assets/viewer.css", include_in_schema=False)
def css() -> Response:
    return _asset("viewer.css", "text/css")


@router.get("/report-viewer-assets/viewer.js", include_in_schema=False)
def javascript() -> Response:
    return _asset("viewer.js", "text/javascript")

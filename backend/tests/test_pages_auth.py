import asyncio
from inspect import signature

import pytest
from fastapi import HTTPException

from app.main import app
from app.routes.api_auth import register as api_register
from app.routes.pages import logout


def test_html_logout_takes_no_response_parameter():
    """Regression: FastAPI treated `response: Response` as a required query field (422)."""
    assert "response" not in signature(logout).parameters


def _iter_routes(routes):
    """Walk app.routes recursively: FastAPI nests included routers since 0.117."""
    for route in routes:
        yield route
        nested = getattr(route, "routes", None)
        if nested is None:
            nested = getattr(getattr(route, "original_router", None), "routes", None)
        if nested:
            yield from _iter_routes(nested)


def test_html_logout_route_has_no_required_query_params():
    route = next(
        r
        for r in _iter_routes(app.routes)
        if getattr(r, "path", None) == "/logout" and "POST" in getattr(r, "methods", set())
    )
    assert route.dependant.query_params == []


def test_api_register_is_forbidden():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(api_register())
    assert exc_info.value.status_code == 403
    assert "/register" in exc_info.value.detail

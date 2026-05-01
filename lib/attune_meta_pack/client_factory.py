from __future__ import annotations

import importlib
import os
from typing import Any

from .errors import ClientDependencyError, ClientNotGeneratedError


def _import_client_module():
    try:
        return importlib.import_module("attune_client.client")
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("attune_client"):
            raise ClientNotGeneratedError(
                "Vendored OpenAPI client is not available. Run ./scripts/generate_client.sh."
            ) from exc
        raise ClientDependencyError(
            f"Vendored OpenAPI client dependency '{exc.name}' is missing. "
            "Install the pack Python dependencies from requirements.txt."
        ) from exc
    except ImportError as exc:
        raise ClientNotGeneratedError(
            "Vendored OpenAPI client is not available. Run ./scripts/generate_client.sh."
        ) from exc


def build_client(params: dict[str, Any], *, require_auth: bool = True):
    client_module = _import_client_module()

    api_url = (
        params.get("api_url")
        or os.environ.get("ATTUNE_API_URL")
        or "http://localhost:8080"
    )
    verify_ssl = params.get("verify_ssl")
    if verify_ssl is None:
        verify_ssl = str(os.environ.get("ATTUNE_VERIFY_SSL", "true")).lower() in {
            "1",
            "true",
            "yes",
        }

    timeout_value = params.get("timeout")
    if timeout_value is None:
        timeout_value = params.get("timeout_seconds")
    if timeout_value is None:
        timeout_value = int(os.environ.get("ATTUNE_TIMEOUT_SECONDS", "30"))

    token = params.get("api_token") or os.environ.get("ATTUNE_API_TOKEN")

    kwargs = {
        "base_url": api_url,
        "timeout": timeout_value,
        "verify_ssl": verify_ssl,
        "follow_redirects": True,
    }

    if require_auth:
        if not token:
            raise ValueError(
                "This action requires an API token. Provide api_token or ATTUNE_API_TOKEN."
            )
        return client_module.AuthenticatedClient(token=token, **kwargs)

    if token:
        return client_module.AuthenticatedClient(token=token, **kwargs)
    return client_module.Client(**kwargs)


def import_symbol(module_name: str, symbol_name: str):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("attune_client"):
            raise ClientNotGeneratedError(
                f"Generated client module '{module_name}' is unavailable. Regenerate the client."
            ) from exc
        raise ClientDependencyError(
            f"Generated client dependency '{exc.name}' is missing. "
            "Install the pack Python dependencies from requirements.txt."
        ) from exc
    except ImportError as exc:
        raise ClientNotGeneratedError(
            f"Generated client module '{module_name}' is unavailable. Regenerate the client."
        ) from exc

    try:
        return getattr(module, symbol_name)
    except AttributeError as exc:
        raise ClientNotGeneratedError(
            f"Generated client symbol '{symbol_name}' is unavailable in '{module_name}'. "
            "Regenerate the client against the latest OpenAPI spec."
        ) from exc

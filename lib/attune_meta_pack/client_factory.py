from __future__ import annotations

import importlib
import json
import os
import re
from typing import Any

from .errors import ClientDependencyError, ClientNotGeneratedError, MetaPackError


_CREDENTIAL_REF = re.compile(r"attune\.[A-Za-z0-9][A-Za-z0-9_.:-]{0,247}")


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


def _fetch_external_credential(key_ref: Any) -> dict[str, Any]:
    if not isinstance(key_ref, str) or not _CREDENTIAL_REF.fullmatch(key_ref):
        raise MetaPackError("credential_key must be a pack-owned attune.* Key ref")

    try:
        import attune
        from attune.api_client.api.secrets import get_key

        response = get_key.sync_detailed(
            key_ref, client=attune.context.client, decrypt=True
        )
    except Exception as exc:
        raise MetaPackError(
            f"Could not read external Attune credential Key ({type(exc).__name__})"
        ) from None

    if response.status_code != 200 or response.parsed is None:
        if response.status_code == 404:
            raise MetaPackError("External Attune credential Key was not found")
        raise MetaPackError(
            f"Could not read external Attune credential Key (HTTP {response.status_code})"
        )

    value = response.parsed.data.value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise MetaPackError(
                "External Attune credential Key must contain a JSON object"
            ) from None
    if not isinstance(value, dict):
        raise MetaPackError("External Attune credential Key must contain a JSON object")
    if not isinstance(value.get("api_url"), str) or not value["api_url"]:
        raise MetaPackError("External Attune credential requires api_url")
    if not isinstance(value.get("api_token"), str) or not value["api_token"]:
        raise MetaPackError("External Attune credential requires api_token")
    if "verify_ssl" in value and not isinstance(value["verify_ssl"], bool):
        raise MetaPackError("External Attune credential verify_ssl must be a boolean")
    for field in ("timeout", "timeout_seconds"):
        timeout = value.get(field)
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, int)
            or not 1 <= timeout <= 600
        ):
            raise MetaPackError(
                f"External Attune credential {field} must be an integer from 1 to 600"
            )
    return value


def build_client(params: dict[str, Any], *, require_auth: bool = True):
    client_module = _import_client_module()
    credential = None
    if params.get("credential_key") is not None:
        credential = _fetch_external_credential(params["credential_key"])

    api_url = (
        (credential or {}).get("api_url")
        or params.get("api_url")
        or os.environ.get("ATTUNE_API_URL")
        or "http://localhost:8080"
    )
    verify_ssl = (credential or {}).get("verify_ssl")
    if verify_ssl is None:
        verify_ssl = params.get("verify_ssl")
    if verify_ssl is None:
        verify_ssl = str(os.environ.get("ATTUNE_VERIFY_SSL", "true")).lower() in {
            "1",
            "true",
            "yes",
        }

    timeout_value = (credential or {}).get("timeout")
    if timeout_value is None:
        timeout_value = (credential or {}).get("timeout_seconds")
    if timeout_value is None:
        timeout_value = params.get("timeout")
    if timeout_value is None:
        timeout_value = params.get("timeout_seconds")
    if timeout_value is None:
        timeout_value = int(os.environ.get("ATTUNE_TIMEOUT_SECONDS", "30"))

    token = (
        (credential or {}).get("api_token")
        or params.get("api_token")
        or os.environ.get("ATTUNE_API_TOKEN")
    )

    kwargs = {
        "base_url": api_url,
        "timeout": timeout_value,
        "verify_ssl": verify_ssl,
        "follow_redirects": True,
    }

    if require_auth:
        if not token:
            raise ValueError(
                "This action requires an API token. Provide credential_key, api_token, "
                "or ATTUNE_API_TOKEN."
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

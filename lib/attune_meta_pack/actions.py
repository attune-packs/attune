from __future__ import annotations

import os
from typing import Any, Callable

from .client_factory import build_client, import_symbol
from .errors import ClientDependencyError, ClientNotGeneratedError, MetaPackError
from .io import emit_json, fail, read_params
from .result_utils import to_plain_data


def _build_model(model_module: str, model_name: str, payload: dict[str, Any]) -> Any:
    model_cls = import_symbol(model_module, model_name)
    if hasattr(model_cls, "from_dict"):
        return model_cls.from_dict(payload)
    return model_cls(**payload)


def _require(params: dict[str, Any], *fields: str) -> None:
    for field in fields:
        if not params.get(field):
            raise ValueError(f"{field} is required")


def _require_any(params: dict[str, Any], *fields: str) -> None:
    if any(params.get(field) is not None for field in fields):
        return
    names = ", ".join(fields)
    raise ValueError(f"One of {names} is required")


def run_action(
    action_fn: Callable[[dict[str, Any]], Any],
) -> int:
    try:
        params = read_params()
        result = action_fn(params)
        return emit_json({"success": True, "data": to_plain_data(result)})
    except ClientNotGeneratedError as exc:
        return fail(str(exc))
    except ClientDependencyError as exc:
        return fail(str(exc))
    except MetaPackError as exc:
        return fail(str(exc))
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:
        return fail(f"Unhandled action error: {exc}")


def execution_get(params: dict[str, Any]) -> Any:
    execution_id = params.get("execution_id")
    if execution_id is None:
        raise ValueError("execution_id is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.executions.get_execution", "sync")
    return sync(id=int(execution_id), client=client)


def execution_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.executions.list_executions", "sync")
    return sync(
        client=client,
        status=params.get("status"),
        action_ref=params.get("action_ref"),
        pack_name=params.get("pack_name"),
        result_contains=params.get("result_contains"),
        enforcement=params.get("enforcement"),
        parent=params.get("parent"),
        page=params.get("page"),
        per_page=params.get("per_page"),
    )


def execution_stats(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.executions.get_execution_stats", "sync")
    return sync(client=client)


def execution_list_by_status(params: dict[str, Any]) -> Any:
    status = params.get("status")
    if not status:
        raise ValueError("status is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.executions.list_executions_by_status", "sync"
    )
    return sync(
        str(status),
        client=client,
        page=params.get("page"),
        page_size=params.get("page_size"),
    )


def execution_list_by_enforcement(params: dict[str, Any]) -> Any:
    enforcement_id = params.get("enforcement_id")
    if enforcement_id is None:
        raise ValueError("enforcement_id is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.executions.list_executions_by_enforcement", "sync"
    )
    return sync(
        int(enforcement_id),
        client=client,
        page=params.get("page"),
        page_size=params.get("page_size"),
    )


def execution_run(params: dict[str, Any]) -> Any:
    action_ref = params.get("action_ref")
    if not action_ref:
        raise ValueError("action_ref is required")

    client = build_client(params)
    try:
        sync = import_symbol("attune_client.api.executions.create_execution", "sync")
    except ClientNotGeneratedError as exc:
        raise ClientNotGeneratedError(
            "The generated client does not contain the manual execution endpoint. "
            "Regenerate the client from a spec that includes POST /api/v1/executions/execute."
        ) from exc
    request_body = _build_model(
        "attune_client.models.create_execution_request",
        "CreateExecutionRequest",
        {
            "action_ref": action_ref,
            "parameters": params.get("parameters"),
            "env_vars": params.get("env_vars"),
        },
    )
    return sync(client=client, body=request_body)


def pack_sync_workflows(params: dict[str, Any]) -> Any:
    pack_ref = params.get("pack_ref")
    if not pack_ref:
        raise ValueError("pack_ref is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.sync_pack_workflows", "sync")
    return sync(ref=str(pack_ref), client=client)


def health_detailed(params: dict[str, Any]) -> Any:
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.health.health_detailed", "sync")
    return sync(client=client)


def rule_get(params: dict[str, Any]) -> Any:
    rule_ref = params.get("ref")
    if not rule_ref:
        raise ValueError("ref is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.rules.get_rule", "sync")
    return sync(ref=str(rule_ref), client=client)


def rule_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    page = params.get("page")
    page_size = params.get("page_size")

    if params.get("enabled") is True:
        sync = import_symbol("attune_client.api.rules.list_enabled_rules", "sync")
        return sync(client=client, page=page, page_size=page_size)

    if params.get("pack_ref"):
        sync = import_symbol("attune_client.api.rules.list_rules_by_pack", "sync")
        return sync(
            str(params["pack_ref"]), client=client, page=page, page_size=page_size
        )

    if params.get("action_ref"):
        sync = import_symbol("attune_client.api.rules.list_rules_by_action", "sync")
        return sync(
            str(params["action_ref"]), client=client, page=page, page_size=page_size
        )

    if params.get("trigger_ref"):
        sync = import_symbol("attune_client.api.rules.list_rules_by_trigger", "sync")
        return sync(
            str(params["trigger_ref"]), client=client, page=page, page_size=page_size
        )

    sync = import_symbol("attune_client.api.rules.list_rules", "sync")
    return sync(client=client, page=page, page_size=page_size)


def rule_create(params: dict[str, Any]) -> Any:
    for field in ("ref", "label", "pack_ref", "trigger_ref", "action_ref"):
        if not params.get(field):
            raise ValueError(f"{field} is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.rules.create_rule", "sync")
    body = _build_model(
        "attune_client.models.create_rule_request",
        "CreateRuleRequest",
        {
            "ref": params["ref"],
            "label": params["label"],
            "pack_ref": params["pack_ref"],
            "trigger_ref": params["trigger_ref"],
            "action_ref": params["action_ref"],
            "description": params.get("description"),
            "enabled": params.get("enabled"),
            "conditions": params.get("conditions"),
            "action_params": params.get("action_params"),
            "trigger_params": params.get("trigger_params"),
        },
    )
    return sync(client=client, body=body)


def rule_update(params: dict[str, Any]) -> Any:
    rule_ref = params.get("ref")
    if not rule_ref:
        raise ValueError("ref is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.rules.update_rule", "sync")
    body = _build_model(
        "attune_client.models.update_rule_request",
        "UpdateRuleRequest",
        {
            "action_params": params.get("action_params"),
            "conditions": params.get("conditions"),
            "trigger_params": params.get("trigger_params"),
            "description": params.get("description"),
            "enabled": params.get("enabled"),
            "label": params.get("label"),
        },
    )
    return sync(ref=str(rule_ref), client=client, body=body)


def rule_enable(params: dict[str, Any]) -> Any:
    rule_ref = params.get("ref")
    if not rule_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.rules.enable_rule", "sync")
    return sync(ref=str(rule_ref), client=client)


def rule_disable(params: dict[str, Any]) -> Any:
    rule_ref = params.get("ref")
    if not rule_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.rules.disable_rule", "sync")
    return sync(ref=str(rule_ref), client=client)


def rule_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.rules.delete_rule", "sync")
    return sync(str(params["ref"]), client=client)


def trigger_get(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.triggers.get_trigger", "sync")
    return sync(ref=str(trigger_ref), client=client)


def trigger_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    page = params.get("page")
    page_size = params.get("page_size")

    if params.get("enabled") is True:
        sync = import_symbol("attune_client.api.triggers.list_enabled_triggers", "sync")
        return sync(client=client, page=page, page_size=page_size)

    if params.get("pack_ref"):
        sync = import_symbol("attune_client.api.triggers.list_triggers_by_pack", "sync")
        return sync(
            str(params["pack_ref"]), client=client, page=page, page_size=page_size
        )

    sync = import_symbol("attune_client.api.triggers.list_triggers", "sync")
    return sync(client=client, page=page, page_size=page_size)


def trigger_create(params: dict[str, Any]) -> Any:
    for field in ("ref", "label"):
        if not params.get(field):
            raise ValueError(f"{field} is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.triggers.create_trigger", "sync")
    body = _build_model(
        "attune_client.models.create_trigger_request",
        "CreateTriggerRequest",
        {
            "ref": params["ref"],
            "label": params["label"],
            "description": params.get("description"),
            "enabled": params.get("enabled"),
            "pack_ref": params.get("pack_ref"),
            "param_schema": params.get("param_schema"),
            "out_schema": params.get("out_schema"),
        },
    )
    return sync(client=client, body=body)


def trigger_update(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.triggers.update_trigger", "sync")
    body = _build_model(
        "attune_client.models.update_trigger_request",
        "UpdateTriggerRequest",
        {
            "param_schema": params.get("param_schema"),
            "out_schema": params.get("out_schema"),
            "description": params.get("description"),
            "enabled": params.get("enabled"),
            "label": params.get("label"),
        },
    )
    return sync(ref=str(trigger_ref), client=client, body=body)


def trigger_enable(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.triggers.enable_trigger", "sync")
    return sync(ref=str(trigger_ref), client=client)


def trigger_disable(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.triggers.disable_trigger", "sync")
    return sync(ref=str(trigger_ref), client=client)


def trigger_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.triggers.delete_trigger", "sync")
    return sync(str(params["ref"]), client=client)


def webhook_enable(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.webhooks.enable_webhook", "sync")
    return sync(ref=str(trigger_ref), client=client)


def webhook_disable(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.webhooks.disable_webhook", "sync")
    return sync(ref=str(trigger_ref), client=client)


def webhook_regenerate(params: dict[str, Any]) -> Any:
    trigger_ref = params.get("ref")
    if not trigger_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.webhooks.regenerate_webhook_key", "sync")
    return sync(ref=str(trigger_ref), client=client)


def sensor_get(params: dict[str, Any]) -> Any:
    sensor_ref = params.get("ref")
    if not sensor_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.sensors.get_sensor", "sync")
    return sync(ref=str(sensor_ref), client=client)


def sensor_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    page = params.get("page")
    page_size = params.get("page_size")

    if params.get("enabled") is True:
        sync = import_symbol("attune_client.api.sensors.list_enabled_sensors", "sync")
        return sync(client=client, page=page, page_size=page_size)

    if params.get("pack_ref"):
        sync = import_symbol("attune_client.api.sensors.list_sensors_by_pack", "sync")
        return sync(
            str(params["pack_ref"]), client=client, page=page, page_size=page_size
        )

    if params.get("trigger_ref"):
        sync = import_symbol(
            "attune_client.api.sensors.list_sensors_by_trigger", "sync"
        )
        return sync(
            str(params["trigger_ref"]), client=client, page=page, page_size=page_size
        )

    sync = import_symbol("attune_client.api.sensors.list_sensors", "sync")
    return sync(client=client, page=page, page_size=page_size)


def sensor_create(params: dict[str, Any]) -> Any:
    required = ("ref", "label", "pack_ref", "runtime_ref", "trigger_ref", "entrypoint")
    for field in required:
        if not params.get(field):
            raise ValueError(f"{field} is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.sensors.create_sensor", "sync")
    body = _build_model(
        "attune_client.models.create_sensor_request",
        "CreateSensorRequest",
        {
            "ref": params["ref"],
            "label": params["label"],
            "pack_ref": params["pack_ref"],
            "runtime_ref": params["runtime_ref"],
            "trigger_ref": params["trigger_ref"],
            "entrypoint": params["entrypoint"],
            "config": params.get("config"),
            "description": params.get("description"),
            "enabled": params.get("enabled"),
            "param_schema": params.get("param_schema"),
        },
    )
    return sync(client=client, body=body)


def sensor_update(params: dict[str, Any]) -> Any:
    sensor_ref = params.get("ref")
    if not sensor_ref:
        raise ValueError("ref is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.sensors.update_sensor", "sync")
    body = _build_model(
        "attune_client.models.update_sensor_request",
        "UpdateSensorRequest",
        {
            "param_schema": params.get("param_schema"),
            "description": params.get("description"),
            "enabled": params.get("enabled"),
            "entrypoint": params.get("entrypoint"),
            "label": params.get("label"),
        },
    )
    return sync(ref=str(sensor_ref), client=client, body=body)


def sensor_enable(params: dict[str, Any]) -> Any:
    sensor_ref = params.get("ref")
    if not sensor_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.sensors.enable_sensor", "sync")
    return sync(ref=str(sensor_ref), client=client)


def sensor_disable(params: dict[str, Any]) -> Any:
    sensor_ref = params.get("ref")
    if not sensor_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.sensors.disable_sensor", "sync")
    return sync(ref=str(sensor_ref), client=client)


def sensor_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.sensors.delete_sensor", "sync")
    return sync(str(params["ref"]), client=client)


def key_get(params: dict[str, Any]) -> Any:
    key_ref = params.get("ref")
    if not key_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.secrets.get_key", "sync")
    return sync(ref=str(key_ref), client=client)


def key_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.secrets.list_keys", "sync")
    return sync(
        client=client,
        owner_type=params.get("owner_type"),
        owner=params.get("owner"),
        page=params.get("page"),
        per_page=params.get("per_page"),
    )


def key_create(params: dict[str, Any]) -> Any:
    for field in ("local_ref", "name", "owner_type"):
        if not params.get(field):
            raise ValueError(f"{field} is required")
    if "value" not in params:
        raise ValueError("value is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.secrets.create_key", "sync")
    payload = {
        "local_ref": params["local_ref"],
        "name": params["name"],
        "owner_type": params["owner_type"],
        "value": params["value"],
    }
    for field in (
        "encrypted",
        "owner_action_ref",
        "owner_identity_login",
        "owner_pack_ref",
        "owner_sensor_ref",
    ):
        if params.get(field) is not None:
            payload[field] = params[field]
    body = _build_model(
        "attune_client.models.create_key_request",
        "CreateKeyRequest",
        payload,
    )
    return sync(client=client, body=body)


def key_update(params: dict[str, Any]) -> Any:
    key_ref = params.get("ref")
    if not key_ref:
        raise ValueError("ref is required")

    client = build_client(params)
    sync = import_symbol("attune_client.api.secrets.update_key", "sync")
    payload = {
        field: params[field]
        for field in ("name", "value", "encrypted")
        if field in params
    }
    body = _build_model(
        "attune_client.models.update_key_request",
        "UpdateKeyRequest",
        payload,
    )
    return sync(ref=str(key_ref), client=client, body=body)


def key_delete(params: dict[str, Any]) -> Any:
    key_ref = params.get("ref")
    if not key_ref:
        raise ValueError("ref is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.secrets.delete_key", "sync")
    return sync(ref=str(key_ref), client=client)


def action_get(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.actions.get_action", "sync")
    return sync(str(params["ref"]), client=client)


def action_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    page = params.get("page")
    page_size = params.get("page_size")

    if params.get("pack_ref"):
        sync = import_symbol("attune_client.api.actions.list_actions_by_pack", "sync")
        return sync(
            str(params["pack_ref"]), client=client, page=page, page_size=page_size
        )

    sync = import_symbol("attune_client.api.actions.list_actions", "sync")
    return sync(client=client, page=page, page_size=page_size)


def action_create(params: dict[str, Any]) -> Any:
    _require(params, "ref", "label", "pack_ref", "entrypoint")
    client = build_client(params)
    sync = import_symbol("attune_client.api.actions.create_action", "sync")
    body = _build_model(
        "attune_client.models.create_action_request",
        "CreateActionRequest",
        {
            "ref": params["ref"],
            "label": params["label"],
            "pack_ref": params["pack_ref"],
            "entrypoint": params["entrypoint"],
            "description": params.get("description"),
            "param_schema": params.get("param_schema"),
            "out_schema": params.get("out_schema"),
            "runtime": params.get("runtime"),
            "runtime_version_constraint": params.get("runtime_version_constraint"),
        },
    )
    return sync(client=client, body=body)


def action_update(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.actions.update_action", "sync")
    body = _build_model(
        "attune_client.models.update_action_request",
        "UpdateActionRequest",
        {
            "param_schema": params.get("param_schema"),
            "out_schema": params.get("out_schema"),
            "description": params.get("description"),
            "entrypoint": params.get("entrypoint"),
            "label": params.get("label"),
            "runtime": params.get("runtime"),
            "runtime_version_constraint": params.get("runtime_version_constraint"),
        },
    )
    return sync(str(params["ref"]), client=client, body=body)


def action_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.actions.delete_action", "sync")
    return sync(str(params["ref"]), client=client)


def action_queue_stats(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.actions.get_queue_stats", "sync")
    return sync(str(params["ref"]), client=client)


def pack_get(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.get_pack", "sync")
    return sync(str(params["ref"]), client=client)


def pack_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.list_packs", "sync")
    return sync(
        client=client, page=params.get("page"), page_size=params.get("page_size")
    )


def pack_create(params: dict[str, Any]) -> Any:
    _require(params, "ref", "label", "version")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.create_pack", "sync")
    body = _build_model(
        "attune_client.models.create_pack_request",
        "CreatePackRequest",
        {
            "ref": params["ref"],
            "label": params["label"],
            "version": params["version"],
            "conf_schema": params.get("conf_schema"),
            "config": params.get("config"),
            "dependencies": params.get("dependencies"),
            "description": params.get("description"),
            "is_standard": params.get("is_standard"),
            "meta": params.get("meta"),
            "runtime_deps": params.get("runtime_deps"),
            "tags": params.get("tags"),
        },
    )
    return sync(client=client, body=body)


def pack_update(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.update_pack", "sync")
    body = _build_model(
        "attune_client.models.update_pack_request",
        "UpdatePackRequest",
        {
            "conf_schema": params.get("conf_schema"),
            "config": params.get("config"),
            "meta": params.get("meta"),
            "dependencies": params.get("dependencies"),
            "description": params.get("description"),
            "is_standard": params.get("is_standard"),
            "label": params.get("label"),
            "runtime_deps": params.get("runtime_deps"),
            "tags": params.get("tags"),
            "version": params.get("version"),
        },
    )
    return sync(str(params["ref"]), client=client, body=body)


def pack_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.delete_pack", "sync")
    return sync(str(params["ref"]), client=client)


def pack_register(params: dict[str, Any]) -> Any:
    _require(params, "path")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.register_pack", "sync")
    body = _build_model(
        "attune_client.models.register_pack_request",
        "RegisterPackRequest",
        {
            "path": params["path"],
            "force": params.get("force"),
            "skip_tests": params.get("skip_tests"),
        },
    )
    return sync(client=client, body=body)


def pack_install(params: dict[str, Any]) -> Any:
    _require(params, "source")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.install_pack", "sync")
    body = _build_model(
        "attune_client.models.install_pack_request",
        "InstallPackRequest",
        {
            "source": params["source"],
            "ref_spec": params.get("ref_spec"),
            "skip_deps": params.get("skip_deps"),
            "skip_tests": params.get("skip_tests"),
        },
    )
    return sync(client=client, body=body)


def pack_test(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.test_pack", "sync")
    return sync(str(params["ref"]), client=client)


def pack_validate_workflows(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.validate_pack_workflows", "sync")
    return sync(str(params["ref"]), client=client)


def pack_test_history(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.packs.get_pack_test_history", "sync")
    return sync(
        str(params["ref"]),
        client=client,
        page=params.get("page"),
        page_size=params.get("page_size"),
    )


def pack_latest_test(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.packs.get_pack_latest_test", "sync_detailed"
    )
    return sync(str(params["ref"]), client=client)


def workflow_get(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.workflows.get_workflow", "sync")
    return sync(str(params["ref"]), client=client)


def workflow_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    page = params.get("page")
    page_size = params.get("page_size")
    if params.get("pack_ref"):
        sync = import_symbol(
            "attune_client.api.workflows.list_workflows_by_pack", "sync"
        )
        return sync(
            str(params["pack_ref"]), client=client, page=page, page_size=page_size
        )
    sync = import_symbol("attune_client.api.workflows.list_workflows", "sync")
    return sync(client=client, page=page, page_size=page_size)


def workflow_create(params: dict[str, Any]) -> Any:
    _require(
        params,
        "ref",
        "label",
        "pack_ref",
        "version",
        "definition",
        "param_schema",
        "out_schema",
    )
    client = build_client(params)
    sync = import_symbol("attune_client.api.workflows.create_workflow", "sync")
    body = _build_model(
        "attune_client.models.create_workflow_request",
        "CreateWorkflowRequest",
        {
            "ref": params["ref"],
            "label": params["label"],
            "pack_ref": params["pack_ref"],
            "version": params["version"],
            "definition": params["definition"],
            "param_schema": params["param_schema"],
            "out_schema": params["out_schema"],
            "description": params.get("description"),
            "tags": params.get("tags"),
        },
    )
    return sync(client=client, body=body)


def workflow_update(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.workflows.update_workflow", "sync")
    body = _build_model(
        "attune_client.models.update_workflow_request",
        "UpdateWorkflowRequest",
        {
            "definition": params.get("definition"),
            "param_schema": params.get("param_schema"),
            "out_schema": params.get("out_schema"),
            "description": params.get("description"),
            "label": params.get("label"),
            "tags": params.get("tags"),
            "version": params.get("version"),
        },
    )
    return sync(str(params["ref"]), client=client, body=body)


def workflow_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.workflows.delete_workflow", "sync")
    return sync(str(params["ref"]), client=client)


def runtime_get(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.runtimes.get_runtime", "sync")
    return sync(str(params["ref"]), client=client)


def runtime_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    page = params.get("page")
    page_size = params.get("page_size")
    if params.get("pack_ref"):
        sync = import_symbol("attune_client.api.runtimes.list_runtimes_by_pack", "sync")
        return sync(
            str(params["pack_ref"]), client=client, page=page, page_size=page_size
        )
    sync = import_symbol("attune_client.api.runtimes.list_runtimes", "sync")
    return sync(client=client, page=page, page_size=page_size)


def runtime_create(params: dict[str, Any]) -> Any:
    _require(params, "ref", "name")
    client = build_client(params)
    sync = import_symbol("attune_client.api.runtimes.create_runtime", "sync")
    body = _build_model(
        "attune_client.models.create_runtime_request",
        "CreateRuntimeRequest",
        {
            "ref": params["ref"],
            "name": params["name"],
            "description": params.get("description"),
            "distributions": params.get("distributions"),
            "execution_config": params.get("execution_config"),
            "installation": params.get("installation"),
            "pack_ref": params.get("pack_ref"),
        },
    )
    return sync(client=client, body=body)


def runtime_update(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.runtimes.update_runtime", "sync")
    body = _build_model(
        "attune_client.models.update_runtime_request",
        "UpdateRuntimeRequest",
        {
            "distributions": params.get("distributions"),
            "execution_config": params.get("execution_config"),
            "description": params.get("description"),
            "installation": params.get("installation"),
            "name": params.get("name"),
        },
    )
    return sync(str(params["ref"]), client=client, body=body)


def runtime_delete(params: dict[str, Any]) -> Any:
    _require(params, "ref")
    client = build_client(params)
    sync = import_symbol("attune_client.api.runtimes.delete_runtime", "sync")
    return sync(str(params["ref"]), client=client)


def event_get(params: dict[str, Any]) -> Any:
    event_id = params.get("id")
    if event_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.events.get_event", "sync")
    return sync(int(event_id), client=client)


def event_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.events.list_events", "sync")
    return sync(
        client=client,
        trigger=params.get("trigger"),
        trigger_ref=params.get("trigger_ref"),
        rule_ref=params.get("rule_ref"),
        source=params.get("source"),
        page=params.get("page"),
        per_page=params.get("per_page"),
    )


def enforcement_get(params: dict[str, Any]) -> Any:
    enforcement_id = params.get("id")
    if enforcement_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.enforcements.get_enforcement", "sync")
    return sync(int(enforcement_id), client=client)


def enforcement_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.enforcements.list_enforcements", "sync")
    return sync(
        client=client,
        rule=params.get("rule"),
        event=params.get("event"),
        status=params.get("status"),
        trigger_ref=params.get("trigger_ref"),
        rule_ref=params.get("rule_ref"),
        page=params.get("page"),
        per_page=params.get("per_page"),
    )


def inquiry_get(params: dict[str, Any]) -> Any:
    inquiry_id = params.get("id")
    if inquiry_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.get_inquiry", "sync")
    return sync(int(inquiry_id), client=client)


def inquiry_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.list_inquiries", "sync")
    return sync(
        client=client,
        status=params.get("status"),
        execution=params.get("execution"),
        assigned_to=params.get("assigned_to"),
        offset=params.get("offset"),
        limit=params.get("limit"),
    )


def inquiry_list_by_execution(params: dict[str, Any]) -> Any:
    execution_id = params.get("execution_id")
    if execution_id is None:
        raise ValueError("execution_id is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.inquiries.list_inquiries_by_execution", "sync"
    )
    return sync(
        int(execution_id),
        client=client,
        page=params.get("page"),
        page_size=params.get("page_size"),
    )


def inquiry_list_by_status(params: dict[str, Any]) -> Any:
    status = params.get("status")
    if not status:
        raise ValueError("status is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.list_inquiries_by_status", "sync")
    return sync(
        str(status),
        client=client,
        page=params.get("page"),
        page_size=params.get("page_size"),
    )


def inquiry_create(params: dict[str, Any]) -> Any:
    _require(params, "execution", "prompt", "response_schema")
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.create_inquiry", "sync")
    body = _build_model(
        "attune_client.models.create_inquiry_request",
        "CreateInquiryRequest",
        {
            "execution": params["execution"],
            "prompt": params["prompt"],
            "response_schema": params["response_schema"],
            "assigned_to": params.get("assigned_to"),
            "timeout_at": params.get("timeout_at"),
        },
    )
    return sync(client=client, body=body)


def inquiry_update(params: dict[str, Any]) -> Any:
    inquiry_id = params.get("id")
    if inquiry_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.update_inquiry", "sync")
    body = _build_model(
        "attune_client.models.update_inquiry_request",
        "UpdateInquiryRequest",
        {
            "response": params.get("response"),
            "assigned_to": params.get("assigned_to"),
            "status": params.get("status"),
        },
    )
    return sync(int(inquiry_id), client=client, body=body)


def inquiry_respond(params: dict[str, Any]) -> Any:
    inquiry_id = params.get("id")
    if inquiry_id is None:
        raise ValueError("id is required")
    _require(params, "response")
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.respond_to_inquiry", "sync")
    body = _build_model(
        "attune_client.models.inquiry_respond_request",
        "InquiryRespondRequest",
        {"response": params["response"]},
    )
    return sync(int(inquiry_id), client=client, body=body)


def inquiry_delete(params: dict[str, Any]) -> Any:
    inquiry_id = params.get("id")
    if inquiry_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.inquiries.delete_inquiry", "sync")
    return sync(int(inquiry_id), client=client)


def identity_get(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.get_identity", "sync")
    return sync(int(identity_id), client=client)


def identity_list(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.list_identities", "sync")
    return sync(
        client=client, page=params.get("page"), page_size=params.get("page_size")
    )


def identity_create(params: dict[str, Any]) -> Any:
    _require(params, "login")
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.create_identity", "sync")
    body = _build_model(
        "attune_client.models.create_identity_request",
        "CreateIdentityRequest",
        {
            "login": params["login"],
            "attributes": params.get("attributes"),
            "display_name": params.get("display_name"),
            "password": params.get("password"),
        },
    )
    return sync(client=client, body=body)


def identity_update(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.update_identity", "sync")
    body = _build_model(
        "attune_client.models.update_identity_request",
        "UpdateIdentityRequest",
        {
            "attributes": params.get("attributes"),
            "display_name": params.get("display_name"),
            "frozen": params.get("frozen"),
            "password": params.get("password"),
        },
    )
    return sync(int(identity_id), client=client, body=body)


def identity_delete(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.delete_identity", "sync")
    return sync(int(identity_id), client=client)


def identity_freeze(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.freeze_identity", "sync")
    return sync(int(identity_id), client=client)


def identity_unfreeze(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.unfreeze_identity", "sync")
    return sync(int(identity_id), client=client)


def permission_list_sets(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.permissions.list_permission_sets", "sync")
    return sync(client=client)


def permission_list_identity_permissions(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.list_identity_permissions", "sync"
    )
    return sync(int(identity_id), client=client)


def permission_grant(params: dict[str, Any]) -> Any:
    _require(params, "permission_set_ref")
    _require_any(params, "identity_id", "identity_login")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.create_permission_assignment", "sync"
    )
    body = _build_model(
        "attune_client.models.create_permission_assignment_request",
        "CreatePermissionAssignmentRequest",
        {
            "permission_set_ref": params["permission_set_ref"],
            "identity_id": params.get("identity_id"),
            "identity_login": params.get("identity_login"),
        },
    )
    return sync(client=client, body=body)


def permission_revoke(params: dict[str, Any]) -> Any:
    assignment_id = params.get("id")
    if assignment_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.delete_permission_assignment", "sync"
    )
    return sync(int(assignment_id), client=client)


def role_assign_identity(params: dict[str, Any]) -> Any:
    identity_id = params.get("id")
    if identity_id is None:
        raise ValueError("id is required")
    _require(params, "role")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.create_identity_role_assignment", "sync"
    )
    body = _build_model(
        "attune_client.models.create_identity_role_assignment_request",
        "CreateIdentityRoleAssignmentRequest",
        {"role": params["role"]},
    )
    return sync(int(identity_id), client=client, body=body)


def role_remove_identity(params: dict[str, Any]) -> Any:
    assignment_id = params.get("id")
    if assignment_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.delete_identity_role_assignment", "sync"
    )
    return sync(int(assignment_id), client=client)


def role_assign_permission_set(params: dict[str, Any]) -> Any:
    permission_set_id = params.get("id")
    if permission_set_id is None:
        raise ValueError("id is required")
    _require(params, "role")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.create_permission_set_role_assignment", "sync"
    )
    body = _build_model(
        "attune_client.models.create_permission_set_role_assignment_request",
        "CreatePermissionSetRoleAssignmentRequest",
        {"role": params["role"]},
    )
    return sync(int(permission_set_id), client=client, body=body)


def role_remove_permission_set(params: dict[str, Any]) -> Any:
    assignment_id = params.get("id")
    if assignment_id is None:
        raise ValueError("id is required")
    client = build_client(params)
    sync = import_symbol(
        "attune_client.api.permissions.delete_permission_set_role_assignment", "sync"
    )
    return sync(int(assignment_id), client=client)


def health_check(params: dict[str, Any]) -> Any:
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.health.health", "sync")
    return sync(client=client)


def health_readiness(params: dict[str, Any]) -> Any:
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.health.readiness", "sync_detailed")
    return sync(client=client)


def health_liveness(params: dict[str, Any]) -> Any:
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.health.liveness", "sync_detailed")
    return sync(client=client)


def agent_info(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.agent.agent_info", "sync")
    return sync(client=client)


def auth_settings(params: dict[str, Any]) -> Any:
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.auth.auth_settings", "sync")
    return sync(client=client)


def auth_me(params: dict[str, Any]) -> Any:
    client = build_client(params)
    sync = import_symbol("attune_client.api.auth.get_current_user", "sync")
    return sync(client=client)


def auth_login(params: dict[str, Any]) -> Any:
    _require(params, "login", "password")
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.auth.login", "sync")
    body = _build_model(
        "attune_client.models.login_request",
        "LoginRequest",
        {"login": params["login"], "password": params["password"]},
    )
    return sync(client=client, body=body)


def auth_refresh(params: dict[str, Any]) -> Any:
    _require(params, "refresh_token")
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.auth.refresh_token", "sync")
    body = _build_model(
        "attune_client.models.refresh_token_request",
        "RefreshTokenRequest",
        {"refresh_token": params["refresh_token"]},
    )
    return sync(client=client, body=body)


def auth_register(params: dict[str, Any]) -> Any:
    _require(params, "login", "password")
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.auth.register", "sync")
    body = _build_model(
        "attune_client.models.register_request",
        "RegisterRequest",
        {
            "login": params["login"],
            "password": params["password"],
            "display_name": params.get("display_name"),
        },
    )
    return sync(client=client, body=body)


def auth_change_password(params: dict[str, Any]) -> Any:
    _require(params, "current_password", "new_password")
    client = build_client(params)
    sync = import_symbol("attune_client.api.auth.change_password", "sync")
    body = _build_model(
        "attune_client.models.change_password_request",
        "ChangePasswordRequest",
        {
            "current_password": params["current_password"],
            "new_password": params["new_password"],
        },
    )
    return sync(client=client, body=body)


def auth_ldap_login(params: dict[str, Any]) -> Any:
    _require(params, "login", "password")
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.auth.ldap_login", "sync")
    body = _build_model(
        "attune_client.models.ldap_login_request",
        "LdapLoginRequest",
        {"login": params["login"], "password": params["password"]},
    )
    return sync(client=client, body=body)


def webhook_receive(params: dict[str, Any]) -> Any:
    _require(params, "webhook_key")
    if "payload" not in params:
        raise ValueError("payload is required")
    client = build_client(params, require_auth=False)
    sync = import_symbol("attune_client.api.webhooks.receive_webhook", "sync")
    body = _build_model(
        "attune_client.models.webhook_receiver_request",
        "WebhookReceiverRequest",
        {
            "payload": params["payload"],
            "headers": params.get("headers"),
            "source_ip": params.get("source_ip"),
            "user_agent": params.get("user_agent"),
        },
    )
    return sync(str(params["webhook_key"]), client=client, body=body)


ACTIONS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "attune.action_list": action_list,
    "attune.execution_get": execution_get,
    "attune.execution_list": execution_list,
    "attune.execution_stats": execution_stats,
    "attune.execution_list_by_status": execution_list_by_status,
    "attune.execution_list_by_enforcement": execution_list_by_enforcement,
    "attune.execution_run": execution_run,
    "attune.pack_get": pack_get,
    "attune.pack_list": pack_list,
    "attune.pack_register": pack_register,
    "attune.pack_install": pack_install,
    "attune.pack_test": pack_test,
    "attune.pack_validate_workflows": pack_validate_workflows,
    "attune.pack_test_history": pack_test_history,
    "attune.pack_latest_test": pack_latest_test,
    "attune.pack_sync_workflows": pack_sync_workflows,
    "attune.workflow_get": workflow_get,
    "attune.workflow_list": workflow_list,
    "attune.workflow_create": workflow_create,
    "attune.workflow_update": workflow_update,
    "attune.workflow_delete": workflow_delete,
    "attune.inquiry_get": inquiry_get,
    "attune.inquiry_list": inquiry_list,
    "attune.inquiry_list_by_execution": inquiry_list_by_execution,
    "attune.inquiry_list_by_status": inquiry_list_by_status,
    "attune.inquiry_respond": inquiry_respond,
    "attune.key_get": key_get,
    "attune.key_list": key_list,
    "attune.key_create": key_create,
    "attune.key_update": key_update,
    "attune.key_delete": key_delete,
    "attune.rule_get": rule_get,
    "attune.rule_list": rule_list,
    "attune.rule_create": rule_create,
    "attune.rule_update": rule_update,
    "attune.rule_enable": rule_enable,
    "attune.rule_disable": rule_disable,
    "attune.rule_delete": rule_delete,
    "attune.trigger_get": trigger_get,
    "attune.trigger_list": trigger_list,
    "attune.trigger_create": trigger_create,
    "attune.trigger_update": trigger_update,
    "attune.trigger_enable": trigger_enable,
    "attune.trigger_disable": trigger_disable,
    "attune.trigger_delete": trigger_delete,
    "attune.webhook_enable": webhook_enable,
    "attune.webhook_disable": webhook_disable,
    "attune.webhook_regenerate": webhook_regenerate,
    "attune.sensor_get": sensor_get,
    "attune.sensor_list": sensor_list,
    "attune.sensor_enable": sensor_enable,
    "attune.sensor_disable": sensor_disable,
}


def dispatch_from_env() -> int:
    action_ref = os.environ.get("ATTUNE_ACTION")
    if not action_ref:
        return fail(
            "ATTUNE_ACTION is not set; cannot dispatch generic action entrypoint."
        )

    action_fn = ACTIONS.get(action_ref)
    if action_fn is None:
        return fail(f"No action handler registered for '{action_ref}'.")
    return run_action(action_fn)

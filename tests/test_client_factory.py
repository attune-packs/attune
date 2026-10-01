from __future__ import annotations

import json
import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from attune_meta_pack import actions, client_factory
from attune_meta_pack.errors import MetaPackError
from attune_client.models.create_key_request import CreateKeyRequest
from attune_client.models.key_response import KeyResponse
from attune_client.models.key_summary import KeySummary
from attune_client.models.paginated_response_key_summary import (
    PaginatedResponseKeySummary,
)
from attune_client.models.update_key_request import UpdateKeyRequest
from attune_client.api.secrets import create_key, delete_key, get_key, list_keys, update_key


class _ClientModule:
    class AuthenticatedClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class ClientFactoryTests(unittest.TestCase):
    def test_every_action_exposes_external_credential(self):
        action_files = sorted((ROOT / "actions").glob("*.yaml"))
        self.assertTrue(action_files)

        for path in action_files:
            with self.subTest(action=path.name):
                parameters = path.read_text(encoding="utf-8").split(
                    "parameters:", 1
                )[1]
                self.assertIn("credential_key:", parameters)

    def test_external_credential_configures_target_client(self):
        credential = {
            "api_url": "https://remote.attune.example",
            "api_token": "remote-token",
            "verify_ssl": False,
            "timeout_seconds": 45,
        }
        params = {
            "credential_key": "pack.attune.remote",
            "api_url": "https://ignored.example",
            "api_token": "ignored-token",
            "verify_ssl": True,
            "timeout": 10,
        }

        with mock.patch.object(
            client_factory, "_import_client_module", return_value=_ClientModule
        ), mock.patch.object(
            client_factory, "_fetch_external_credential", return_value=credential
        ) as fetch:
            client = client_factory.build_client(params)

        fetch.assert_called_once_with("pack.attune.remote")
        self.assertEqual(
            {
                "base_url": "https://remote.attune.example",
                "timeout": 45,
                "verify_ssl": False,
                "follow_redirects": True,
                "token": "remote-token",
            },
            client.kwargs,
        )

    def test_no_credential_preserves_inline_configuration(self):
        params = {
            "api_url": "https://local.attune.example",
            "api_token": "inline-token",
            "verify_ssl": True,
            "timeout": 12,
        }

        with mock.patch.object(
            client_factory, "_import_client_module", return_value=_ClientModule
        ):
            client = client_factory.build_client(params)

        self.assertEqual("https://local.attune.example", client.kwargs["base_url"])
        self.assertEqual("inline-token", client.kwargs["token"])
        self.assertEqual(12, client.kwargs["timeout"])

    def test_fetches_json_credential_from_installing_instance(self):
        context_client = object()
        parsed = types.SimpleNamespace(
            data=types.SimpleNamespace(
                value=json.dumps(
                    {
                        "api_url": "https://remote.attune.example",
                        "api_token": "remote-token",
                    }
                )
            )
        )
        get_key = mock.Mock(
            return_value=types.SimpleNamespace(status_code=200, parsed=parsed)
        )
        fake_attune = types.ModuleType("attune")
        fake_attune.context = types.SimpleNamespace(client=context_client)
        fake_secrets = types.ModuleType("attune.api_client.api.secrets")
        fake_secrets.get_key = types.SimpleNamespace(sync_detailed=get_key)
        modules = {
            "attune": fake_attune,
            "attune.api_client": types.ModuleType("attune.api_client"),
            "attune.api_client.api": types.ModuleType("attune.api_client.api"),
            "attune.api_client.api.secrets": fake_secrets,
        }

        with mock.patch.dict(sys.modules, modules):
            credential = client_factory._fetch_external_credential("pack.attune.remote")

        get_key.assert_called_once_with("pack.attune.remote", client=context_client)
        self.assertEqual("remote-token", credential["api_token"])

    def test_rejects_non_pack_owned_or_incomplete_credentials(self):
        with self.assertRaisesRegex(MetaPackError, "attune\\.\\*"):
            client_factory._fetch_external_credential("other.remote")

        with mock.patch.object(
            client_factory, "_import_client_module", return_value=_ClientModule
        ), mock.patch.object(
            client_factory,
            "_fetch_external_credential",
            side_effect=MetaPackError("External Attune credential requires api_token"),
        ), self.assertRaisesRegex(MetaPackError, "requires api_token"):
            client_factory.build_client({"credential_key": "pack.attune.remote"})


class KeyContractTests(unittest.TestCase):
    def test_create_request_uses_local_ref_and_textual_owner_refs(self):
        self.assertEqual(
            {
                "local_ref",
                "name",
                "owner_type",
                "value",
                "encrypted",
                "owner_action_ref",
                "owner_identity_login",
                "owner_pack_ref",
                "owner_sensor_ref",
            },
            set(inspect.signature(CreateKeyRequest).parameters),
        )
        request = CreateKeyRequest.from_dict(
            {
                "local_ref": "remote",
                "name": "Remote Attune",
                "owner_type": "pack",
                "value": {"api_token": "secret"},
                "owner_pack_ref": "attune",
            }
        )
        self.assertEqual(
            {
                "local_ref": "remote",
                "name": "Remote Attune",
                "owner_type": "pack",
                "value": {"api_token": "secret"},
                "owner_pack_ref": "attune",
            },
            request.to_dict(),
        )
        with self.assertRaises(KeyError):
            CreateKeyRequest.from_dict(
                {
                    "ref": "pack.attune.remote",
                    "name": "Remote Attune",
                    "owner_type": "pack",
                    "value": "secret",
                }
            )

    def test_key_create_adapter_does_not_send_legacy_owner_fields(self):
        sent = []

        def import_symbol(module, name):
            if name == "CreateKeyRequest":
                return CreateKeyRequest
            return lambda **kwargs: sent.append(kwargs["body"].to_dict())

        with mock.patch.object(actions, "build_client", return_value=object()), mock.patch.object(
            actions, "import_symbol", side_effect=import_symbol
        ):
            actions.key_create(
                {
                    "local_ref": "remote",
                    "name": "Remote Attune",
                    "owner_type": "identity",
                    "value": "secret",
                    "owner_identity_login": "alice@example.com",
                }
            )

        self.assertEqual(
            {
                "local_ref": "remote",
                "name": "Remote Attune",
                "owner_type": "identity",
                "value": "secret",
                "owner_identity_login": "alice@example.com",
            },
            sent[0],
        )
        for legacy in ("ref", "owner", "owner_action", "owner_identity", "owner_pack", "owner_sensor"):
            self.assertNotIn(legacy, sent[0])

    def test_response_models_match_current_owner_and_local_ref_contract(self):
        self.assertEqual(
            {
                "created",
                "encrypted",
                "id",
                "local_ref",
                "name",
                "owner_type",
                "ref",
                "updated",
                "value",
                "owner",
                "owner_action",
                "owner_action_ref",
                "owner_identity",
                "owner_pack",
                "owner_pack_ref",
                "owner_sensor",
                "owner_sensor_ref",
            },
            set(inspect.signature(KeyResponse).parameters),
        )
        self.assertEqual(
            {
                "created",
                "encrypted",
                "id",
                "local_ref",
                "name",
                "owner_type",
                "ref",
                "owner",
            },
            set(inspect.signature(KeySummary).parameters),
        )

    def test_list_response_uses_items_contract(self):
        response = PaginatedResponseKeySummary.from_dict(
            {
                "items": [
                    {
                        "created": "2026-09-01T12:00:00Z",
                        "encrypted": True,
                        "id": 42,
                        "local_ref": "remote",
                        "name": "Remote Attune",
                        "owner_type": "pack",
                        "ref": "pack.attune.remote",
                        "owner": "attune",
                    }
                ],
                "pagination": {
                    "has_next": False,
                    "has_previous": False,
                    "page": 1,
                    "page_size": 50,
                    "total_items": 1,
                    "total_pages": 1,
                },
            }
        )
        self.assertEqual("remote", response.items[0].local_ref)
        self.assertEqual("attune", response.items[0].owner)
        self.assertEqual("items", next(iter(response.to_dict())))

    def test_key_endpoint_signatures_match_current_contract(self):
        self.assertEqual(
            {"client", "body"}, set(inspect.signature(create_key.sync).parameters)
        )
        self.assertEqual(
            {"client", "owner_type", "owner", "page", "per_page"},
            set(inspect.signature(list_keys.sync).parameters),
        )
        for endpoint in (get_key.sync, delete_key.sync):
            self.assertEqual(
                {"ref", "client"}, set(inspect.signature(endpoint).parameters)
            )
        self.assertEqual(
            {"ref", "client", "body"},
            set(inspect.signature(update_key.sync).parameters),
        )

    def test_key_list_adapter_uses_current_filter_and_pagination_names(self):
        sent = []

        with mock.patch.object(actions, "build_client", return_value=object()), mock.patch.object(
            actions,
            "import_symbol",
            return_value=lambda **kwargs: sent.append(kwargs),
        ):
            actions.key_list(
                {
                    "owner_type": "pack",
                    "owner": "attune",
                    "page": 2,
                    "per_page": 25,
                }
            )

        self.assertEqual(
            {
                "client",
                "owner_type",
                "owner",
                "page",
                "per_page",
            },
            set(sent[0]),
        )
        self.assertEqual(25, sent[0]["per_page"])

    def test_key_actions_have_metadata_and_dispatch_handlers(self):
        for name in ("get", "list", "create", "update", "delete"):
            action_ref = f"attune.key_{name}"
            self.assertIn(action_ref, actions.ACTIONS)
            metadata = (ROOT / "actions" / f"key_{name}.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn(f"ref: {action_ref}", metadata)

        create_metadata = (ROOT / "actions" / "key_create.yaml").read_text(
            encoding="utf-8"
        )
        for field in (
            "local_ref",
            "owner_action_ref",
            "owner_identity_login",
            "owner_pack_ref",
            "owner_sensor_ref",
        ):
            self.assertIn(f"  {field}:", create_metadata)
        for removed in (
            "  owner_action:",
            "  owner_identity:",
            "  owner_pack:",
            "  owner_sensor:",
        ):
            self.assertNotIn(removed, create_metadata)

        list_metadata = (ROOT / "actions" / "key_list.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("  per_page:", list_metadata)
        self.assertNotIn("  page_size:", list_metadata)

    def test_key_crud_paths_use_canonical_ref(self):
        canonical_ref = "identity.alice+sdk@example.com.remote"
        expected_url = "/api/v1/keys/identity.alice%2Bsdk%40example.com.remote"
        self.assertEqual(expected_url, get_key._get_kwargs(ref=canonical_ref)["url"])
        self.assertEqual(expected_url, delete_key._get_kwargs(ref=canonical_ref)["url"])
        self.assertEqual(
            expected_url,
            update_key._get_kwargs(
                ref=canonical_ref, body=UpdateKeyRequest(name="Rotated")
            )["url"],
        )

if __name__ == "__main__":
    unittest.main()

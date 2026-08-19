from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from attune_meta_pack import client_factory
from attune_meta_pack.errors import MetaPackError


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
            "credential_key": "attune.remote",
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

        fetch.assert_called_once_with("attune.remote")
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
            credential = client_factory._fetch_external_credential("attune.remote")

        get_key.assert_called_once_with(
            "attune.remote", client=context_client, decrypt=True
        )
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
            client_factory.build_client({"credential_key": "attune.remote"})


if __name__ == "__main__":
    unittest.main()

# Attune Meta-Pack Proposal

## Direction

This pack should use a generated API client from Attune's OpenAPI spec rather than hand-written `curl` wrappers.

That matches the existing project direction:

- The API publishes OpenAPI at `/api-spec/openapi.json`
- The web UI already uses a generated TypeScript client
- The test suite already uses a generated Python client

For pack actions, the best fit is a generated Python client:

- most actions are API callouts, not shell-heavy local operations
- Python gives better request/response typing than shell scripts
- the generated client already exists as a proven pattern in `tests/generated_client`
- actions can stay thin and schema-aligned as the API evolves

## Source Of Truth

Use the backend OpenAPI spec as the single source of truth for all action inputs and outputs.

Relevant repo references:

- `crates/api/src/openapi.rs`
- `crates/api/src/server.rs`
- `scripts/generate-python-client.sh`
- `tests/generated_client/`
- `web/package.json`
- `web/src/api/`
- `scripts/generate-python-client.sh`
- `packs.external/attune/scripts/generate_client.sh`

## Proposed Architecture

### Runtime

Use a Python runtime for this pack.

### Generated client layout

Generate and vendor a Python client into the pack, for example:

```text
packs.external/attune/
├── pack.yaml
├── README.md
├── actions/
│   ├── execution_run.py
│   ├── execution_run.yaml
│   ├── rule_create.py
│   ├── rule_create.yaml
│   └── ...
├── lib/
│   ├── attune_client/            # generated from OpenAPI
│   ├── client_factory.py         # token/base-url/bootstrap helpers
│   ├── result_utils.py           # response normalization
│   ├── errors.py                 # pack-level error mapping
│   └── helpers.py                # ref resolution / common helpers
├── scripts/
│   └── generate_client.sh
└── requirements.txt
```

### Generation workflow

Recommended workflow:

1. Fetch OpenAPI spec from a running Attune API.
2. Generate Python client with `openapi-python-client`.
3. Commit generated client code into `lib/attune_client/`.
4. Keep action implementations hand-written, but only as thin adapters over the generated client.

The pack now includes its own helper script for this flow:

```bash
cd packs.external/attune
./scripts/generate_client.sh
```

Environment overrides:

- `ATTUNE_API_URL` to point at a non-default API host
- `OPENAPI_CLIENT_CMD` to point at a specific `openapi-python-client` binary

This is better than generating at action runtime:

- no runtime dependency on generator tooling
- no runtime dependency on a reachable spec endpoint
- reproducible pack contents
- pack reviews can inspect actual generated client diffs

## Initial Skeleton

The repository now includes:

- `pack.yaml`
- `requirements.txt`
- `lib/attune_meta_pack/` shared helpers
- `lib/attune_client/` vendored generated client
- `actions/dispatch.py` generic dispatcher keyed by `ATTUNE_ACTION`
- direct wrappers currently scaffolded for a deliberately trimmed subset:
  - executions
  - action listing
  - rules
  - triggers and webhook lifecycle
  - sensors
  - workflows
  - pack registration, installation, testing, and workflow sync
  - inquiry inspection and response

The actions intentionally call the generated client and fail fast with a clear
message if the client has not been generated or its Python dependencies are not
installed.

The pack does not define its own Python runtime. It depends on the system-level
Python runtime via `runtime_deps` and uses `runner_type: python` in actions.

### Client bootstrap

Each action should construct the generated client through a shared helper:

- `credential_key`: optional `pack.attune.*` Key containing external instance credentials
- `api_url`: default `http://localhost:8080`
- `api_token`: optional explicit token
- fallback token: `ATTUNE_API_TOKEN`
- `verify_ssl`: default `true`
- `timeout`: action-specific

An external instance credential should be stored in an encrypted Key containing
a JSON object:

```json
{
  "api_url": "https://attune.example.com",
  "api_token": "...",
  "verify_ssl": true,
  "timeout_seconds": 30
}
```

When `credential_key` is provided, the Key's target URL, token, TLS setting, and
optional timeout take precedence over inline action parameters and the local
execution environment. The Key itself is always read from the Attune instance
executing the action, using its execution-scoped client.

Use `AuthenticatedClient` when a bearer token is available, otherwise `Client`
for the small number of public endpoints that may still be wrapped later.

### Action implementation style

Each action should do only four things:

1. Parse action params.
2. Build the generated request model.
3. Call the generated endpoint function.
4. Return normalized JSON.

Avoid embedding endpoint-specific HTTP logic in each action.

### Dispatcher pattern

Most action YAML files use a single `dispatch.py` entry point. The worker sets
`ATTUNE_ACTION` to the action reference being executed, and the dispatcher maps
that ref to the corresponding thin wrapper in `lib/attune_meta_pack/actions.py`.

That keeps the pack layout simple:

- one shared import/bootstrap path
- one shared error and output contract
- thin wrapper functions per API operation
- generated client as the only HTTP layer

### Current omissions

The generated client still exposes a few operations that are not wrapped yet:

- binary download endpoints such as agent binary download

`attune.execution_run` also remains conditional on the generated client
including the manual execution endpoint. The current vendored client does not
contain `create_execution`.

## Design Rules

- Prefer one action per OpenAPI operation for Tier 1 and Tier 2.
- Keep names resource-oriented: `attune.execution.run`, `attune.rule.enable`, `attune.pack.sync_workflows`.
- Accept refs wherever the API uses refs.
- Preserve API field names in outputs unless there is a strong reason to adapt them.
- Put common normalization in shared helpers, not in individual actions.
- Treat generated code as vendored code: regenerate, do not hand-edit.

## Action Portfolio

The pack is intentionally trimmed to operations that still make sense when an
Attune action calls back into Attune with its execution-scoped token.

Kept actions:

- `attune.action_list`
- `attune.execution.get`
- `attune.execution.list`
- `attune.execution.list_by_enforcement`
- `attune.execution.list_by_status`
- `attune.execution.run`
- `attune.execution.stats`
- `attune.rule.get`
- `attune.rule.list`
- `attune.rule.create`
- `attune.rule.update`
- `attune.rule.enable`
- `attune.rule.disable`
- `attune.rule.delete`
- `attune.trigger.get`
- `attune.trigger.list`
- `attune.trigger.create`
- `attune.trigger.update`
- `attune.trigger.enable`
- `attune.trigger.disable`
- `attune.trigger.delete`
- `attune.webhook_enable`
- `attune.webhook_disable`
- `attune.webhook_regenerate`
- `attune.sensor.get`
- `attune.sensor.list`
- `attune.sensor.enable`
- `attune.sensor.disable`
- `attune.workflow.get`
- `attune.workflow.list`
- `attune.workflow.create`
- `attune.workflow.update`
- `attune.workflow.delete`
- `attune.pack.get`
- `attune.pack.list`
- `attune.pack.register`
- `attune.pack.install`
- `attune.pack.test`
- `attune.pack.test_history`
- `attune.pack.latest_test`
- `attune.pack.sync_workflows`
- `attune.pack.validate_workflows`
- `attune.inquiry.get`
- `attune.inquiry.list`
- `attune.inquiry.list_by_execution`
- `attune.inquiry.list_by_status`
- `attune.inquiry.respond`

Deferred or intentionally omitted from the trimmed pack:

- auth/session bootstrap actions
- identity, permission, and role management
- direct key management
- runtime CRUD
- health and agent introspection
- event and enforcement inspection
- synthetic webhook receipt
- artifact management
- sensor create/update/delete

## Tier 3 helpers

These should be convenience actions built on top of Tier 1/Tier 2 wrappers, not direct endpoint mirrors.

- `attune.execution.wait`
- `attune.execution.run_and_wait`
- `attune.execution.run_and_collect_artifacts`
- `attune.rule.ensure_present`
- `attune.trigger.ensure_webhook`
- `attune.pack.register_and_test`
- `attune.pack.install_and_sync`
- `attune.artifact.upsert_progress`
- `attune.system.summary`

## Explicit Non-Goals For V1

- Do not build shell `curl` wrappers for every endpoint.
- Do not manually maintain request/response models in the pack.
- Do not expose direct `event.create` as a normal workflow action until the auth/token model is clear.
  - The API currently restricts direct event creation for normal user sessions.
- Do not over-normalize outputs.

## Recommended First Implementation Slice

Build the pack in this order:

1. Shared Python runtime and vendored generated client.
2. Shared client bootstrap and response helpers.
3. Execution actions.
4. Rule, trigger, and sensor actions.
5. Workflow and pack actions.
6. Key and artifact actions.
7. Admin/operator actions.
8. Helper/composite actions.

## Regeneration Policy

When the API changes:

1. Regenerate the vendored Python client from the latest OpenAPI spec.
2. Review generated diffs.
3. Update action adapters only where endpoint signatures or models changed.
4. Add or remove actions when new operations appear or old ones are retired.

This keeps the meta-pack aligned with the actual Attune API instead of a second manually-maintained contract.

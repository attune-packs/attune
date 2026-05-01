#!/bin/bash
# Generate vendored Python client for the attune meta-pack from Attune's OpenAPI spec.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${PACK_DIR}/lib/attune_client"
TEMP_DIR="$(mktemp -d)"
TEMP_SPEC="${TEMP_DIR}/openapi.json"
TEMP_OUT="${TEMP_DIR}/generated"

API_URL="${ATTUNE_API_URL:-http://localhost:8080}"
OPENAPI_SPEC_URL="${API_URL}/api-spec/openapi.json"
OPENAPI_CLIENT_CMD="${OPENAPI_CLIENT_CMD:-openapi-python-client}"

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

echo "==> Generating attune meta-pack Python client"
echo "API URL: ${API_URL}"
echo "Spec URL: ${OPENAPI_SPEC_URL}"
echo "Output: ${OUTPUT_DIR}"

if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl is required" >&2
    exit 1
fi

if ! command -v "${OPENAPI_CLIENT_CMD}" >/dev/null 2>&1; then
    echo "ERROR: ${OPENAPI_CLIENT_CMD} not found in PATH" >&2
    echo "Install openapi-python-client first, or set OPENAPI_CLIENT_CMD to its full path." >&2
    exit 1
fi

echo "==> Checking API health"
curl -sf "${API_URL}/health" >/dev/null

echo "==> Downloading OpenAPI spec"
curl -sf "${OPENAPI_SPEC_URL}" -o "${TEMP_SPEC}"

echo "==> Generating Python client"
"${OPENAPI_CLIENT_CMD}" generate \
    --path "${TEMP_SPEC}" \
    --output-path "${TEMP_OUT}" \
    --overwrite \
    --meta none

mkdir -p "${PACK_DIR}/lib"
rm -rf "${OUTPUT_DIR}"
mv "${TEMP_OUT}" "${OUTPUT_DIR}"

echo "==> Generated client written to ${OUTPUT_DIR}"
echo "Next steps:"
echo "  1. Review generated diffs"
echo "  2. Update action adapters if endpoint signatures changed"

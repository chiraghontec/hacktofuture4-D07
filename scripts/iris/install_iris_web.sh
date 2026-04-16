#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-}"
IRIS_REF="${2:-v2.4.27}"

if [[ -z "${TARGET_DIR}" ]]; then
  echo "Usage: $0 <target_dir> [iris_ref]"
  exit 1
fi

mkdir -p "$(dirname "${TARGET_DIR}")"

if [[ ! -d "${TARGET_DIR}/.git" ]]; then
  git clone https://github.com/dfir-iris/iris-web.git "${TARGET_DIR}"
fi

cd "${TARGET_DIR}"

git fetch --tags --force

git checkout "${IRIS_REF}"

if [[ ! -f .env ]]; then
  cp .env.model .env
  echo "Created ${TARGET_DIR}/.env from .env.model"
fi

random_hex() {
  python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
}

update_env_if_match() {
  local key="$1"
  local expected="$2"
  local replacement="$3"
  local current

  current=$(grep -E "^${key}=" .env | head -1 | cut -d '=' -f2- || true)
  if [[ "${current}" == "${expected}" ]]; then
    sed -i.bak "s|^${key}=.*|${key}=${replacement}|" .env
  fi
}

update_env_if_match "POSTGRES_PASSWORD" "__MUST_BE_CHANGED__" "$(random_hex)"
update_env_if_match "POSTGRES_ADMIN_PASSWORD" "__MUST_BE_CHANGED__" "$(random_hex)"
update_env_if_match "IRIS_SECRET_KEY" "AVerySuperSecretKey-SoNotThisOne" "$(random_hex)"
update_env_if_match "IRIS_SECURITY_PASSWORD_SALT" "ARandomSalt-NotThisOneEither" "$(random_hex)"
update_env_if_match "SERVER_NAME" "iris.app.dev" "localhost"

rm -f .env.bak

echo "iris-web is ready in ${TARGET_DIR} at ref ${IRIS_REF}"

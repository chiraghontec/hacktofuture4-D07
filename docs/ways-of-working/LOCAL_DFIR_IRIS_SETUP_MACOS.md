# Local DFIR-IRIS Setup on macOS

This runbook installs and runs the official `dfir-iris/iris-web` stack locally for UniOps integration testing.

## Prerequisites

- Docker Desktop running
- `git` installed
- Ports available:
  - `443` for IRIS HTTPS
  - `5672` for RabbitMQ
  - `5432` for PostgreSQL

## Install and Start

From repository root:

```bash
make iris-install
make iris-up
```

This installs `dfir-iris/iris-web` to `.vendor/iris-web` and checks out `v2.4.27`.

## Get Initial Admin Password

```bash
make iris-admin-password
```

Look for the line containing `create_safe_admin`.

## Access IRIS

Open:

- `https://localhost`

Use username `administrator` and the password from logs.

## Create API Key for UniOps

In DFIR-IRIS UI:

1. Open user settings for `administrator`.
2. Generate an API key.
3. Put it in project `.env` as `IRIS_API_KEY`.

## UniOps Environment Mapping

Use these keys in `.env`:

```env
IRIS_BASE_URL=https://localhost
IRIS_API_KEY=replace_me
IRIS_PROJECT_KEY=SERVICE-X
IRIS_VERIFY_SSL=false

CONFLUENCE_BASE_URL=https://confluence.example.internal
CONFLUENCE_SPACE_KEY=OPS
CONFLUENCE_API_TOKEN=replace_me
CONFLUENCE_EMAIL=replace_me@example.com
```

## Stop Stack

```bash
make iris-down
```

## Tail App Logs

```bash
make iris-logs
```

## Notes

- `IRIS_VERIFY_SSL=false` is for local self-signed cert setup only.
- For production-like environments, set valid TLS certs and SSL verification on.

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_numbered_steps(markdown: str) -> list[str]:
    steps: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if match:
            steps.append(match.group(1).strip())
    return steps


def parse_dash_kv(markdown: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        parsed[key.strip().lower().replace(" ", "_")] = value.strip()
    return parsed


def build_bundle(root: Path, output_dir: Path, project_key: str) -> dict[str, Any]:
    data_dir = root / "data"

    confluence_runbook_path = data_dir / "confluence" / "redis-latency-runbook.md"
    runbook_path = data_dir / "runbooks" / "high-cpu-service-x.md"
    incident_path = data_dir / "incidents" / "incident-2026-04-08.json"
    github_path = data_dir / "github" / "pr-rollback-example.md"
    slack_path = data_dir / "slack" / "customer-xyz-thread.md"

    confluence_runbook = read_text(confluence_runbook_path)
    high_cpu_runbook = read_text(runbook_path)
    incident = read_json(incident_path)
    github_md = read_text(github_path)
    slack_md = read_text(slack_path)

    redis_steps = parse_numbered_steps(confluence_runbook)
    cpu_steps = parse_numbered_steps(high_cpu_runbook)
    github_context = parse_dash_kv(github_md)

    now = datetime.now(UTC).isoformat()

    incident_seed = {
        "project_key": project_key,
        "source": "uniops-data-bundle",
        "external_incident_id": incident.get("id"),
        "service": incident.get("service", "service-x"),
        "severity": incident.get("severity", "SEV-2"),
        "summary": incident.get("summary", "Redis latency incident"),
        "status": incident.get("status", "resolved"),
        "tags": ["redis", "latency", "production"],
        "created_at": now,
    }

    resolution_plan = {
        "project_key": project_key,
        "service": incident_seed["service"],
        "incident_summary": incident_seed["summary"],
        "workflow": [
            "detect",
            "triage",
            "diagnose",
            "propose_action",
            "approval",
            "execute",
            "resolve",
            "postmortem",
        ],
        "runbooks": [
            {
                "name": "Redis Latency Runbook",
                "source_path": "data/confluence/redis-latency-runbook.md",
                "steps": redis_steps,
            },
            {
                "name": "High CPU Runbook for Service X",
                "source_path": "data/runbooks/high-cpu-service-x.md",
                "steps": cpu_steps,
            },
        ],
        "approval_policy": {
            "required_for_actions": ["rollback", "deploy", "update", "scale", "create"],
            "approver_role": "sre_lead",
            "note": "Rollback and scale actions require explicit SRE approval before execution.",
        },
        "operational_evidence": {
            "github": {
                "source_path": "data/github/pr-rollback-example.md",
                "pr": github_context.get("pr", "unknown"),
                "reason": github_context.get("reason", "unknown"),
                "action": github_context.get("action", "unknown"),
            },
            "slack": {
                "source_path": "data/slack/customer-xyz-thread.md",
                "summary": slack_md,
            },
        },
        "generated_at": now,
    }

    runbook_mapping = {
        "project_key": project_key,
        "incident_type": "redis_latency_spike_after_deployment",
        "service": incident_seed["service"],
        "severity_map": {
            "SEV-1": "critical",
            "SEV-2": "high",
            "SEV-3": "medium",
            "SEV-4": "low",
        },
        "runbook_links": [
            {
                "title": "Redis Latency Runbook",
                "category": "confluence",
                "path": "data/confluence/redis-latency-runbook.md",
            },
            {
                "title": "High CPU Runbook for Service X",
                "category": "runbooks",
                "path": "data/runbooks/high-cpu-service-x.md",
            },
        ],
        "required_context_sources": [
            "data/incidents/incident-2026-04-08.json",
            "data/github/pr-rollback-example.md",
            "data/slack/customer-xyz-thread.md",
        ],
    }

    manifest = {
        "bundle_name": "iris-incident-resolution-bundle",
        "project_key": project_key,
        "service": incident_seed["service"],
        "generated_at": now,
        "source_files": [
            "data/confluence/redis-latency-runbook.md",
            "data/runbooks/high-cpu-service-x.md",
            "data/incidents/incident-2026-04-08.json",
            "data/github/pr-rollback-example.md",
            "data/slack/customer-xyz-thread.md",
        ],
        "output_files": [
            "iris-incident-seed.json",
            "iris-resolution-plan.json",
            "iris-runbook-mapping.json",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "iris-incident-seed.json").write_text(json.dumps(incident_seed, indent=2), encoding="utf-8")
    (output_dir / "iris-resolution-plan.json").write_text(json.dumps(resolution_plan, indent=2), encoding="utf-8")
    (output_dir / "iris-runbook-mapping.json").write_text(json.dumps(runbook_mapping, indent=2), encoding="utf-8")
    (output_dir / "iris-import-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an IRIS incident-resolution setup bundle from UniOps data files "
            "(confluence/runbooks/incidents/github/slack)."
        )
    )
    parser.add_argument(
        "--project-key",
        default="SERVICE-X",
        help="Target IRIS project key used for incident and runbook mapping (default: SERVICE-X).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/iris/import_bundle",
        help="Output directory for generated IRIS import bundle.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = root / args.output_dir

    manifest = build_bundle(root=root, output_dir=output_dir, project_key=args.project_key)
    print("Generated IRIS import bundle:")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

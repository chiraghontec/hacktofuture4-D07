from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.routes.chat import IncidentReport, kernel
from src.adapters.confluence_client import ConfluenceClient, ConfluenceClientError
from src.adapters.github_client import GitHubClient, GitHubClientError
from src.adapters.iris_client import IrisClient, IrisClientError
from src.adapters.jira_client import JiraClient, JiraClientError
from src.adapters.slack_client import SlackClient, SlackClientError
from src.memory.three_tier_memory import MemoryDocument

router = APIRouter()


class IngestIrisResponse(BaseModel):
    ingested_count: int
    source: str
    case_id: str
    incident_report: IncidentReport


class CreateIrisIncidentRequest(BaseModel):
    case_name: str = Field(min_length=2, max_length=255)
    case_description: str = Field(min_length=2, max_length=5000)
    severity: str = "medium"
    tags: list[str] = Field(default_factory=list)
    case_customer: int = 1
    case_soc_id: str = ""
    classification_id: int | None = None
    case_template_id: str | None = None
    custom_attributes: dict[str, object] | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            normalized = tag.strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned


class CreateIrisIncidentResponse(BaseModel):
    source: str
    case_id: str
    incident_report: IncidentReport


class IngestConfluenceRequest(BaseModel):
    page_ids: list[str] = Field(min_length=1)

    @field_validator("page_ids")
    @classmethod
    def validate_page_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for page_id in value:
            normalized = page_id.strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)

        if not cleaned:
            raise ValueError("page_ids must contain at least one non-empty page id")
        return cleaned


class IngestConfluenceResult(BaseModel):
    page_id: str
    status: Literal["ingested", "failed"]
    title: str | None = None
    error: str | None = None


class IngestConfluenceResponse(BaseModel):
    ingested_count: int
    failed_count: int
    source: str
    results: list[IngestConfluenceResult]


class GitHubIssueRef(BaseModel):
    repository: str = Field(min_length=3)
    issue_number: int = Field(gt=0)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        normalized = value.strip()
        if "/" not in normalized:
            raise ValueError("repository must be in owner/repo format")
        return normalized


class IngestGitHubRequest(BaseModel):
    issue_refs: list[GitHubIssueRef] = Field(min_length=1)


class IngestGitHubResult(BaseModel):
    repository: str
    issue_number: int
    status: Literal["ingested", "failed"]
    title: str | None = None
    url: str | None = None
    error: str | None = None


class IngestGitHubResponse(BaseModel):
    ingested_count: int
    failed_count: int
    source: str
    results: list[IngestGitHubResult]


class IngestJiraRequest(BaseModel):
    issue_keys: list[str] = Field(min_length=1)

    @field_validator("issue_keys")
    @classmethod
    def validate_issue_keys(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for issue_key in value:
            normalized = issue_key.strip().upper()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)

        if not cleaned:
            raise ValueError("issue_keys must contain at least one non-empty issue key")
        return cleaned


class IngestJiraResult(BaseModel):
    issue_key: str
    status: Literal["ingested", "failed"]
    summary: str | None = None
    url: str | None = None
    error: str | None = None


class IngestJiraResponse(BaseModel):
    ingested_count: int
    failed_count: int
    source: str
    results: list[IngestJiraResult]


class SlackChannelRef(BaseModel):
    channel_id: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=200)

    @field_validator("channel_id")
    @classmethod
    def validate_channel_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("channel_id must be non-empty")
        return normalized


class IngestSlackChannelsRequest(BaseModel):
    channels: list[SlackChannelRef] = Field(min_length=1)

    @field_validator("channels")
    @classmethod
    def dedupe_channels(cls, value: list[SlackChannelRef]) -> list[SlackChannelRef]:
        deduped: list[SlackChannelRef] = []
        seen: set[str] = set()

        for ref in value:
            if ref.channel_id in seen:
                continue
            seen.add(ref.channel_id)
            deduped.append(ref)

        if not deduped:
            raise ValueError("channels must contain at least one valid channel")
        return deduped


class IngestSlackChannelResult(BaseModel):
    channel_id: str
    status: Literal["ingested", "failed"]
    message_count: int | None = None
    error: str | None = None


class IngestSlackChannelsResponse(BaseModel):
    ingested_count: int
    failed_count: int
    source: str
    results: list[IngestSlackChannelResult]


class SlackThreadRef(BaseModel):
    channel_id: str = Field(min_length=1)
    thread_ts: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=200)

    @field_validator("channel_id")
    @classmethod
    def validate_thread_channel_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("channel_id must be non-empty")
        return normalized

    @field_validator("thread_ts")
    @classmethod
    def validate_thread_ts(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("thread_ts must be non-empty")
        return normalized


class IngestSlackThreadsRequest(BaseModel):
    threads: list[SlackThreadRef] = Field(min_length=1)

    @field_validator("threads")
    @classmethod
    def dedupe_threads(cls, value: list[SlackThreadRef]) -> list[SlackThreadRef]:
        deduped: list[SlackThreadRef] = []
        seen: set[tuple[str, str]] = set()

        for ref in value:
            key = (ref.channel_id, ref.thread_ts)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ref)

        if not deduped:
            raise ValueError("threads must contain at least one valid thread")
        return deduped


class IngestSlackThreadResult(BaseModel):
    channel_id: str
    thread_ts: str
    status: Literal["ingested", "failed"]
    message_count: int | None = None
    error: str | None = None


class IngestSlackThreadsResponse(BaseModel):
    ingested_count: int
    failed_count: int
    source: str
    results: list[IngestSlackThreadResult]


def _render_slack_messages(messages: list[dict[str, str]]) -> str:
    rendered_lines: list[str] = []
    for message in messages:
        ts = message.get("ts", "")
        user = message.get("user", "")
        text = message.get("text", "")
        rendered_lines.append(f"- [{ts}] {user}: {text}")

    return "\n".join(rendered_lines)


@router.post("/ingest/iris", response_model=IngestIrisResponse)
def ingest_iris(case_id: str) -> IngestIrisResponse:
    try:
        client = IrisClient.from_env()
        case_payload = client.fetch_case(case_id=case_id)
        incident_report = IncidentReport(**case_payload)
    except (IrisClientError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    doc = MemoryDocument(
        title=f"IRIS Case {incident_report.case_id or case_id}",
        path=f"runtime/iris/{incident_report.case_id or case_id}.json",
        source_type="incidents",
        content=json.dumps(incident_report.model_dump(mode="json"), indent=2, ensure_ascii=False),
    )
    kernel.memory.ingest_runtime_document(doc)

    return IngestIrisResponse(
        ingested_count=1,
        source="iris",
        case_id=incident_report.case_id or case_id,
        incident_report=incident_report,
    )


@router.post("/incidents/create", response_model=CreateIrisIncidentResponse)
def create_iris_incident(payload: CreateIrisIncidentRequest) -> CreateIrisIncidentResponse:
    try:
        client = IrisClient.from_env()
        case_payload = client.create_incident(
            case_name=payload.case_name,
            case_description=payload.case_description,
            severity=payload.severity,
            tags=payload.tags,
            case_customer=payload.case_customer,
            case_soc_id=payload.case_soc_id,
            classification_id=payload.classification_id,
            case_template_id=payload.case_template_id,
            custom_attributes=payload.custom_attributes,
        )
        incident_report = IncidentReport(**case_payload)
    except (IrisClientError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    case_id = incident_report.case_id or "new"
    doc = MemoryDocument(
        title=f"IRIS Case {case_id}",
        path=f"runtime/iris/{case_id}.json",
        source_type="incidents",
        content=json.dumps(incident_report.model_dump(mode="json"), indent=2, ensure_ascii=False),
    )
    kernel.memory.ingest_runtime_document(doc)

    return CreateIrisIncidentResponse(
        source="iris",
        case_id=case_id,
        incident_report=incident_report,
    )


@router.post("/ingest/confluence", response_model=IngestConfluenceResponse)
def ingest_confluence(payload: IngestConfluenceRequest) -> IngestConfluenceResponse:
    try:
        client = ConfluenceClient.from_env()
    except ConfluenceClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: list[IngestConfluenceResult] = []
    for page_id in payload.page_ids:
        try:
            page_payload = client.fetch_page(page_id=page_id)
            content = f"# {page_payload['title']}\n\n{page_payload['body']}\n\nSource: {page_payload['source_url']}\n"
            doc = MemoryDocument(
                title=page_payload["title"],
                path=f"runtime/confluence/{page_id}.md",
                source_type="confluence",
                content=content,
            )
            kernel.memory.ingest_runtime_document(doc)
            results.append(
                IngestConfluenceResult(
                    page_id=page_id,
                    status="ingested",
                    title=page_payload["title"],
                )
            )
        except Exception as exc:  # Keep batch ingestion resilient to per-page failures.
            results.append(
                IngestConfluenceResult(
                    page_id=page_id,
                    status="failed",
                    error=str(exc),
                )
            )

    ingested_count = len([item for item in results if item.status == "ingested"])
    failed_count = len(results) - ingested_count

    return IngestConfluenceResponse(
        ingested_count=ingested_count,
        failed_count=failed_count,
        source="confluence",
        results=results,
    )


@router.post("/ingest/github", response_model=IngestGitHubResponse)
def ingest_github(payload: IngestGitHubRequest) -> IngestGitHubResponse:
    try:
        client = GitHubClient.from_env()
    except GitHubClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    unique_refs: list[GitHubIssueRef] = []
    seen: set[tuple[str, int]] = set()
    for ref in payload.issue_refs:
        key = (ref.repository.strip(), ref.issue_number)
        if key in seen:
            continue
        seen.add(key)
        unique_refs.append(ref)

    results: list[IngestGitHubResult] = []
    for ref in unique_refs:
        try:
            issue_payload = client.fetch_issue(repository=ref.repository, issue_number=ref.issue_number)
            title = str(issue_payload.get("title", ""))
            issue_url = str(issue_payload.get("url", ""))
            state = str(issue_payload.get("state", "unknown"))
            body = str(issue_payload.get("body", "")).strip()

            content = (
                f"# GitHub Issue {ref.repository}#{ref.issue_number}\n\n"
                f"Title: {title}\n"
                f"State: {state}\n"
                f"URL: {issue_url}\n\n"
                f"{body}\n"
            )
            safe_repo = ref.repository.replace("/", "__")
            doc = MemoryDocument(
                title=f"{ref.repository}#{ref.issue_number}",
                path=f"runtime/github/{safe_repo}-{ref.issue_number}.md",
                source_type="github",
                content=content,
            )
            kernel.memory.ingest_runtime_document(doc)
            results.append(
                IngestGitHubResult(
                    repository=ref.repository,
                    issue_number=ref.issue_number,
                    status="ingested",
                    title=title,
                    url=issue_url,
                )
            )
        except Exception as exc:  # Keep batch ingestion resilient to per-issue failures.
            results.append(
                IngestGitHubResult(
                    repository=ref.repository,
                    issue_number=ref.issue_number,
                    status="failed",
                    error=str(exc),
                )
            )

    ingested_count = len([item for item in results if item.status == "ingested"])
    failed_count = len(results) - ingested_count

    return IngestGitHubResponse(
        ingested_count=ingested_count,
        failed_count=failed_count,
        source="github",
        results=results,
    )


@router.post("/ingest/jira", response_model=IngestJiraResponse)
def ingest_jira(payload: IngestJiraRequest) -> IngestJiraResponse:
    try:
        client = JiraClient.from_env()
    except JiraClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: list[IngestJiraResult] = []
    for issue_key in payload.issue_keys:
        try:
            issue_payload = client.fetch_issue(issue_key=issue_key)
            summary = str(issue_payload.get("summary", ""))
            issue_url = str(issue_payload.get("url", ""))
            status = str(issue_payload.get("status", "unknown"))
            priority = str(issue_payload.get("priority", ""))
            assignee = str(issue_payload.get("assignee", ""))
            description = issue_payload.get("description")

            if isinstance(description, str):
                description_text = description
            else:
                description_text = json.dumps(description, ensure_ascii=False, indent=2) if description else ""

            content = (
                f"# Jira Issue {issue_key}\n\n"
                f"Summary: {summary}\n"
                f"Status: {status}\n"
                f"Priority: {priority}\n"
                f"Assignee: {assignee}\n"
                f"URL: {issue_url}\n\n"
                f"{description_text}\n"
            )
            doc = MemoryDocument(
                title=f"Jira {issue_key}",
                path=f"runtime/jira/{issue_key}.md",
                source_type="jira",
                content=content,
            )
            kernel.memory.ingest_runtime_document(doc)
            results.append(
                IngestJiraResult(
                    issue_key=issue_key,
                    status="ingested",
                    summary=summary,
                    url=issue_url,
                )
            )
        except Exception as exc:  # Keep batch ingestion resilient to per-issue failures.
            results.append(
                IngestJiraResult(
                    issue_key=issue_key,
                    status="failed",
                    error=str(exc),
                )
            )

    ingested_count = len([item for item in results if item.status == "ingested"])
    failed_count = len(results) - ingested_count

    return IngestJiraResponse(
        ingested_count=ingested_count,
        failed_count=failed_count,
        source="jira",
        results=results,
    )


@router.post("/ingest/slack/channels", response_model=IngestSlackChannelsResponse)
def ingest_slack_channels(payload: IngestSlackChannelsRequest) -> IngestSlackChannelsResponse:
    try:
        client = SlackClient.from_env()
    except SlackClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: list[IngestSlackChannelResult] = []
    for ref in payload.channels:
        try:
            channel_payload = client.fetch_channel_messages(channel_id=ref.channel_id, limit=ref.limit)
            messages = channel_payload.get("messages", [])
            message_count = int(channel_payload.get("message_count", 0))

            content = (
                f"# Slack Channel {ref.channel_id}\n\n"
                f"Message Count: {message_count}\n"
                f"Has More: {channel_payload.get('has_more', False)}\n\n"
                f"{_render_slack_messages(messages if isinstance(messages, list) else [])}\n"
            )

            doc = MemoryDocument(
                title=f"Slack Channel {ref.channel_id}",
                path=f"runtime/slack/channel-{ref.channel_id}.md",
                source_type="slack",
                content=content,
            )
            kernel.memory.ingest_runtime_document(doc)

            results.append(
                IngestSlackChannelResult(
                    channel_id=ref.channel_id,
                    status="ingested",
                    message_count=message_count,
                )
            )
        except Exception as exc:  # Keep batch ingestion resilient to per-channel failures.
            results.append(
                IngestSlackChannelResult(
                    channel_id=ref.channel_id,
                    status="failed",
                    error=str(exc),
                )
            )

    ingested_count = len([item for item in results if item.status == "ingested"])
    failed_count = len(results) - ingested_count

    return IngestSlackChannelsResponse(
        ingested_count=ingested_count,
        failed_count=failed_count,
        source="slack",
        results=results,
    )


@router.post("/ingest/slack/threads", response_model=IngestSlackThreadsResponse)
def ingest_slack_threads(payload: IngestSlackThreadsRequest) -> IngestSlackThreadsResponse:
    try:
        client = SlackClient.from_env()
    except SlackClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: list[IngestSlackThreadResult] = []
    for ref in payload.threads:
        try:
            thread_payload = client.fetch_thread_messages(
                channel_id=ref.channel_id,
                thread_ts=ref.thread_ts,
                limit=ref.limit,
            )
            messages = thread_payload.get("messages", [])
            message_count = int(thread_payload.get("message_count", 0))
            safe_thread_ts = ref.thread_ts.replace(".", "_")

            content = (
                f"# Slack Thread {ref.channel_id}:{ref.thread_ts}\n\n"
                f"Message Count: {message_count}\n"
                f"Has More: {thread_payload.get('has_more', False)}\n\n"
                f"{_render_slack_messages(messages if isinstance(messages, list) else [])}\n"
            )

            doc = MemoryDocument(
                title=f"Slack Thread {ref.channel_id}:{ref.thread_ts}",
                path=f"runtime/slack/thread-{ref.channel_id}-{safe_thread_ts}.md",
                source_type="slack",
                content=content,
            )
            kernel.memory.ingest_runtime_document(doc)

            results.append(
                IngestSlackThreadResult(
                    channel_id=ref.channel_id,
                    thread_ts=ref.thread_ts,
                    status="ingested",
                    message_count=message_count,
                )
            )
        except Exception as exc:  # Keep batch ingestion resilient to per-thread failures.
            results.append(
                IngestSlackThreadResult(
                    channel_id=ref.channel_id,
                    thread_ts=ref.thread_ts,
                    status="failed",
                    error=str(exc),
                )
            )

    ingested_count = len([item for item in results if item.status == "ingested"])
    failed_count = len(results) - ingested_count

    return IngestSlackThreadsResponse(
        ingested_count=ingested_count,
        failed_count=failed_count,
        source="slack",
        results=results,
    )

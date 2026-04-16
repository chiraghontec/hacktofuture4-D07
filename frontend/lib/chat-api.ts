export type ChatRequest = {
  message?: string;
  session_id: string;
};

export type DedupSummary = {
  documents: {
    scanned: number;
    duplicates: number;
  };
  transcripts: {
    scanned: number;
    duplicates: number;
  };
  deduped_count: number;
  duplication_ratio: number;
  last_run_at: string | null;
};

export type ChatStreamEventType =
  | "trace_started"
  | "trace_step"
  | "trace_heartbeat"
  | "trace_complete"
  | "trace_error";

export type ChatError = {
  error: string;
  trace_id: string | null;
  status_code: number;
};

export type IngestConfluenceResult = {
  page_id: string;
  status: "ingested" | "failed";
  title: string | null;
  error: string | null;
};

export type IngestConfluenceResponse = {
  ingested_count: number;
  failed_count: number;
  source: "confluence";
  results: IngestConfluenceResult[];
};

export type IncidentReport = {
  source_system: string;
  case_id?: string | null;
  report_id?: string | null;
  report_url?: string | null;
  ingested_at?: string | null;
  case_name: string;
  short_description: string;
  severity: string;
  tags: string[];
  iocs: Array<string | Record<string, unknown>>;
  timeline: Array<string | Record<string, unknown>>;
};

export type IngestIrisResponse = {
  ingested_count: number;
  source: "iris";
  case_id: string;
  incident_report: IncidentReport;
};

export type ApprovalDecision = "approve" | "reject";

export type ApprovalResponse = {
  trace_id: string;
  final_status: "executed" | "rejected";
  approval: {
    decision: ApprovalDecision;
    approver_id: string;
    comment: string;
    timestamp: string;
  };
  execution_result: {
    tool: string;
    status: string;
    output: string;
    timestamp: string;
  };
};

export type TraceStep = {
  step: string;
  agent: string;
  observation: string;
  sources: Array<{
    title: string;
    path: string;
    source_type?: string;
    score?: number;
  }>;
  metadata?: {
    stream_sequence?: number;
    retrieval_method?: string;
    query_tokens?: string[];
    llm_query_expansion?: {
      used?: boolean;
      provider?: string | null;
      model?: string | null;
      expanded_query_tokens?: string[];
    };
    confidence?: number;
    confidence_breakdown?: {
      base_confidence?: number;
      quality_bonus?: number;
      duplicate_penalty?: number;
      clean_evidence_bonus?: number;
      duplication_ratio?: number;
      final_confidence?: number;
    };
    reasoning_steps?: string[];
    evidence_scores?: Array<{
      title: string;
      path: string;
      source_type: string;
      raw_score: number;
      priority_score: number;
    }>;
    action_details?: {
      intent?: string;
      tool?: string | null;
      parameters?: Record<string, unknown>;
      approval_required?: boolean;
      risk_hint?: string | null;
    };
    risk_level?: string;
    requires_human_approval?: boolean;
    execution_reasoning?: string;
    provider?: string;
    model?: string;
    risk_hint?: string | null;
    started_at?: string;
    finished_at?: string;
    duration_ms?: number;
  };
  timestamp?: string;
};

export type ChatStreamEvent = {
  event_type: ChatStreamEventType;
  event_id: string;
  trace_id: string;
  sequence: number;
  timestamp: string;
  status: string;
  step?: string;
  agent?: string;
  observation?: string;
  sources?: TraceStep["sources"];
  metadata?: TraceStep["metadata"] & {
    dedup_summary?: DedupSummary;
    step_count?: number;
    message?: string;
  };
  answer?: string;
  needs_approval?: boolean;
  suggested_action?: string | null;
  error_code?: string;
  error?: string;
};

export type TranscriptResponse = {
  trace_id: string;
  suggested_action?: string;
  action_details?: {
    intent?: string;
    tool?: string | null;
    parameters?: Record<string, unknown>;
    approval_required?: boolean;
    risk_hint?: string | null;
  };
  needs_approval?: boolean;
  execution_status?: string;
  final_status?: string;
  approval?: ApprovalResponse["approval"];
  execution_result?: ApprovalResponse["execution_result"];
  dedup_summary?: DedupSummary;
  steps: TraceStep[];
};

const backendBaseUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL
  ?? process.env.NEXT_PUBLIC_API_BASE_URL
  ?? "http://127.0.0.1:8000";

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function errorMessageFromBody(parsedBody: unknown, statusCode: number): string {
  if (parsedBody && typeof parsedBody === "object") {
    if ("detail" in parsedBody && typeof (parsedBody as { detail?: unknown }).detail === "string") {
      return (parsedBody as { detail: string }).detail;
    }

    if ("error" in parsedBody && typeof (parsedBody as { error?: unknown }).error === "string") {
      return (parsedBody as { error: string }).error;
    }
  }

  return `Request failed with status ${statusCode}`;
}

function assertSuccess<T>(response: Response, parsedBody: unknown): T {
  if (!response.ok) {
    throw new Error(errorMessageFromBody(parsedBody, response.status));
  }

  return parsedBody as T;
}

type ParsedSSE = {
  event: string;
  id: string;
  data: string;
};

function parseSSEChunk(chunk: string): ParsedSSE | null {
  const lines = chunk
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    return null;
  }

  let event = "message";
  let id = "";
  const dataParts: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("id:")) {
      id = line.slice("id:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataParts.push(line.slice("data:".length).trimStart());
    }
  }

  return {
    event,
    id,
    data: dataParts.join("\n"),
  };
}

function eventFromParsed(parsed: ParsedSSE): ChatStreamEvent | null {
  if (!parsed.data) {
    return null;
  }

  try {
    const payload = JSON.parse(parsed.data) as ChatStreamEvent;
    if (!payload.event_id && parsed.id) {
      payload.event_id = parsed.id;
    }
    if (!payload.event_type && parsed.event) {
      payload.event_type = parsed.event as ChatStreamEventType;
    }
    return payload;
  } catch {
    return null;
  }
}

export async function streamChat(
  payload: ChatRequest,
  options: {
    onEvent: (event: ChatStreamEvent) => void;
    signal?: AbortSignal;
  },
): Promise<void> {
  const response = await fetch(`${backendBaseUrl}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    signal: options.signal,
  });

  if (!response.ok) {
    const parsedBody = await parseJson(response);
    throw new Error(errorMessageFromBody(parsedBody, response.status));
  }

  if (!response.body) {
    throw new Error("SSE stream did not provide a readable response body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      if (buffer.trim().length > 0) {
        const parsed = parseSSEChunk(buffer);
        if (parsed) {
          const event = eventFromParsed(parsed);
          if (event) {
            options.onEvent(event);
          }
        }
      }
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split(/\r?\n\r?\n/);
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const parsed = parseSSEChunk(chunk);
      if (!parsed) {
        continue;
      }
      const event = eventFromParsed(parsed);
      if (!event) {
        continue;
      }
      options.onEvent(event);
    }
  }
}

export async function ingestConfluence(pageIds: string[]): Promise<IngestConfluenceResponse> {
  const response = await fetch(`${backendBaseUrl}/api/ingest/confluence`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ page_ids: pageIds }),
    cache: "no-store",
  });

  const parsedBody = await parseJson(response);
  return assertSuccess<IngestConfluenceResponse>(response, parsedBody);
}

export async function ingestIris(caseId: string): Promise<IngestIrisResponse> {
  const query = new URLSearchParams({ case_id: caseId }).toString();
  const response = await fetch(`${backendBaseUrl}/api/ingest/iris?${query}`, {
    method: "POST",
    cache: "no-store",
  });

  const parsedBody = await parseJson(response);
  return assertSuccess<IngestIrisResponse>(response, parsedBody);
}

export async function submitApproval(
  traceId: string,
  payload: {
    decision: ApprovalDecision;
    approver_id: string;
    comment?: string;
  },
): Promise<ApprovalResponse> {
  const response = await fetch(`${backendBaseUrl}/api/approvals/${encodeURIComponent(traceId)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const parsedBody = await parseJson(response);
  return assertSuccess<ApprovalResponse>(response, parsedBody);
}

export async function getTranscript(traceId: string): Promise<TranscriptResponse> {
  const response = await fetch(`${backendBaseUrl}/api/chat/transcript/${encodeURIComponent(traceId)}`, {
    method: "GET",
    cache: "no-store",
  });

  const parsedBody = await parseJson(response);
  return assertSuccess<TranscriptResponse>(response, parsedBody);
}


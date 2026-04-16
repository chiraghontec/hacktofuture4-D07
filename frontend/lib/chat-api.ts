export type ChatRequest = {
  message?: string;
  session_id: string;
};

export type ChatResponse = {
  answer: string;
  trace_id: string;
  needs_approval: boolean;
  dedup_summary: {
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
};

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
  }>;
  timestamp?: string;
};

export type TranscriptResponse = {
  trace_id: string;
  suggested_action?: string;
  needs_approval?: boolean;
  execution_status?: string;
  final_status?: string;
  approval?: ApprovalResponse["approval"];
  execution_result?: ApprovalResponse["execution_result"];
  dedup_summary?: ChatResponse["dedup_summary"];
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

export async function postChat(payload: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${backendBaseUrl}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  const parsedBody = await parseJson(response);
  return assertSuccess<ChatResponse>(response, parsedBody);
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

export function streamTrace(traceId: string): EventSource {
  return new EventSource(`${backendBaseUrl}/api/chat/stream?trace_id=${encodeURIComponent(traceId)}`);
}

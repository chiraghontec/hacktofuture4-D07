export type ChatRequest = {
  message: string;
  session_id: string;
};

export type ChatResponse = {
  answer: string;
  trace_id: string;
  needs_approval: boolean;
};

export type ChatError = {
  error: string;
  trace_id: string | null;
  status_code: number;
};

const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function postChat(payload: ChatRequest): Promise<ChatResponse | ChatError> {
  const response = await fetch(`${backendBaseUrl}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  let parsedBody: unknown = null;

  try {
    parsedBody = await response.json();
  } catch {
    parsedBody = null;
  }

  if (
    response.ok
    && parsedBody
    && typeof parsedBody === "object"
    && "answer" in parsedBody
    && "trace_id" in parsedBody
    && "needs_approval" in parsedBody
  ) {
    return parsedBody as ChatResponse;
  }

  const statusCode = response.status;
  const errorMessage =
    parsedBody
    && typeof parsedBody === "object"
    && "error" in parsedBody
    && typeof (parsedBody as { error?: unknown }).error === "string"
      ? (parsedBody as { error: string }).error
      : `Request failed with status ${statusCode}`;
  const traceId =
    parsedBody
    && typeof parsedBody === "object"
    && "trace_id" in parsedBody
    && typeof (parsedBody as { trace_id?: unknown }).trace_id === "string"
      ? (parsedBody as { trace_id: string }).trace_id
      : null;

  return {
    error: errorMessage,
    trace_id: traceId,
    status_code: statusCode,
  };
}

export function streamTrace(traceId: string): EventSource {
  return new EventSource(`${backendBaseUrl}/api/chat/stream?trace_id=${encodeURIComponent(traceId)}`);
}

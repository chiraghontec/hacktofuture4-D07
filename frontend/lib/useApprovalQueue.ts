import { useCallback, useEffect, useState } from "react";

export type PendingAction = {
  id: string;
  trace_id: string;
  action: string;
  risk_level: string;
  reason: string;
  status: string;
  created_at: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function useApprovalQueue() {
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mutatingActionId, setMutatingActionId] = useState<string | null>(null);

  const reloadPending = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/actions/pending`);
      if (!response.ok) {
        throw new Error(`Failed to fetch pending actions (${response.status})`);
      }

      const payload = (await response.json()) as { actions: PendingAction[] };
      setActions(payload.actions);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected queue request error";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const approveAction = useCallback(
    async (actionId: string): Promise<boolean> => {
      setMutatingActionId(actionId);
      try {
        const response = await fetch(`${API_BASE_URL}/api/actions/${actionId}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decided_by: "demo-user" }),
        });

        if (!response.ok) {
          throw new Error(`Approve failed (${response.status})`);
        }

        await reloadPending();
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Approve request failed";
        setError(message);
        return false;
      } finally {
        setMutatingActionId(null);
      }
    },
    [reloadPending],
  );

  const rejectAction = useCallback(
    async (actionId: string): Promise<boolean> => {
      setMutatingActionId(actionId);
      try {
        const response = await fetch(`${API_BASE_URL}/api/actions/${actionId}/reject`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decided_by: "demo-user", reason: "Rejected from UI" }),
        });

        if (!response.ok) {
          throw new Error(`Reject failed (${response.status})`);
        }

        await reloadPending();
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Reject request failed";
        setError(message);
        return false;
      } finally {
        setMutatingActionId(null);
      }
    },
    [reloadPending],
  );

  useEffect(() => {
    void reloadPending();
  }, [reloadPending]);

  return {
    actions,
    loading,
    error,
    mutatingActionId,
    reloadPending,
    approveAction,
    rejectAction,
  };
}

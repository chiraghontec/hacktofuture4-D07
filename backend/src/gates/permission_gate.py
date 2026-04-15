from dataclasses import dataclass


@dataclass
class PermissionRequest:
    trace_id: str
    action: str


class PermissionGate:
    def evaluate(self, request: PermissionRequest) -> dict:
        # Native HITL placeholder: always requires approval for external actions.
        return {
            "trace_id": request.trace_id,
            "action": request.action,
            "requires_human_approval": True,
        }

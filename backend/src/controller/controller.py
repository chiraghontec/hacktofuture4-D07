from dataclasses import dataclass


@dataclass
class ControllerResult:
    plan: str
    trace_id: str


class ControllerKernel:
    def handle_query(self, query: str) -> ControllerResult:
        plan = f"Plan generated for query: {query}"
        return ControllerResult(plan=plan, trace_id="trace-dev-0001")

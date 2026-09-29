from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark_runner import run_benchmark_suite
from .environment import load_project_environment
from .task_kinds import list_task_kind_keys
from .task_models import AgentTaskRequest
from .task_service import AgentTaskService


def main() -> None:
    load_project_environment()
    args = _build_parser().parse_args()
    args.handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Digital IC Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the LangGraph workflow")
    _add_common_task_arguments(run_parser)
    run_parser.set_defaults(handler=_handle_run)

    queue_submit_parser = subparsers.add_parser("queue-submit", help="Submit a task into the local file-backed queue")
    _add_common_task_arguments(queue_submit_parser)
    queue_submit_parser.set_defaults(handler=_handle_queue_submit)

    queue_run_next_parser = subparsers.add_parser("queue-run-next", help="Claim and run the next queued task")
    queue_run_next_parser.set_defaults(handler=_handle_queue_run_next)

    queue_list_parser = subparsers.add_parser("queue-list", help="List queued task records")
    queue_list_parser.set_defaults(handler=_handle_queue_list)

    serve_parser = subparsers.add_parser("serve", help="Run the HTTP API and UI server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host for the API server")
    serve_parser.add_argument("--port", default=8000, type=int, help="Port for the API server")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto reload for development")
    serve_parser.set_defaults(handler=_handle_serve)

    benchmark_run_parser = subparsers.add_parser("benchmark-run", help="Run a benchmark suite and write a scored report")
    benchmark_run_parser.add_argument("--suite-dir", required=True, help="Directory containing benchmark_case.json cases")
    benchmark_run_parser.add_argument("--output-dir", required=True, help="Directory for benchmark outputs and reports")
    benchmark_run_parser.add_argument("--mode", default="fpga", choices=["fpga"], help="Execution mode")
    benchmark_run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force benchmark cases to run in dry-run mode",
    )
    benchmark_run_parser.set_defaults(handler=_handle_benchmark_run)

    return parser


def _handle_run(args: argparse.Namespace) -> None:
    service = AgentTaskService()
    execution = service.run_sync(_task_request_from_args(args))
    print(f"Artifacts written to {execution.record.request.output_dir}")


def _handle_queue_submit(args: argparse.Namespace) -> None:
    service = AgentTaskService()
    record = service.enqueue(_task_request_from_args(args))
    print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))


def _handle_queue_run_next(_: argparse.Namespace) -> None:
    service = AgentTaskService()
    execution = service.run_next_queued()
    if execution is None:
        print("No queued tasks.")
        return
    print(json.dumps(execution.record.to_dict(), ensure_ascii=False, indent=2))


def _handle_queue_list(_: argparse.Namespace) -> None:
    service = AgentTaskService()
    records = [record.to_dict() for record in service.list_queue()]
    print(json.dumps(records, ensure_ascii=False, indent=2))


def _handle_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("digital_ic_agent.api:app", host=args.host, port=args.port, reload=args.reload)


def _handle_benchmark_run(args: argparse.Namespace) -> None:
    service = AgentTaskService()
    report = run_benchmark_suite(
        service=service,
        suite_dir=Path(args.suite_dir),
        output_dir=Path(args.output_dir),
        mode=args.mode,
        dry_run=True if args.dry_run else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _add_common_task_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-file", required=True, help="Input requirement file")
    parser.add_argument("--output-dir", required=True, help="Directory for artifacts")
    parser.add_argument("--title", help="Optional task title for queue/API reuse")
    parser.add_argument(
        "--task-kind",
        default="digital_ic_workflow",
        choices=list_task_kind_keys(),
        help="Task type profile",
    )
    parser.add_argument("--mode", default="fpga", choices=["fpga"], help="Execution mode")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip external API and emit deterministic placeholder outputs",
    )


def _task_request_from_args(args: argparse.Namespace) -> AgentTaskRequest:
    return AgentTaskRequest.from_task_file(
        task_file=Path(args.task_file),
        output_dir=Path(args.output_dir),
        mode=args.mode,
        dry_run=args.dry_run,
        task_kind=args.task_kind,
        title=args.title,
        origin="cli",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

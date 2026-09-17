"""RQ worker entrypoint."""

from __future__ import annotations

from app.config import settings


def main() -> None:
    try:
        from redis import Redis
        from rq import Queue, Worker
    except ImportError as exc:
        raise RuntimeError("Install redis and rq to run the worker") from exc

    connection = Redis.from_url(settings.redis_url)
    queue = Queue("agent-platform", connection=connection)
    worker = Worker([queue], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()

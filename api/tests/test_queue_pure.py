"""`core/queue.py` best-effort va'dasi — DB'SIZ, Redis'siz o'tadi.

Navbat yiqilishi chaqiruvchini yiqitmasligi kerak: smena yopilishi
bildirishnoma keta olmagani sababli xato bermaydi.
"""

from typing import Any

import pytest

from playbron.core import queue

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    queue._pool = None
    yield
    queue._pool = None


async def test_enqueue_swallows_pool_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def dead_pool(*args: Any, **kwargs: Any) -> Any:
        raise ConnectionError("redis yo'q")

    monkeypatch.setattr(queue, "create_pool", dead_pool)

    # Xato tashqariga chiqmaydi — False qaytadi
    assert await queue.enqueue("notify_shift_variance", 1, 2, {}) is False


async def test_enqueue_delivers_when_pool_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, tuple[Any, ...]]] = []

    class FakePool:
        async def enqueue_job(self, job: str, *args: Any, **kwargs: Any) -> None:
            sent.append((job, args))

    async def alive_pool(*args: Any, **kwargs: Any) -> FakePool:
        return FakePool()

    monkeypatch.setattr(queue, "create_pool", alive_pool)

    assert await queue.enqueue("notify_shift_variance", 7, 8, {"x": 1}) is True
    assert sent == [("notify_shift_variance", (7, 8, {"x": 1}))]

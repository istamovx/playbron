"""Worker registratsiyasi — DB'SIZ, `RUN_DB_TESTS`siz o'tadi.

Yozilgan-lekin-ro'yxatlanmagan vazifa JIMGINA hech qachon yurmaydi —
shu test cron jadval va funksiyalar ro'yxatini muzlatib turadi.
"""

from playbron.worker.main import WorkerSettings


def _cron_names() -> set[str]:
    return {job.coroutine.__name__ for job in WorkerSettings.cron_jobs}


def _function_names() -> set[str]:
    return {fn.__name__ for fn in WorkerSettings.functions}


def test_periodic_tasks_are_registered() -> None:
    assert _cron_names() == {
        "send_pending",
        "expire_unpaid_bookings",
        "booking_reminders",
        "daily_summary",
    }


def test_enqueued_tasks_are_registered() -> None:
    # API navbatga qo'yadiganlar functions ro'yxatida bo'lishi shart
    assert "notify_shift_variance" in _function_names()
    assert "send_pending" in _function_names()


def test_blocked_tasks_are_not_registered() -> None:
    # NotImplementedError tashlaydigan skeletlar ro'yxatda bo'lmasin —
    # aks holda cron har daqiqada xato yog'diradi
    names = _cron_names() | _function_names()
    assert "mark_no_show" not in names
    assert "low_stock_alert" not in names

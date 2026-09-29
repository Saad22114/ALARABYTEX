"""يقارن تشغيلين متتاليين لأمر البيانات ويطبع الفرق شهراً بشهر وفرعاً بفرع."""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test.runner import DiscoverRunner
from django.test.utils import setup_test_environment, teardown_test_environment

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False)
old_config = runner.setup_databases()

log = open("_seed_diff.log", "w", encoding="utf-8")
try:
    from django.core.management import call_command
    from django.db.models import Sum

    from sale_sessions.models import SaleSession
    from sales.models import DailySale

    def snapshot():
        from django.db.models import Count

        sessions = {
            (d, b): n
            for d, b, n in SaleSession.objects.values_list("session_date", "branch_id")
            .annotate(n=Count("id")).values_list("session_date", "branch_id", "n")
        }
        sales = {
            (d, b): n
            for d, b, n in DailySale.objects.values_list("date", "branch_id")
            .annotate(n=Count("id")).values_list("date", "branch_id", "n")
        }
        totals = DailySale.objects.aggregate(t=Sum("total_sales"))["t"]
        return sessions, sales, totals

    call_command("seed_showcase", months=2, verbosity=0, random_seed=20260929)
    a_sessions, a_sales, a_total = snapshot()
    log.write(f"RUN1 sessions={sum(a_sessions.values())} sales={sum(a_sales.values())} total={a_total}\n")

    call_command("seed_showcase", months=2, verbosity=0, random_seed=20260929)
    b_sessions, b_sales, b_total = snapshot()
    log.write(f"RUN2 sessions={sum(b_sessions.values())} sales={sum(b_sales.values())} total={b_total}\n")

    only_a = sorted(set(a_sessions) - set(b_sessions))
    only_b = sorted(set(b_sessions) - set(a_sessions))
    log.write(f"session keys only in run1: {len(only_a)}\n")
    log.write(f"session keys only in run2: {len(only_b)}\n")
    for key in only_a[:10]:
        log.write(f"  A {key} {a_sessions[key]}\n")
    for key in only_b[:10]:
        log.write(f"  B {key} {b_sessions[key]}\n")
    diff = {k: (a_sessions[k], b_sessions[k]) for k in set(a_sessions) & set(b_sessions) if a_sessions[k] != b_sessions[k]}
    log.write(f"session count differs on {len(diff)} shared keys\n")
    for key, pair in list(sorted(diff.items()))[:10]:
        log.write(f"  {key}: {pair}\n")

    sa = sorted(set(a_sales) - set(b_sales))
    sb = sorted(set(b_sales) - set(a_sales))
    log.write(f"sale keys only in run1: {len(sa)} {sa[:5]}\n")
    log.write(f"sale keys only in run2: {len(sb)} {sb[:5]}\n")
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
    log.close()

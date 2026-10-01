# -*- coding: utf-8 -*-
"""throwaway probe: print the trailing month's profit-loss breakdown."""

from django.test import TestCase

from core.tests_seed_showcase import SeedShowcaseBase, add_months, month_start


class Probe(SeedShowcaseBase):
    months = 3

    def test_probe(self):
        for offset in (0, 1, 2):
            first = add_months(month_start(self.ran_at), -offset)
            last = add_months(first, 1).replace(day=1)
            last = last.fromordinal(last.toordinal() - 1)
            res = self.c.get(
                "/api/reports/profit-loss/",
                {"date_from": first.isoformat(), "date_to": last.isoformat()},
            )
            t = res.data["totals"]
            print(
                "PROBE %s sales=%s cogs=%s gross=%s expenses=%s salaries=%s net=%s"
                % (
                    first.isoformat()[:7],
                    t["total_sales"],
                    t["cogs"],
                    t["gross_profit"],
                    t["expenses"],
                    t["salaries"],
                    t["net_profit"],
                )
            )
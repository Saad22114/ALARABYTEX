"""A test run must not spend a real backup slot.

`AutoBackupMiddleware` fired on every request, and the directory it writes to
keeps only twenty files. Running the test suite therefore serialised the whole
throwaway database into ``MEDIA_ROOT/backups`` and pushed the oldest real
backup off the end -- a run of the tests could delete the shop's last copy of
yesterday's books.

Both directions are pinned here. The interesting one is the first: a guard
that stops everything is not a fix, it is an outage with a good comment, so a
test proves the backup still happens when the database is a real one.
"""

from unittest import mock

from django.db import connections
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from core import middleware


def _name_of(database):
    return str(connections["default"].settings_dict.get("NAME") or "")


class AutoBackupMiddlewareTest(TestCase):
    def setUp(self):
        factory = RequestFactory()
        self.request = factory.get("/api/dashboard/")
        self.middleware = middleware.AutoBackupMiddleware(
            lambda request: HttpResponse("ok")
        )
        # The throttle is a module global kept between calls, so a test run
        # would otherwise be decided by whichever test happened to run first.
        self._previous_check = middleware._last_auto_backup_check
        middleware._last_auto_backup_check = 0.0

    def tearDown(self):
        middleware._last_auto_backup_check = self._previous_check

    def _call_with_database_named(self, name):
        """Call the middleware while the connection claims to point at `name`."""
        with mock.patch.dict(connections["default"].settings_dict, {"NAME": name}):
            with mock.patch("appsettings.backup.run_auto_backup_if_due") as run:
                response = self.middleware(self.request)
        return response, run

    # --- the bug -----------------------------------------------------------
    def test_it_writes_nothing_when_the_database_is_a_test_database(self):
        _response, run = self._call_with_database_named("test_fabric_arabi")
        run.assert_not_called()

    def test_it_recognises_the_parallel_test_databases_too(self):
        # `--parallel 4` clones the database as test_fabric_arabi_1 .. _4.
        _response, run = self._call_with_database_named("test_fabric_arabi_3")
        run.assert_not_called()

    def test_the_database_this_suite_runs_against_is_really_a_test_database(self):
        # Otherwise the two tests above are asserting nothing at all: they
        # would pass on a machine where the guard never fires for any reason.
        self.assertTrue(_name_of("default").startswith("test_"))

    # --- the half that must keep working ------------------------------------
    def test_it_still_backs_up_a_real_database(self):
        response, run = self._call_with_database_named("fabric_arabi")
        self.assertEqual(response.status_code, 200)
        run.assert_called_once()

    def test_a_backup_failure_does_not_reach_the_caller(self):
        factory = RequestFactory()
        request = factory.get("/api/dashboard/")
        with mock.patch.dict(connections["default"].settings_dict,
                             {"NAME": "fabric_arabi"}):
            with mock.patch("appsettings.backup.run_auto_backup_if_due",
                            side_effect=RuntimeError("no disk")):
                response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    # --- the throttle is still a throttle -----------------------------------
    def test_repeated_requests_do_not_back_up_more_than_once_a_minute(self):
        with mock.patch.dict(connections["default"].settings_dict,
                             {"NAME": "fabric_arabi"}):
            with mock.patch("appsettings.backup.run_auto_backup_if_due") as run:
                for _ in range(5):
                    self.middleware(self.request)
        run.assert_called_once()
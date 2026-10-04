"""Closes sale sessions that were left open past the configured close time.

The auto-close sweep normally runs when someone reads the sessions list, because
there is no scheduler in this project and a forgotten shift is repaired by the
first person who goes looking for one. That is enough while people use the
system, and not enough at 3am on a day nobody opened it.

Run it from a scheduled task for that case:

    python manage.py close_stale_sessions

It closes only sessions whose own close moment has passed -- the first occurrence
of `session_auto_close_time` after they were opened -- so it is safe to run every
few minutes and never closes a shift early. It writes the sales to the session's
own day, the day it was opened on, and records the reason in the session notes.
"""

from django.core.management.base import BaseCommand

from sale_sessions.services import auto_close_stale_sessions


class Command(BaseCommand):
    help = "Closes sale sessions left open past the configured close time."

    def handle(self, *args, **options):
        closed = auto_close_stale_sessions()
        if closed:
            self.stdout.write(
                self.style.WARNING(
                    "closed %d stale session(s): %s" % (len(closed), ", ".join(map(str, closed)))
                )
            )
        else:
            self.stdout.write("no stale sessions")
"""Check that every employee can still reach the sections their role grants.

There was a complaint that the attendance section "is not in the menu". It was
in SECTIONS and in every role preset, and it was still invisible, for two
reasons that both live in the employee's row rather than in any decision:

    1. `permissions` is a JSON snapshot written when the account was created.
       Every section added to SECTIONS after that moment is simply absent from
       it. The sidebar tests `perms[key].view`, so an absent key reads as
       "no access", and the page itself filters its tabs through the same key
       and comes up empty.

    2. `role` is a free-text column, and rows exist holding `ADMIN` where the
       choices say `admin`. A preset lookup on that string misses, which reads
       as "no permissions at all".

Reads now paper over both (`sale_sessions.sections.effective_permissions`),
which is why the sections reappeared without touching a single row. Papering
over is the wrong thing to leave behind, because the row is still wrong and the
next report starts from the row. So this is the audit:

    python manage.py audit_access
    python manage.py audit_access --apply

It prints one line per employee whose stored row disagrees with their role, and
--apply rewrites just the role field to the value the model defines. It does not
touch the permission map: a map is a set of decisions, and the read path now
interprets an incomplete one correctly without pretending it was complete.

Nothing here is fatal on its own. A missing key that the role grants is
recovered; a role in the wrong case costs the employee nothing after the fix.
The point of the command is that both should be zero rows, and when they are
not, this names which employees to look at instead of leaving the operator to
infer it from a section that failed to appear.
"""
from django.core.management.base import BaseCommand

from sale_sessions.models import Employee
from sale_sessions.sections import SECTIONS, canonical_role, effective_permissions

SECTIONS_BY_KEY = {s["key"]: s for s in SECTIONS}


class Command(BaseCommand):
    help = "Report employees whose stored role or permission map has gone stale."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="rewrite a non-canonical role to the value the model defines")

    def handle(self, *args, **options):
        declared = {s["key"] for s in SECTIONS}
        everyone = Employee.objects.all().only("id", "name", "role", "permissions")

        bad_role = []
        missing = []
        for emp in everyone:
            if canonical_role(emp.role) != (emp.role or "").strip():
                bad_role.append(emp)
            gaps = declared - set(emp.permissions or {})
            if gaps:
                missing.append((emp, sorted(gaps)))

        self.stdout.write(f"employees: {everyone.count()}   sections: {len(declared)}")

        # --- 1. the role the model defines ---------------------------------
        if bad_role:
            self.stdout.write(self.style.ERROR(
                f"\nFAIL  {len(bad_role)} employee(s) hold a role the choices do not define"))
            for emp in bad_role:
                self.stdout.write(
                    f"      {emp.id:>5}  {emp.name}  role={emp.role!r} "
                    f"should be {canonical_role(emp.role)!r}")
            self.stdout.write("      a role the presets cannot read looks like no role at all")
        else:
            self.stdout.write(self.style.SUCCESS("ok    every role is one of the defined choices"))

        # --- 2. sections the role grants but the row never recorded ---------
        if missing:
            self.stdout.write(self.style.WARNING(
                f"\nwarn  {len(missing)} employee(s) lack a section in the stored map"))
            for emp, gaps in missing[:20]:
                gained = [g for g in gaps if effective_permissions(emp.role, emp.permissions)[g]["view"]]
                # The count that matters is what the employee can now reach, not
                # how many keys are blank: a `custom` role is meant to be empty,
                # and listing its gaps as failures would drown the real ones.
                note = f"recovered on read: {', '.join(gained)}" if gained else "not granted by this role"
                self.stdout.write(f"      {emp.id:>5}  {emp.name}  missing {len(gaps)}  ({note})")
            if len(missing) > 20:
                self.stdout.write(f"      ... and {len(missing) - 20} more")
            self.stdout.write("      reads fill these in from the role, so nothing is lost")
        else:
            self.stdout.write(self.style.SUCCESS("ok    every stored map names every section"))

        # --- what each account can actually reach right now ----------------
        silent = []
        for emp in Employee.objects.all().only("id", "name", "role", "permissions"):
            perms = effective_permissions(emp.role, emp.permissions)
            reachable = [k for k in declared if perms[k].get("view")]
            dead = [k for k in reachable
                    if SECTIONS_BY_KEY[k].get("windows")
                    and not perms[k].get("windows")]
            if dead:
                silent.append((emp, reachable, dead))
        if silent:
            self.stdout.write(self.style.ERROR(
                f"\nFAIL  {len(silent)} employee(s) can open a section with no tab in it"))
            for emp, reachable, dead in silent[:20]:
                self.stdout.write(f"      {emp.id:>5}  {emp.name}  sees {', '.join(dead)} "
                                  f"but has no window in it")
            self.stdout.write("      'view' on a windowed section with no window is an empty promise")
        else:
            self.stdout.write(self.style.SUCCESS(
                "ok    every section an employee can view also opens a tab"))

        if options["apply"] and bad_role:
            for emp in bad_role:
                Employee.objects.filter(pk=emp.pk).update(role=canonical_role(emp.role))
            self.stdout.write(self.style.SUCCESS(
                f"\nrewrote {len(bad_role)} role value(s) to their canonical form"))
        elif bad_role:
            self.stdout.write(self.style.WARNING(
                "\nre-run with --apply to rewrite the role values (permission maps untouched)"))

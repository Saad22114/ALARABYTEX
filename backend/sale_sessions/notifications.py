from .models import Employee, Notification


def notify_employee(recipient, kind, title, body="", url=""):
    if recipient is None or not recipient.is_active:
        return None
    return Notification.objects.create(
        recipient=recipient, kind=kind, title=title, body=body, url=url,
    )


def notify_transfer_approvers(transfer, actor=None):
    recipients = Employee.objects.filter(
        is_active=True, role__in=[Employee.Role.ADMIN, Employee.Role.SUPERVISOR],
    ).exclude(pk=getattr(actor, "pk", None))
    transfer_branch_ids = {
        branch_id for branch_id in (
            transfer.from_branch_id,
            transfer.to_branch_id,
            transfer.from_warehouse.branch_id if transfer.from_warehouse_id else None,
            transfer.to_warehouse.branch_id if transfer.to_warehouse_id else None,
        ) if branch_id is not None
    }
    for employee in recipients:
        if not employee.has_permission("warehouses", "create"):
            continue
        if employee.role != Employee.Role.ADMIN:
            employee_branch_ids = set(employee.allowed_branches.values_list("id", flat=True))
            if employee.branch_id:
                employee_branch_ids.add(employee.branch_id)
            if employee_branch_ids and not employee_branch_ids.intersection(transfer_branch_ids):
                continue
            if transfer_branch_ids and not employee_branch_ids:
                continue
        notify_employee(
            employee, "transfer_request", "طلب تحويل بانتظار الموافقة",
            f"التحويل {transfer.number} من {transfer.from_branch.name if transfer.from_branch_id else transfer.from_warehouse.name} إلى {transfer.to_branch.name if transfer.to_branch_id else transfer.to_warehouse.name if transfer.to_warehouse_id else '—'}.",
            "/warehouses/transfers",
        )


def notify_transfer_requester(transfer, kind, title, body):
    # أسماء الموظفين فريدة في النظام؛ هذا يتيح إشعار الطلبات القديمة أيضاً
    # دون تغيير بنية سند التحويل أو فقدان توافق النسخ السابقة.
    recipient = Employee.objects.filter(name=transfer.requested_by, is_active=True).first()
    return notify_employee(recipient, kind, title, body, "/warehouses/transfers")

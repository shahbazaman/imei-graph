from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _


SERIAL_SPLIT_RE = re.compile(r"[\n\r,;|]+")


STOCK_DOCTYPES = {
    "Purchase Invoice": {
        "child_table": "Purchase Invoice Item",
        "party_field": "supplier",
        "party_name_field": "supplier_name",
        "serial_fields": ("serial_no", "rejected_serial_no"),
    },
    "Sales Invoice": {
        "child_table": "Sales Invoice Item",
        "party_field": "customer",
        "party_name_field": "customer_name",
        "serial_fields": ("serial_no",),
    },
    "Delivery Note": {
        "child_table": "Delivery Note Item",
        "party_field": "customer",
        "party_name_field": "customer_name",
        "serial_fields": ("serial_no",),
    },
    "Purchase Receipt": {
        "child_table": "Purchase Receipt Item",
        "party_field": "supplier",
        "party_name_field": "supplier_name",
        "serial_fields": ("serial_no", "rejected_serial_no"),
    },
    "Stock Entry": {
        "child_table": "Stock Entry Detail",
        "party_field": "supplier",
        "party_name_field": "supplier_name",
        "serial_fields": ("serial_no",),
    },
}

DOCTYPE_PREFIX_HINTS = (
    ("ACC-SINV", "Sales Invoice"),
    ("SINV", "Sales Invoice"),
    ("ACC-PINV", "Purchase Invoice"),
    ("PINV", "Purchase Invoice"),
    ("MAT-DN", "Delivery Note"),
    ("DN", "Delivery Note"),
    ("MAT-PRE", "Purchase Receipt"),
    ("PREC", "Purchase Receipt"),
    ("MAT-STE", "Stock Entry"),
    ("STE", "Stock Entry"),
)


@dataclass(frozen=True)
class TransactionMeta:
    doctype: str
    name: str
    posting_date: Any
    posting_time: Any
    creation: Any
    company: str | None = None
    party: str | None = None
    party_name: str | None = None
    is_return: int = 0
    return_against: str | None = None


def _parse_serials(value: str | None) -> list[str]:
    if not value:
        return []

    serials = []
    seen = set()
    for serial in SERIAL_SPLIT_RE.split(str(value)):
        serial = serial.strip()
        if serial and serial not in seen:
            seen.add(serial)
            serials.append(serial)
    return serials


def _transaction_datetime_sql(alias: str = "p") -> str:
    return f"timestamp(coalesce({alias}.posting_date, date({alias}.creation)), coalesce({alias}.posting_time, time({alias}.creation)))"


def _get_transaction_meta(doctype: str, name: str) -> TransactionMeta:
    if doctype not in STOCK_DOCTYPES:
        frappe.throw(_("Unsupported transaction type: {0}").format(doctype))

    config = STOCK_DOCTYPES[doctype]
    fields = [
        "name",
        "posting_date",
        "posting_time",
        "creation",
        "company",
        "is_return",
        "return_against",
        config["party_field"],
        config["party_name_field"],
    ]
    doc = frappe.db.get_value(doctype, name, fields, as_dict=True)
    if not doc:
        frappe.throw(_("{0} {1} was not found").format(doctype, name))

    return TransactionMeta(
        doctype=doctype,
        name=name,
        posting_date=doc.posting_date,
        posting_time=doc.posting_time,
        creation=doc.creation,
        company=doc.company,
        party=doc.get(config["party_field"]),
        party_name=doc.get(config["party_name_field"]),
        is_return=doc.is_return or 0,
        return_against=doc.return_against,
    )


def _infer_transaction_doctype(name: str, preferred_doctype: str | None = None) -> str:
    if preferred_doctype:
        preferred_doctype = preferred_doctype.strip()
        if preferred_doctype in STOCK_DOCTYPES and frappe.db.exists(preferred_doctype, name):
            return preferred_doctype

    upper_name = name.upper()
    hinted_doctypes = [
        doctype
        for prefix, doctype in DOCTYPE_PREFIX_HINTS
        if upper_name.startswith(prefix)
    ]

    for doctype in hinted_doctypes:
        if frappe.db.exists(doctype, name):
            return doctype

    for doctype in STOCK_DOCTYPES:
        if doctype not in hinted_doctypes and frappe.db.exists(doctype, name):
            return doctype

    frappe.throw(
        _("Could not find {0} in Sales Invoice, Purchase Invoice, Delivery Note, Purchase Receipt, or Stock Entry").format(
            name
        )
    )


def _get_transaction_items(meta: TransactionMeta) -> list[dict[str, Any]]:
    config = STOCK_DOCTYPES[meta.doctype]
    child_table = config["child_table"]
    serial_select = ", ".join(f"`{field}`" for field in config["serial_fields"])

    rows = frappe.db.sql(
        f"""
        select
            name,
            idx,
            item_code,
            item_name,
            qty,
            {serial_select}
        from `tab{child_table}`
        where parent = %s
        order by idx asc, name asc
        """,
        (meta.name,),
        as_dict=True,
    )

    items = []
    for row in rows:
        for field in config["serial_fields"]:
            for serial in _parse_serials(row.get(field)):
                items.append(
                    {
                        "detail_name": row.name,
                        "idx": row.idx,
                        "item_code": row.item_code,
                        "item_name": row.item_name,
                        "qty": row.qty,
                        "serial_no": serial,
                        "serial_field": field,
                    }
                )
    return items


def _get_transaction_datetime(meta: TransactionMeta) -> Any:
    return frappe.db.sql(
        f"""
        select {_transaction_datetime_sql()} as posting_datetime
        from `tab{meta.doctype}` p
        where p.name = %s
        """,
        (meta.name,),
        as_dict=True,
    )[0].posting_datetime


def _find_next_from_item_tables(serial_no: str, current: TransactionMeta) -> dict[str, Any] | None:
    current_dt = frappe.db.sql(
        f"""
        select {_transaction_datetime_sql()} as posting_datetime
        from `tab{current.doctype}` p
        where p.name = %s
        """,
        (current.name,),
        as_dict=True,
    )[0].posting_datetime

    candidates = []
    for doctype, config in STOCK_DOCTYPES.items():
        child_table = config["child_table"]
        for serial_field in config["serial_fields"]:
            rows = frappe.db.sql(
                f"""
                select
                    c.name,
                    c.name as voucher_detail_no,
                    %s as voucher_type,
                    p.name as voucher_no,
                    c.item_code,
                    c.item_name,
                    c.qty,
                    c.`{serial_field}` as serial_no,
                    %s as serial_field,
                    p.posting_date,
                    p.posting_time,
                    {_transaction_datetime_sql()} as posting_datetime,
                    p.creation
                from `tab{child_table}` c
                inner join `tab{doctype}` p on p.name = c.parent
                where
                    p.docstatus < 2
                    and p.name != %s
                    and c.`{serial_field}` like %s
                    and (
                        {_transaction_datetime_sql()} > %s
                        or (
                            {_transaction_datetime_sql()} = %s
                            and coalesce(p.creation, '1000-01-01') > coalesce(%s, '1000-01-01')
                        )
                    )
                order by posting_datetime asc, p.creation asc, c.idx asc, c.name asc
                limit 80
                """,
                (
                    doctype,
                    serial_field,
                    current.name,
                    f"%{serial_no}%",
                    current_dt,
                    current_dt,
                    current.creation,
                ),
                as_dict=True,
            )
            for row in rows:
                if serial_no in _parse_serials(row.serial_no):
                    candidates.append(row)

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: (
            row.posting_datetime,
            row.creation,
            row.voucher_type,
            row.voucher_no,
            row.voucher_detail_no,
        )
    )
    return candidates[0]


def _find_next_from_stock_ledger(serial_no: str, current: TransactionMeta) -> dict[str, Any] | None:
    current_dt = _get_transaction_datetime(current)

    rows = frappe.db.sql(
        """
        select
            sle.name,
            sle.voucher_type,
            sle.voucher_no,
            sle.voucher_detail_no,
            sle.item_code,
            null as item_name,
            sle.actual_qty as qty,
            sle.serial_no,
            'stock_ledger' as serial_field,
            sle.posting_date,
            sle.posting_time,
            sle.posting_datetime,
            sle.creation
        from `tabStock Ledger Entry` sle
        where
            sle.docstatus < 2
            and sle.is_cancelled = 0
            and sle.serial_no like %s
            and sle.voucher_no != %s
            and sle.voucher_type in (
                'Purchase Invoice', 'Sales Invoice', 'Delivery Note',
                'Purchase Receipt', 'Stock Entry'
            )
            and sle.posting_datetime > %s
        order by sle.posting_datetime asc, sle.creation asc, sle.name asc
        limit 80
        """,
        (f"%{serial_no}%", current.name, current_dt),
        as_dict=True,
    )

    for row in rows:
        if serial_no in _parse_serials(row.serial_no):
            return row
    return None


def _find_immediate_next_transaction(serial_no: str, current: TransactionMeta) -> dict[str, Any] | None:
    return _find_next_from_item_tables(serial_no, current) or _find_next_from_stock_ledger(serial_no, current)


def _accounting_links(doctype: str, name: str) -> list[dict[str, str]]:
    links = []

    payment_entries = frappe.db.sql(
        """
        select parent
        from `tabPayment Entry Reference`
        where reference_doctype = %s and reference_name = %s
        order by creation asc
        """,
        (doctype, name),
        as_dict=True,
    )
    for row in payment_entries:
        links.append({"doctype": "Payment Entry", "name": row.parent, "relation": "payment"})

    gl_entries = frappe.db.sql(
        """
        select name
        from `tabGL Entry`
        where voucher_type = %s and voucher_no = %s and is_cancelled = 0
        order by posting_date asc, creation asc
        limit 20
        """,
        (doctype, name),
        as_dict=True,
    )
    if gl_entries:
        links.append({"doctype": "GL Entry", "name": f"{len(gl_entries)} rows", "relation": "ledger"})

    journal_entries = frappe.db.sql(
        """
        select parent
        from `tabJournal Entry Account`
        where reference_type = %s and reference_name = %s
        order by creation asc
        """,
        (doctype, name),
        as_dict=True,
    )
    for row in journal_entries:
        links.append({"doctype": "Journal Entry", "name": row.parent, "relation": "reference"})

    return links


def _transaction_node_id(doctype: str, name: str) -> str:
    return f"txn::{doctype}::{name}"


def _serial_node_id(parent_doctype: str, parent_name: str, serial_no: str) -> str:
    return f"serial::{parent_doctype}::{parent_name}::{serial_no}"


def _add_transaction_node(nodes: dict[str, dict[str, Any]], meta: TransactionMeta, level: int, root: bool = False) -> str:
    node_id = _transaction_node_id(meta.doctype, meta.name)
    if node_id in nodes:
        return node_id

    accounting = _accounting_links(meta.doctype, meta.name)
    accounting_text = "\n".join(f"{row['relation']}: {row['doctype']} {row['name']}" for row in accounting)
    title = "\n".join(
        filter(
            None,
            [
                f"{meta.doctype}: {meta.name}",
                f"Company: {meta.company or ''}",
                f"Party: {meta.party_name or meta.party or ''}",
                f"Date: {meta.posting_date or ''} {meta.posting_time or ''}",
                f"Return against: {meta.return_against}" if meta.return_against else None,
                accounting_text,
            ],
        )
    )

    nodes[node_id] = {
        "id": node_id,
        "label": f"{'ROOT' if root else 'DISPUTED'}\n{meta.doctype}\n{meta.name}",
        "level": level,
        "shape": "box",
        "color": {
            "background": "#dc2626" if root else "#f97316",
            "border": "#7f1d1d" if root else "#9a3412",
        },
        "font": {"color": "white", "size": 12},
        "title": title,
    }
    return node_id


def _add_serial_node(nodes: dict[str, dict[str, Any]], meta: TransactionMeta, item: dict[str, Any], level: int) -> str:
    node_id = _serial_node_id(meta.doctype, meta.name, item["serial_no"])
    if node_id not in nodes:
        nodes[node_id] = {
            "id": node_id,
            "label": f"{item['serial_no']}\n{item.get('item_code') or ''}",
            "level": level,
            "shape": "ellipse",
            "color": {"background": "#0ea5e9", "border": "#075985"},
            "font": {"color": "white", "size": 12},
            "title": "\n".join(
                [
                    f"Serial: {item['serial_no']}",
                    f"Item: {item.get('item_code') or ''}",
                    f"Item row: {item.get('detail_name') or ''}",
                    f"Source field: {item.get('serial_field') or ''}",
                ]
            ),
        }
    return node_id


@frappe.whitelist()
def get_dispute_graph(start_name: str, max_depth: int = 8, start_doctype: str | None = None) -> dict[str, Any]:
    max_depth = max(1, min(int(max_depth or 8), 20))
    start_name = (start_name or "").strip()
    start_doctype = _infer_transaction_doctype(start_name, start_doctype)

    if not start_name:
        frappe.throw(_("Invoice or transaction number is required"))

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    visited_transactions: set[tuple[str, str]] = set()
    expanded_serials: set[tuple[str, str, str]] = set()

    root_meta = _get_transaction_meta(start_doctype, start_name)
    queue = deque([(root_meta, 0, True)])

    while queue:
        meta, depth, is_root = queue.popleft()
        txn_key = (meta.doctype, meta.name)
        if depth > max_depth or txn_key in visited_transactions:
            continue

        visited_transactions.add(txn_key)
        txn_node = _add_transaction_node(nodes, meta, depth * 2, root=is_root)

        for item in _get_transaction_items(meta):
            serial_key = (meta.doctype, meta.name, item["serial_no"])
            if serial_key in expanded_serials:
                continue
            expanded_serials.add(serial_key)

            serial_node = _add_serial_node(nodes, meta, item, depth * 2 + 1)
            edges.append(
                {
                    "from": txn_node,
                    "to": serial_node,
                    "label": "item",
                    "arrows": "to",
                    "color": {"color": "#38bdf8"},
                }
            )

            next_row = _find_immediate_next_transaction(item["serial_no"], meta)
            if not next_row:
                continue

            next_key = (next_row.voucher_type, next_row.voucher_no)
            next_node_id = _transaction_node_id(next_row.voucher_type, next_row.voucher_no)
            edges.append(
                {
                    "from": serial_node,
                    "to": next_node_id,
                    "label": "next movement",
                    "arrows": "to",
                    "color": {"color": "#f97316"},
                    "title": "\n".join(
                        [
                            f"Source row: {next_row.name}",
                            f"Item: {next_row.item_code or ''}",
                            f"Qty: {next_row.qty or ''}",
                            f"Serial field: {next_row.serial_field or ''}",
                            f"Date: {next_row.posting_date or ''} {next_row.posting_time or ''}",
                        ]
                    ),
                }
            )

            if next_key not in visited_transactions and depth + 1 <= max_depth:
                queue.append((_get_transaction_meta(next_row.voucher_type, next_row.voucher_no), depth + 1, False))

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "root": {"doctype": start_doctype, "name": start_name},
        "depth": max_depth,
    }

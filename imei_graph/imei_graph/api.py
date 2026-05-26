import frappe
from sqlalchemy import text
from app.erp_connector import ERP_Session


@frappe.whitelist()
def get_imei_graph(imei):

    db = ERP_Session()

    target_serial = str(imei).strip()

    voucher_query = text("""

        SELECT DISTINCT parent

        FROM `tabPurchase Invoice Item`

        WHERE serial_no IS NOT NULL

        ORDER BY creation DESC

        LIMIT 3000

    """)

    vouchers = db.execute(
        voucher_query
    ).fetchall()

    nodes = []
    edges = []

    added_vouchers = set()
    added_invoices = set()

    found = False

    for voucher_row in vouchers:

        voucher_name = str(
            voucher_row.parent
        )

        invoice_query = text("""

            SELECT
                parent,
                serial_no,
                item_code

            FROM `tabPurchase Invoice Item`

            WHERE parent = :voucher_name

        """)

        rows = db.execute(

            invoice_query,

            {
                "voucher_name": voucher_name
            }

        ).fetchall()

        invoice_devices = {}

        for row in rows:

            invoice_name = str(row.parent)

            if invoice_name not in invoice_devices:
                invoice_devices[invoice_name] = []

            raw = str(row.serial_no or "")

            serials = []

            for sep in ["\n", ",", ";", "\r"]:
                raw = raw.replace(sep, "|")

            for s in raw.split("|"):

                s = s.strip()

                if s:
                    serials.append(s)

            serials.reverse()

            for serial in serials:

                invoice_devices[
                    invoice_name
                ].append({

                    "device": serial,

                    "item_code": str(
                        row.item_code
                    )
                })

        invoice_names = list(
            invoice_devices.keys()
        )

        invoice_names.reverse()

        for invoice_name in invoice_names:

            invoice_id = f"I_{invoice_name}"

            if invoice_id not in added_invoices:

                nodes.append({

                    "id": invoice_id,

                    "label": f"Invoice\\n{invoice_name}",

                    "shape": "ellipse",

                    "color": "#f59e0b"

                })

                added_invoices.add(
                    invoice_id
                )

            voucher_id = f"V_{voucher_name}"

            if voucher_id not in added_vouchers:

                nodes.append({

                    "id": voucher_id,

                    "label": f"Voucher\\n{voucher_name}",

                    "shape": "box",

                    "color": "#16a34a"

                })

                edges.append({

                    "from": voucher_id,

                    "to": invoice_id

                })

                added_vouchers.add(
                    voucher_id
                )

            devices = invoice_devices[
                invoice_name
            ]

            for idx, d in enumerate(devices):

                serial = d["device"]

                matched = (
                    serial.strip()
                    ==
                    target_serial
                )

                device_id = (
                    f"D_{voucher_name}_{invoice_name}_{idx}"
                )

                if matched:

                    found = True

                    nodes.append({

                        "id": device_id,

                        "label": (
                            f"TARGET DEVICE\\n"
                            f"{serial}"
                        ),

                        "shape": "star",

                        "size": 35,

                        "color": "#ff0000"

                    })

                else:

                    nodes.append({

                        "id": device_id,

                        "label": serial,

                        "shape": "dot",

                        "size": 15,

                        "color": "#334155"

                    })

                edges.append({

                    "from": invoice_id,

                    "to": device_id

                })

                if matched:
                    break

            if found:
                break

        if found:
            break

    return {

        "nodes": nodes,

        "edges": edges,

        "found": found
    }
import frappe


@frappe.whitelist()
def get_imei_graph(imei):

    result = []

    vouchers = frappe.db.sql("""

        SELECT DISTINCT parent

        FROM `tabPurchase Invoice Item`

        WHERE serial_no IS NOT NULL

        ORDER BY creation DESC

        LIMIT 100

    """, as_dict=True)

    step = 1

    for voucher_row in vouchers:

        voucher = voucher_row.parent

        items = frappe.db.sql("""

            SELECT
                parent,
                serial_no,
                item_code

            FROM `tabPurchase Invoice Item`

            WHERE parent = %s

        """, (voucher,), as_dict=True)

        invoice_devices = []

        found = False

        for row in items:

            if not row.serial_no:
                continue

            serials = str(row.serial_no).replace(
                "\n",
                ","
            ).split(",")

            for serial in serials:

                serial = serial.strip()

                if not serial:
                    continue

                invoice_devices.append({

                    "step": step,
                    "voucher": voucher,
                    "invoice": row.parent,
                    "device": serial,
                    "item_code": row.item_code,
                    "matched": serial == imei

                })

                if serial == imei:
                    found = True

                step += 1

        if found:
            result = invoice_devices
            break

    return result
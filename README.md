# IMEI Dispute Graph

Frappe app code for tracing disputed mobile-store transactions by serial number / IMEI.

The graph starts from a disputed stock transaction, expands its serial-number items, finds the immediate next stock movement for each serial number, marks that transaction as dependent-disputed, and repeats until no later movement is found or the configured depth is reached.

## Suggested install

```bash
cd /mnt/c/Users/USER/Downloads/frappe-bench
source env/bin/activate
bench --site local.test install-app imei_graph
bench --site local.test migrate
bench restart
```

Open Desk page: **IMEI Dispute Graph**.


# Odoo 19 ArcGIS Connector

One-way synchronization from Odoo Project tasks to an ArcGIS hosted Feature Layer.

## Included
- Reads `project.task` records linked to a customer/contact.
- Uses the linked partner's `partner_latitude` and `partner_longitude` as point geometry.
- Sends task ID, task name, project, stage, customer and deadline.
- Finds existing ArcGIS features by `ODOO_TASK_ID`, then adds or updates.
- Uses HTTPS only; ArcGIS tokens are sent in POST bodies over TLS.
- Handles ArcGIS query transfer-limit pagination and validates every add/update result.
- Incremental sync based on task and linked partner `write_date`; the checkpoint advances only after a complete edit run.
- Test Connection, Dry Run and Synchronize Now actions.
- Synchronization logs and an hourly scheduled job; automatic synchronization is disabled by default.

## Required ArcGIS layer fields
Create a Point Feature Layer with:
- `ODOO_TASK_ID` - integer/long (preferably unique)
- `TASK_NAME` - string
- `PROJECT` - string
- `STAGE` - string
- `CUSTOMER` - string
- `DEADLINE` - date

The layer must allow query and applyEdits. Use WKID 4326 or a compatible coordinate system. The URL should end in `/FeatureServer/<layer-index>`. The ArcGIS credential needs permission to query and edit the layer.

## Install on Odoo.sh
1. Push this repository branch to the GitHub repository connected to Odoo.sh.
2. Wait for the Odoo.sh build to finish.
3. Open the development database, enable Developer Mode, update the Apps List, and install **Odoo ArcGIS Connector**.
4. Open **ArcGIS Integration -> Connections** and create a connector.
5. Enter the HTTPS Feature Layer URL and token/API key; save.
6. Click **Test Connection**, then **Dry Run** and inspect Synchronization Logs.
7. Click **Synchronize Now** only after confirming the preview.
8. Enable automatic synchronization only after testing; the scheduled job checks hourly.
9. Test in staging before merging to the production branch.

## Incremental synchronization notes
The first run scans all eligible tasks. Later runs select tasks changed since the last complete run, including changes to the linked partner (where coordinates are stored). If any ArcGIS edits fail or the request fails, the checkpoint is not advanced; successful edits are safe to retry because records are matched by `ODOO_TASK_ID`.

For high-volume deployments, configure `ODOO_TASK_ID` as a unique field/index in ArcGIS and monitor synchronization logs. The connector deliberately remains one-way: it does not import ArcGIS geometries into Odoo.

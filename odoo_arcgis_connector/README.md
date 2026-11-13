# Odoo 19 ArcGIS Connector

First release: one-way synchronization from Odoo Project tasks to an ArcGIS hosted Feature Layer.

## Included
- Reads `project.task` records linked to a customer/contact.
- Uses the linked partner's `partner_latitude` and `partner_longitude` as point geometry.
- Sends task ID, task name, project, stage, customer and deadline.
- Finds existing ArcGIS features by `ODOO_TASK_ID`, then adds or updates.
- Test Connection, Dry Run and Synchronize Now actions.
- Synchronization logs and an hourly scheduled job.
- Automatic synchronization is disabled by default on the connector record.

## Required ArcGIS layer fields
Create a Point Feature Layer with:
- `ODOO_TASK_ID` - integer/long
- `TASK_NAME` - string
- `PROJECT` - string
- `STAGE` - string
- `CUSTOMER` - string
- `DEADLINE` - date

The layer must allow query and applyEdits. Use WKID 4326 or a compatible coordinate system. The URL should end in `/FeatureServer/<layer-index>`. The ArcGIS credential needs permission to query and edit the layer.

## Odoo.sh installation
1. Extract this folder into the connected GitHub repository for your Odoo.sh project, e.g. `custom/odoo_arcgis_connector/` or `odoo_arcgis_connector/`.
2. Commit and push to a development branch.
3. Wait for the Odoo.sh build to finish.
4. Open that branch's database, enable Developer Mode, open Apps, update the Apps List, search `Odoo ArcGIS Connector`, and install.
5. Open **ArcGIS Integration -> Connections** and create a connector.
6. Enter the ArcGIS Feature Layer URL and token/API key; save.
7. Click **Test Connection**, then **Dry Run** and inspect Synchronization Logs.
8. Click **Synchronize Now** only after confirming the preview.
9. Enable **Enable automatic synchronization** only after testing; the scheduled job checks every hour.
10. Test in staging before merging the code to the production branch and installing/updating it in production.

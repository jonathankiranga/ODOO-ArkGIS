import json
import logging
from datetime import datetime, time, timezone

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
HTTP_TIMEOUT = 60
BATCH_SIZE = 200
QUERY_BATCH_SIZE = 500


class ArcGISConnector(models.Model):
    _name = "arcgis.connector"
    _description = "ArcGIS Connector"
    _rec_name = "name"

    name = fields.Char(required=True, default="ArcGIS")
    active = fields.Boolean(default=True)
    layer_url = fields.Char(
        string="ArcGIS Feature Layer URL",
        required=True,
        help="FeatureServer layer URL ending in /FeatureServer/0 (or another layer number).",
    )
    arcgis_token = fields.Char(
        string="ArcGIS Token / API Key",
        groups="base.group_system",
        help="Keep this credential private. Only system administrators can access it.",
    )
    auto_sync_enabled = fields.Boolean(
        string="Enable automatic synchronization",
        default=False,
        help="The scheduled job synchronizes enabled connectors hourly.",
    )
    last_sync_date = fields.Datetime(readonly=True)
    last_sync_message = fields.Text(readonly=True)
    log_ids = fields.One2many("arcgis.sync.log", "connector_id", string="Synchronization Logs")

    _sql_constraints = [
        ("arcgis_connector_unique_name", "unique(name)", "Use a unique connector name.")
    ]

    @api.constrains("layer_url")
    def _check_layer_url(self):
        for rec in self:
            if rec.layer_url and not rec.layer_url.startswith(("https://", "http://")):
                raise ValidationError(_("The ArcGIS layer URL must start with http:// or https://."))

    def _config(self):
        self.ensure_one()
        if not self.layer_url or not self.arcgis_token:
            raise UserError(_("Enter the ArcGIS Feature Layer URL and token/API key first."))
        return self.layer_url.rstrip("/"), self.arcgis_token

    def _arcgis_post(self, path, data):
        layer_url, token = self._config()
        payload = dict(data, f="json", token=token)
        try:
            response = requests.post(
                "%s/%s" % (layer_url, path.lstrip("/")),
                data=payload,
                timeout=HTTP_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            raise UserError(_("Could not contact ArcGIS: %s") % exc) from exc
        except ValueError as exc:
            raise UserError(_("ArcGIS returned invalid JSON.")) from exc
        if result.get("error"):
            raise UserError(_("ArcGIS error: %s") % json.dumps(result["error"], ensure_ascii=False))
        return result

    def action_test_connection(self):
        self.ensure_one()
        result = self._arcgis_post("query", {
            "where": "1=1", "returnCountOnly": "true",
        })
        count = result.get("count", "unknown")
        message = _("Connection successful. The layer contains %s feature(s).") % count
        self.env["arcgis.sync.log"].create({
            "connector_id": self.id, "operation": "test",
            "state": "success", "message": message,
        })
        return self._notify(message, "success")

    @staticmethod
    def _m2o_name(record):
        return record.display_name if record else ""

    @staticmethod
    def _date_to_epoch_ms(value):
        if not value:
            return None
        # Standard project.task.date_deadline is a date, not a datetime.
        dt = datetime.combine(value, time.min).replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    def _task_feature(self, task):
        partner = task.partner_id
        if not partner:
            return None
        lat, lon = partner.partner_latitude, partner.partner_longitude
        # Odoo commonly uses (0, 0) for an unset geolocation.
        if lat is None or lon is None or (lat == 0 and lon == 0):
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return {
            "geometry": {
                "x": lon, "y": lat,
                "spatialReference": {"wkid": 4326},
            },
            "attributes": {
                "ODOO_TASK_ID": task.id,
                "TASK_NAME": task.name or "",
                "PROJECT": self._m2o_name(task.project_id),
                "STAGE": self._m2o_name(task.stage_id),
                "CUSTOMER": partner.display_name or "",
                "DEADLINE": self._date_to_epoch_ms(task.date_deadline),
            },
        }

    def _collect_features(self):
        Task = self.env["project.task"].sudo()
        offset = 0
        tasks_read = skipped = 0
        features = []
        while True:
            tasks = Task.search(
                [("partner_id", "!=", False)],
                offset=offset, limit=BATCH_SIZE, order="id",
            )
            if not tasks:
                break
            tasks_read += len(tasks)
            for task in tasks:
                feature = self._task_feature(task)
                if feature:
                    features.append(feature)
                else:
                    skipped += 1
            offset += len(tasks)
            if len(tasks) < BATCH_SIZE:
                break
        return tasks_read, features, skipped

    def _existing_objectids(self, task_ids):
        existing = {}
        for start in range(0, len(task_ids), QUERY_BATCH_SIZE):
            ids = task_ids[start:start + QUERY_BATCH_SIZE]
            where = "ODOO_TASK_ID IN (%s)" % ",".join(str(int(x)) for x in ids)
            result = self._arcgis_post("query", {
                "where": where,
                "outFields": "OBJECTID,ODOO_TASK_ID",
                "returnGeometry": "false",
            })
            for feature in result.get("features", []):
                attrs = feature.get("attributes", {})
                if attrs.get("ODOO_TASK_ID") is not None and attrs.get("OBJECTID") is not None:
                    existing[int(attrs["ODOO_TASK_ID"])] = attrs["OBJECTID"]
        return existing

    def _apply_edits(self, adds, updates):
        added = updated = failed = 0
        for start in range(0, max(len(adds), len(updates)), BATCH_SIZE):
            add_batch = adds[start:start + BATCH_SIZE]
            update_batch = updates[start:start + BATCH_SIZE]
            response = self._arcgis_post("applyEdits", {
                "adds": json.dumps(add_batch),
                "updates": json.dumps(update_batch),
                "rollbackOnFailure": "true",
            })
            for key, kind in (("addResults", "add"), ("updateResults", "update")):
                for item in response.get(key, []):
                    if item.get("success"):
                        if kind == "add":
                            added += 1
                        else:
                            updated += 1
                    else:
                        failed += 1
                        _logger.error("ArcGIS %s failed: %s", kind, item.get("error"))
        return added, updated, failed

    def action_preview_sync(self):
        self.ensure_one()
        count, features, skipped = self._collect_features()
        message = _(
            "DRY RUN — no ArcGIS data was changed. Tasks read: %(count)s; "
            "features ready: %(ready)s; skipped: %(skipped)s."
        ) % {"count": count, "ready": len(features), "skipped": skipped}
        if features:
            message += "\nFirst feature preview:\n%s" % json.dumps(features[0], indent=2)
        self.env["arcgis.sync.log"].create({
            "connector_id": self.id, "operation": "preview",
            "state": "success" if features else "warning",
            "message": message, "tasks_read": count,
            "features_ready": len(features), "skipped": skipped,
        })
        return self._notify(
            _("Prepared %s feature(s). See Synchronization Logs for details.") % len(features),
            "success" if features else "warning",
        )

    def action_sync_now(self):
        self.ensure_one()
        count, features, skipped = self._collect_features()
        if not features:
            message = _("No eligible task features. Tasks read: %s; skipped: %s.") % (count, skipped)
            self._write_log(message, "warning", count, 0, skipped=skipped)
            return self._notify(message, "warning")

        known = self._existing_objectids([f["attributes"]["ODOO_TASK_ID"] for f in features])
        adds, updates = [], []
        for feature in features:
            task_id = feature["attributes"]["ODOO_TASK_ID"]
            object_id = known.get(task_id)
            if object_id is None:
                adds.append(feature)
            else:
                feature["attributes"]["OBJECTID"] = object_id
                updates.append(feature)

        added, updated, failed = self._apply_edits(adds, updates)
        state = "error" if failed and not (added or updated) else (
            "warning" if failed or skipped else "success"
        )
        message = _(
            "Synchronization finished. Tasks read: %(count)s; prepared: %(ready)s; "
            "added: %(added)s; updated: %(updated)s; skipped: %(skipped)s; failed: %(failed)s."
        ) % {
            "count": count, "ready": len(features), "added": added,
            "updated": updated, "skipped": skipped, "failed": failed,
        }
        self._write_log(
            message, state, count, len(features),
            added=added, updated=updated, skipped=skipped, failed=failed,
        )
        return self._notify(message, "danger" if state == "error" else state)

    def _write_log(self, message, state, count, ready, added=0, updated=0, skipped=0, failed=0):
        self.env["arcgis.sync.log"].create({
            "connector_id": self.id, "operation": "sync", "state": state,
            "message": message, "tasks_read": count, "features_ready": ready,
            "added": added, "updated": updated, "skipped": skipped, "failed": failed,
        })
        self.write({"last_sync_date": fields.Datetime.now(), "last_sync_message": message})

    @staticmethod
    def _notify(message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ArcGIS Integration"),
                "message": message,
                "type": notification_type,
                "sticky": True,
            },
        }

    @api.model
    def _cron_sync_enabled_connectors(self):
        for connector in self.search([
            ("active", "=", True), ("auto_sync_enabled", "=", True)
        ]):
            try:
                connector.action_sync_now()
            except Exception as exc:
                _logger.exception("Scheduled ArcGIS synchronization failed for connector %s", connector.id)
                self.env["arcgis.sync.log"].create({
                    "connector_id": connector.id, "operation": "sync",
                    "state": "error", "message": str(exc),
                })
                connector.write({
                    "last_sync_date": fields.Datetime.now(),
                    "last_sync_message": str(exc),
                })

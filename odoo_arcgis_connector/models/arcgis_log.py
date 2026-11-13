from odoo import fields, models


class ArcGISSyncLog(models.Model):
    _name = "arcgis.sync.log"
    _description = "ArcGIS Synchronization Log"
    _order = "create_date desc, id desc"

    connector_id = fields.Many2one("arcgis.connector", string="Connector", ondelete="set null")
    operation = fields.Selection([
        ("test", "Connection Test"),
        ("preview", "Dry Run"),
        ("sync", "Synchronization"),
    ], required=True, default="sync")
    state = fields.Selection([
        ("success", "Success"), ("warning", "Warning"), ("error", "Error")
    ], required=True, default="success")
    message = fields.Text(required=True)
    tasks_read = fields.Integer()
    features_ready = fields.Integer()
    added = fields.Integer()
    updated = fields.Integer()
    skipped = fields.Integer()
    failed = fields.Integer()

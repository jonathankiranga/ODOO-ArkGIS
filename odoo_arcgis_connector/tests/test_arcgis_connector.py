from unittest.mock import patch

import requests

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestArcGISConnector(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connector = cls.env["arcgis.connector"].create({
            "name": "ArcGIS Test Connector",
            "layer_url": "https://example.arcgis.com/arcgis/rest/services/Test/FeatureServer/0",
            "arcgis_token": "test-token",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer",
            "partner_latitude": -1.286389,
            "partner_longitude": 36.817223,
        })
        cls.task = cls.env["project.task"].create({
            "name": "Test Task",
            "partner_id": cls.partner.id,
        })

    def test_http_layer_url_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.connector.write({"layer_url": "http://example.com/FeatureServer/0"})

    def test_connection_failure_is_reported(self):
        with patch(
            "odoo.addons.odoo_arcgis_connector.models.arcgis_connector.requests.post",
            side_effect=requests.ConnectionError("network down"),
        ):
            with self.assertRaises(UserError):
                self.connector._arcgis_post("query", {"where": "1=1"})

    def test_missing_coordinates_skip_task(self):
        partner = self.env["res.partner"].create({"name": "No GPS"})
        task = self.env["project.task"].create({
            "name": "Task without GPS",
            "partner_id": partner.id,
        })
        self.assertFalse(self.connector._task_feature(task))

    def test_new_feature_is_counted_as_added(self):
        feature = self.connector._task_feature(self.task)
        with patch.object(
            type(self.connector), "_arcgis_post",
            return_value={"addResults": [{"success": True}]},
        ):
            self.assertEqual(self.connector._apply_edits([feature], []), (1, 0, 0))

    def test_existing_feature_is_counted_as_updated(self):
        feature = self.connector._task_feature(self.task)
        feature["attributes"]["OBJECTID"] = 123
        with patch.object(
            type(self.connector), "_arcgis_post",
            return_value={"updateResults": [{"success": True}]},
        ):
            self.assertEqual(self.connector._apply_edits([], [feature]), (0, 1, 0))

    def test_duplicate_task_is_routed_to_update_not_add(self):
        feature = self.connector._task_feature(self.task)
        task_id = self.task.id
        with patch.object(type(self.connector), "_collect_features", return_value=(1, [feature], 0, fields.Datetime.now())), \
             patch.object(type(self.connector), "_existing_objectids", return_value={task_id: 987}), \
             patch.object(type(self.connector), "_apply_edits", return_value=(0, 1, 0)) as apply_edits:
            self.connector.action_sync_now()
        adds, updates = apply_edits.call_args.args
        self.assertEqual(adds, [])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["attributes"]["OBJECTID"], 987)

    def test_partial_apply_edits_response_counts_missing_results_as_failures(self):
        feature = self.connector._task_feature(self.task)
        with patch.object(
            type(self.connector), "_arcgis_post",
            return_value={"addResults": []},
        ):
            self.assertEqual(self.connector._apply_edits([feature], []), (0, 0, 1))

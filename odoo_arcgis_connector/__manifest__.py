{
    "name": "Odoo ArcGIS Connector",
    "version": "19.0.1.1.0",
    "category": "Project",
    "summary": "Synchronize Odoo project tasks to an ArcGIS hosted feature layer",
    "description": "One-way synchronization of Odoo Project tasks to ArcGIS Feature Services.",
    "author": "Custom Integration",
    "license": "LGPL-3",
    "depends": ["base", "project", "base_geolocalize"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "views/arcgis_connector_views.xml",
        "views/arcgis_log_views.xml",
        "data/ir_cron.xml",
    ],
    "application": True,
    "installable": True,
}

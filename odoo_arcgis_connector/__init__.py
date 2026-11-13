from . import models

# Load tests only when Odoo's test runner is enabled.
from odoo.tools import config

if config["test_enable"]:
    from . import tests

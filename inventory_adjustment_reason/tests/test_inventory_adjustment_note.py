from datetime import datetime

from odoo.tests import tagged

from .common import TestCommon


@tagged("post_install", "-at_install")
class TestInventoryAdjustmentNote(TestCommon):
    def test_inventory_adjustment_note(self):
        # Create a new inventory adjustment
        stock_adjustment = self.model_stock_quant.create(
            {
                "inventory_date": datetime.now(),
                "location_id": self.env.ref("stock.stock_location_stock").id,
                "note": "This is a test note",
                "product_id": self.product1.id,
                "inventory_quantity": 10,
            }
        )
        # Check that the note is set
        self.assertEqual(stock_adjustment.note, "This is a test note")

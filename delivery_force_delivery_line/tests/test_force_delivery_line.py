from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.delivery.tests.test_delivery_cost import TestDeliveryCost


@tagged("-at_install", "post_install")
class TestForceDeliveryLine(TestDeliveryCost):
    def test_force_delivery_cost(self):
        sale_order = self.env["sale.order"].create({"partner_id": self.partner_18.id})

        self.env["sale.order.line"].create(
            {
                "order_id": sale_order.id,
                "product_id": self.product_delivery_normal.id,
                "is_delivery": False,
            }
        )

        with self.assertRaises(UserError):
            sale_order.action_confirm()

        self.env["sale.order.line"].create(
            {
                "order_id": sale_order.id,
                "product_id": self.product_delivery_normal.id,
                "is_delivery": True,
            }
        )

        with self.assertNotRaises(UserError):
            sale_order.action_confirm()

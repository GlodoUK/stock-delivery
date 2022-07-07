from odoo.tests import tagged

from odoo.addons.product_commingle.tests.common import CommonCommingleCase


@tagged("post_install", "-at_install")
class TestStock(CommonCommingleCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.product_bolta.type = "product"
        cls.product_boltb.type = "product"
        cls.product_bolt_equiv.type = "product"
        cls.product_bolt_equiv.commingled_policy = "strict"

        cls.partner_id = cls.env["res.partner"].create({"name": "Partner A"})
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")

        cls.outbound_move_filters = {
            "incoming_moves": lambda m: m.location_dest_id.usage == "customer"
            and (
                not m.origin_returned_move_id
                or (m.origin_returned_move_id and m.to_refund)
            ),
            "outgoing_moves": lambda m: m.location_dest_id.usage != "customer"
            and m.to_refund,
        }

    def test_strict_default(self):
        picking_id = self.env["stock.picking"].create(
            {
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "move_lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_bolt_equiv.id,
                            "product_uom": self.product_bolt_equiv.uom_id.id,
                            "product_uom_qty": 1.0,
                            "name": "test_move_1",
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                            "picking_type_id": self.env.ref(
                                "stock.picking_type_out"
                            ).id,
                        },
                    ),
                ],
            }
        )

        picking_id.action_confirm()
        self.assertEqual(len(picking_id.move_lines), 1)
        self.assertEqual(picking_id.move_lines.product_id, self.product_bolta)
        self.assertEqual(
            picking_id.move_lines.product_commingled_id,
            self.product_bolt_equiv.commingled_ids.filtered(
                lambda c: c.product_id == self.product_bolta
            ),
        )
        self.assertEqual(
            picking_id.move_lines._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            1,
        )

        done_moves = picking_id.move_lines.filtered(lambda m: m.state == "done")

        self.assertEqual(
            done_moves._compute_commingled_quantities(
                self.product_bolt_equiv,
                self.outbound_move_filters,
            ),
            0,
        )

    def test_strict_reordered(self):
        self.product_bolt_equiv.commingled_ids.filtered(
            lambda r: r.product_id == self.product_bolta
        ).write({"sequence": 10})
        self.product_bolt_equiv.invalidate_cache()

        picking_id = self.env["stock.picking"].create(
            {
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "move_lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_bolt_equiv.id,
                            "product_uom": self.product_bolt_equiv.uom_id.id,
                            "product_uom_qty": 1.0,
                            "name": "test_move_1",
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                            "picking_type_id": self.env.ref(
                                "stock.picking_type_out"
                            ).id,
                        },
                    ),
                ],
            }
        )

        picking_id.action_confirm()
        self.assertEqual(len(picking_id.move_lines), 1)
        self.assertEqual(picking_id.move_lines.product_id, self.product_boltb)
        self.assertEqual(
            picking_id.move_lines.product_commingled_id,
            self.product_bolt_equiv.commingled_ids.filtered(
                lambda c: c.product_id == self.product_boltb
            ),
        )
        self.assertEqual(
            picking_id.move_lines._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            1,
        )

        self.assertEqual(
            picking_id.move_lines.filtered(
                lambda m: m.state == "done"
            )._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            0,
        )

    def test_deplete(self):
        self.product_bolt_equiv.write({"commingled_policy": "deplete"})
        self.product_bolt_equiv.invalidate_cache()

        self.env["stock.quant"]._update_available_quantity(
            self.product_boltb, self.stock_location, 100
        )

        self.env["stock.quant"]._update_available_quantity(
            self.product_bolta, self.stock_location, 500
        )

        self.product_bolt_equiv.invalidate_cache()

        picking_id = self.env["stock.picking"].create(
            {
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "move_lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_bolt_equiv.id,
                            "product_uom": self.product_bolt_equiv.uom_id.id,
                            "product_uom_qty": 1.0,
                            "name": "test_move_1",
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                            "picking_type_id": self.env.ref(
                                "stock.picking_type_out"
                            ).id,
                        },
                    ),
                ],
            }
        )

        picking_id.action_confirm()
        self.assertEqual(len(picking_id.move_lines), 1)
        self.assertEqual(picking_id.move_lines.product_id, self.product_boltb)
        self.assertEqual(
            picking_id.move_lines.product_commingled_id,
            self.product_bolt_equiv.commingled_ids.filtered(
                lambda c: c.product_id == self.product_boltb
            ),
        )

        self.assertEqual(
            picking_id.move_lines._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            1,
        )

        self.assertEqual(
            picking_id.move_lines.filtered(
                lambda m: m.state == "done"
            )._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            0,
        )

    def test_deplete_prefer_homogenous(self):
        self.product_bolt_equiv.write(
            {
                "commingled_policy": "deplete",
                "commingled_prefer_homogenous": True,
            }
        )
        self.product_bolt_equiv.invalidate_cache()

        self.env["stock.quant"]._update_available_quantity(
            self.product_boltb, self.stock_location, 100
        )

        self.env["stock.quant"]._update_available_quantity(
            self.product_bolta, self.stock_location, 500
        )

        self.product_bolt_equiv.invalidate_cache()

        picking_id = self.env["stock.picking"].create(
            {
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "move_lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_bolt_equiv.id,
                            "product_uom": self.product_bolt_equiv.uom_id.id,
                            "product_uom_qty": 102,
                            "name": "test_move_1",
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                            "picking_type_id": self.env.ref(
                                "stock.picking_type_out"
                            ).id,
                        },
                    ),
                ],
            }
        )

        picking_id.action_confirm()
        self.assertEqual(len(picking_id.move_lines), 1)
        self.assertEqual(picking_id.move_lines.product_id, self.product_bolta)
        self.assertEqual(
            picking_id.move_lines.product_commingled_id,
            self.product_bolt_equiv.commingled_ids.filtered(
                lambda c: c.product_id == self.product_bolta
            ),
        )
        self.assertEqual(
            picking_id.move_lines._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            102,
        )

        self.assertEqual(
            picking_id.move_lines.filtered(
                lambda m: m.state == "done"
            )._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            0,
        )

    def test_deplete_no_prefer_homogenous(self):
        self.product_bolt_equiv.write(
            {
                "commingled_policy": "deplete",
                "commingled_prefer_homogenous": False,
            }
        )
        self.product_bolt_equiv.invalidate_cache()

        self.env["stock.quant"]._update_available_quantity(
            self.product_boltb, self.stock_location, 100
        )

        self.env["stock.quant"]._update_available_quantity(
            self.product_bolta, self.stock_location, 500
        )

        self.product_bolt_equiv.invalidate_cache()

        picking_id = self.env["stock.picking"].create(
            {
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "move_lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_bolt_equiv.id,
                            "product_uom": self.product_bolt_equiv.uom_id.id,
                            "product_uom_qty": 102,
                            "name": "test_move_1",
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                            "picking_type_id": self.env.ref(
                                "stock.picking_type_out"
                            ).id,
                        },
                    ),
                ],
            }
        )

        picking_id.action_confirm()
        self.assertEqual(len(picking_id.move_lines), 2)
        self.assertEqual(
            picking_id.move_lines._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            102,
        )

        self.assertEqual(
            picking_id.move_lines.filtered(
                lambda m: m.state == "done"
            )._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            0,
        )

    def test_deplete_split(self):
        self.product_bolt_equiv.write({"commingled_policy": "deplete"})
        self.product_bolt_equiv.invalidate_cache()

        self.env["stock.quant"]._update_available_quantity(
            self.product_boltb, self.stock_location, 100
        )

        self.env["stock.quant"]._update_available_quantity(
            self.product_bolta, self.stock_location, 100
        )

        self.product_bolt_equiv.invalidate_cache()

        picking_id = self.env["stock.picking"].create(
            {
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "move_lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_bolt_equiv.id,
                            "product_uom": self.product_bolt_equiv.uom_id.id,
                            "product_uom_qty": 102,
                            "name": "test_move_1",
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                            "picking_type_id": self.env.ref(
                                "stock.picking_type_out"
                            ).id,
                        },
                    ),
                ],
            }
        )

        picking_id.action_confirm()
        self.assertEqual(len(picking_id.move_lines), 2)

        self.assertEqual(
            picking_id.move_lines._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            102,
        )

        self.assertEqual(
            picking_id.move_lines.filtered(
                lambda m: m.state == "done"
            )._compute_commingled_quantities(
                self.product_bolt_equiv, self.outbound_move_filters
            ),
            0,
        )

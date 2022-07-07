from odoo import _, api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _compute_qty_delivered(self):
        res = super(SaleOrderLine, self)._compute_qty_delivered()

        filters = {
            "incoming_moves": lambda m: m.location_dest_id.usage == "customer"
            and (
                not m.origin_returned_move_id
                or (m.origin_returned_move_id and m.to_refund)
            ),
            "outgoing_moves": lambda m: m.location_dest_id.usage != "customer"
            and m.to_refund,
        }

        for order_line in self.filtered(
            lambda l: l.product_id.commingled_ok
            and l.qty_delivered_method == "stock_move"
        ):
            done_moves = order_line.mapped("move_ids").filtered(
                lambda m: m.state == "done"
            )
            order_line.qty_delivered = done_moves._compute_commingled_quantities(
                order_line.product_id, filters
            )
        return res

    @api.onchange(
        "product_id",
        "product_uom_qty",
        "product_uom",
        "warehouse_id",
    )
    def _onchange_product_id_commingle(self):
        if (
            not self.product_id.commingled_ok
            or not self.product_uom_qty
            or not self.product_uom
        ):
            return

        quantity = self.product_uom._compute_quantity(
            self.product_uom_qty,
            self.product_id.uom_id,
        )

        lines = self.product_id._explode_commingled(
            quantity,
            self.order_id.warehouse_id.lot_stock_id,
        )

        if len(lines) > 1:
            return {
                "warning": {
                    "title": "Warning",
                    "message": _("This product will split into %s lines") % len(lines),
                }
            }

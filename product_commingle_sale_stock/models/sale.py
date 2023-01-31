from odoo import _, api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _compute_qty_delivered(self):
        res = super(SaleOrderLine, self)._compute_qty_delivered()
        for order_line in self.filtered(
            lambda l: l.product_id.commingled_ok
            and l.qty_delivered_method == "stock_move"
        ):
            # TODO: we aren't supporting partial delivery of commingled products
            # due to the complications of kits within commingled products, and
            # how we go about dealing with those.
            if all(m.state == "done" for m in order_line.move_ids):
                order_line.qty_delivered = order_line.product_uom_qty
            else:
                order_line.qty_delivered = 0.0
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

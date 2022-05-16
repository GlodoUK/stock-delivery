from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    alternatives = fields.Many2many("product.product")

    def action_suggest_alts(self):
        self.ensure_one()
        return {
            "name": _("Available Alternatives"),  # Name You want to display on wizard
            "view_mode": "form",
            "res_model": "wizard.suggest_alternatives",
            "type": "ir.actions.act_window",
            "target": "new",
            "context": {
                "default_product_id": self.product_id.id,
                "default_alternative_ids": self.product_id.stock_backup_ids.ids,
                "default_order_line_id": self.id,
                "default_demand": self.product_uom_qty,
            },
        }

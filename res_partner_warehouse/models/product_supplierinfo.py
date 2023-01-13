from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    res_partner_warehouse_id = fields.Many2one(
        "res.partner.warehouse",
        domain="[('partner_id', '=', name)]",
        string="Partner Warehouse",
    )

    res_partner_warehouse_quantity = fields.Float(
        compute="_compute_res_partner_warehouse_quantity",
        string="Partner Quantity",
    )

    def _compute_res_partner_warehouse_quantity(self):
        for record in self:
            if not record.res_partner_warehouse_id:
                record.res_partner_warehouse_quantity = False
                continue

            record.res_partner_warehouse_quantity = (
                record.res_partner_warehouse_id._get_available_quantity(
                    record.product_id
                    or fields.first(record.product_tmpl_id.product_variant_ids),
                    uom_id=record.product_uom,
                )
            )

    @api.constrains("res_partner_warehouse_id", "name")
    def _check_res_partner_warehouse_id(self):
        for record in self.filtered(lambda r: r.res_partner_warehouse_id):
            if record.res_partner_warehouse_id.partner_id != record.name:
                raise ValidationError(
                    _("Partner on warehouse and supplier info record do not match!")
                )

    def action_view_res_partner_warehouse_quants(self):
        self.ensure_one()

        if not self.res_partner_warehouse_id:
            raise UserError(_("No partner warehouse set!"))

        return self.res_partner_warehouse_id.action_view_quants()

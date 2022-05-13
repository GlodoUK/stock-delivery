from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    commingled_ok = fields.Boolean(
        "Is Commingled?",
    )
    commingled_ids = fields.One2many(
        "product.commingled",
        compute="_compute_commingled",
        inverse="_inverse_commingled",
    )
    used_in_commingled_ids = fields.One2many(
        related="product_variant_ids.used_in_commingled_ids",
    )

    @api.depends("product_variant_ids", "product_variant_ids.commingled_ids")
    def _compute_commingled(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.commingled_ids = p.product_variant_ids.commingled_ids
            else:
                p.commingled_ids = False

    def _inverse_commingled(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.product_variant_ids.commingled_ids = p.commingled_ids

    @api.constrains("company_id", "product_variant_ids")
    def _check_commingled_company(self):
        # Ensure that the commingled products are all in the same company
        for record in self:
            for line in record.commingled_ids:
                if (
                    line.product_id.company_id and record.company_id
                ) and line.product_id.company_id != record.company_id:
                    raise ValidationError(
                        _(
                            "Commingled products must be in the company same as"
                            " the parent product"
                        )
                    )
            for line in record.used_in_commingled_ids:
                if (
                    line.product_id.company_id and record.company_id
                ) and line.parent_product_id.company_id != record.company_id:
                    raise ValidationError(
                        _(
                            "Commingled products must be in the company same as"
                            " the parent product"
                        )
                    )

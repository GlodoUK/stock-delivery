from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    commingled_ids = fields.One2many(
        "product.commingled",
        "parent_product_id",
        "Commingled Products",
        copy=False,
    )

    used_in_commingled_ids = fields.One2many(
        "product.commingled",
        "product_id",
        copy=False,
    )

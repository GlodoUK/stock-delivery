from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.depends("commingled_ids")
    def _compute_available_quantities(self):
        return super()._compute_available_quantities()

    def _compute_available_quantities_dict(self):
        res, stock_dict = super()._compute_available_quantities_dict()
        icp = self.env["ir.config_parameter"]
        based_on = icp.sudo().get_param("stock_available_mrp_based_on", "potential_qty")

        todo = self.filtered(lambda p: p.commingled_ok)

        if not todo:
            return res, stock_dict

        component_ids = self.env["product.product"]
        while todo:
            component_ids = todo.mapped("commingled_ids.product_id").filtered(
                lambda p: not p.commingled_ok
            )
            todo = component_ids.filtered(lambda p: p.commingled_ok)

        (
            commingled_res,
            commingled_stock_dict,
        ) = component_ids._compute_available_quantities_dict()
        stock_dict = {**stock_dict, **commingled_stock_dict}
        res = {**res, **commingled_res}

        for product_id in self.filtered(lambda p: p.commingled_ok and p.commingled_ids):
            # TODO: Create an explode-all-at-once method?
            needs = product_id._explode_commingled_needs(1)

            potential = []

            for line, _need in needs:
                fallback = stock_dict[line.product_id.id]["qty_available"]
                potential.append(stock_dict[line.product_id.id].get(based_on, fallback))

            potential = sum(potential)

            res[product_id.id]["qty_available"] = potential
            res[product_id.id]["potential_qty"] = potential
            res[product_id.id]["immediately_usable_qty"] = potential

        return res, stock_dict

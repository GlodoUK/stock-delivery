from odoo import models, fields, api, _


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.multi
    def _run_buy(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        res = super()._run_buy(product_id, product_qty, product_uom, location_id, name, origin, values)
        print("8<----------")
        print("Running buy %s for %s against %s, w/ %s" % (self, product_id, location_id, values))
        print("---------->8")
        return res

    @api.multi
    def _run_manufacture(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        res = super()._run_manufacture(product_id, product_qty, product_uom, location_id, name, origin, values)
        print("8<----------")
        print("Running manufacture %s for %s against %s, w/ %s" % (self, product_id, location_id, values))
        print("---------->8")

        return res

    @api.multi
    def _run_push(self, move):
        res = super()._run_push(move)
        print("8<----------")
        print("Running push %s for %s" % (self, move))
        print("---------->8")

        return res

    @api.multi
    def _run_pull(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        res = super()._run_pull(product_id, product_qty, product_uom, location_id, name, origin, values)

        print("8<----------")
        print("Running pull %s for %s against %s, w/ %s" % (self, product_id, location_id, values))
        print("---------->8")

        return res

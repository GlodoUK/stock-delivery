from odoo import fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"
    note = fields.Text(string="Inventory Adjustment Reason")

    def _get_inventory_fields_write(self):
        res = super()._get_inventory_fields_write()
        res.extend(["note"])
        return res

    def _get_inventory_move_values(self, qty, location_id, location_dest_id, out=False):
        """Function to super _get_inventory_move_values"""
        res = super()._get_inventory_move_values(
            qty, location_id, location_dest_id, out
        )
        move_line = res["move_line_ids"]
        move_line[0][2]["note"] = self.note
        res.update({"move_line_ids": move_line})

        return res

    def _apply_inventory(self):
        res = super()._apply_inventory()

        self.write({"note": self.note})

        return res


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    note = fields.Text()

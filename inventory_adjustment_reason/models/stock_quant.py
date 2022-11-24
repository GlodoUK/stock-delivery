from odoo import fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"
    note = fields.Text(string="Inventory Adjustment Reason")

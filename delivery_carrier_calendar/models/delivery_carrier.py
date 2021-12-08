from dateutil.relativedelta import relativedelta

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    carrier_calendar_id = fields.Many2one("resource.calendar")

    def plan_days(
        self, day_dt, days=1, compute_leaves=True, domain=None, safety_lead_days=1
    ):
        self.ensure_one()

        if not self.carrier_calendar_id:
            return False

        if safety_lead_days > 0:
            day_dt = day_dt + relativedelta(days=safety_lead_days)

        return self.carrier_calendar_id.plan_days(
            days, day_dt, compute_leaves=compute_leaves, domain=domain
        )

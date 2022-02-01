from dateutil.relativedelta import relativedelta

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    carrier_calendar_id = fields.Many2one("resource.calendar")
    lead_time = fields.Integer(
        string="Lead Time",
        help="Lead time for this carrier, in days.",
        default=0,
    )

    def plan_days(
        self,
        day_dt,
        days=1,
        compute_leaves=True,
        domain=None,
        safety_lead_days=1
    ):
        self.ensure_one()

        lead_days = 0

        if safety_lead_days:
            lead_days += safety_lead_days

        if self.lead_time:
            lead_days += self.lead_time

        day_dt = day_dt + relativedelta(days=lead_days)

        if self.carrier_calendar_id:
            return self.carrier_calendar_id.plan_days(
                days, day_dt, compute_leaves=compute_leaves, domain=domain
            )

        return day_dt



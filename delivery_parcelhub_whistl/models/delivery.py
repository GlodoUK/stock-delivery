import binascii
import datetime
import urllib

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("whistl", "Whistl/Parcelhub")], ondelete={"whistl": "cascade"}
    )

    whistl_api_key = fields.Char(string="Whistl/Parcelhub API Key")
    whistl_base_url = fields.Char(compute="_compute_whistl_base_url", store=True)
    whistl_service = fields.Many2one("delivery.whistl.service")
    whistl_label_format = fields.Selection(
        [
            ("pdf", "PDF"),
            ("png", "PNG"),
            ("zpl", "ZPL300"),
            ("zpl2", "ZPL200"),
            ("epl", "EPL"),
        ],
        required=True,
        default="pdf",
    )

    @api.depends("prod_environment")
    def _compute_whistl_base_url(self):
        for carrier in self:
            if carrier.prod_environment:
                carrier.whistl_base_url = "https://despatch.whistl.co.uk/"
            else:
                carrier.whistl_base_url = "https://despatchuat.whistl.co.uk/"

    @api.onchange("delivery_type", "whistl_api_key")
    def onchange_delivery_type_whistl(self):
        if (
            self.delivery_type == "whistl"
            and self.whistl_api_key
            and not self.whistl_service
        ):
            self.action_whistl_get_services()

    def _get_whistl_url(self, endpoint, args):
        self.ensure_one()
        url = list(urllib.parse.urlparse(self.whistl_base_url))
        url[2] = endpoint
        url[4] = urllib.parse.urlencode(args)
        return urllib.parse.urlunparse(url)

    def action_whistl_get_services(self):
        service_model = self.env["delivery.whistl.service"].sudo()

        request_url = self._get_whistl_url("Service")

        response = requests.post(
            request_url,
            headers={
                "Content-Type": "text/json",
            },
            json={
                "Apikey": self.whistl_api_key,
                "Command": "GetServices",
            },
        )
        services = response.json().get("Services", {})
        service_list = services.get("List", {})
        allowed_services = services.get("AllowedServices", [])

        existing_services = service_model.with_context(active_test=False).search([])

        for existing_service in existing_services:
            if existing_service.ref not in allowed_services:
                existing_service.active = False

        for service in allowed_services:
            existing = existing_services.filtered(lambda s: s.ref == service)
            if existing:
                existing.active = True
                continue
            service_model.create(
                {
                    "ref": service,
                    "name": service_list.get(service),
                }
            )

    def whistl_rate_shipment(self, order):
        matches = self._match_address(order.partner_shipping_id)
        if not matches:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _(
                    "Error: this delivery method is not available for this address."
                ),
                "warning_message": False,
            }

        price = order.pricelist_id.get_product_price(
            self.product_id, 1.0, order.partner_id
        )

        return {
            "success": True,
            "price": price,
            "error_message": False,
            "warning_message": _(
                "Whistl API does not support dynamic rating at this time"
            ),
        }

    def whistl_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            order = picking.sale_id
            product_list = []
            for line in picking.move_lines:
                product_list.append(
                    {
                        "Description": line.name,
                        "Sku": line.product_id.default_code,
                        "OriginCountry": picking.location_id.company_id.country_id.code,
                        "Quantity": line.product_uom_qty,
                        "Value": line.product_id.lst_price,
                        "Weight": line.product_id.weight,
                        "HsCode": line.product_id.hs_code or "",
                    }
                )
            order_value = 0.0
            order_name = picking.name
            order_date = picking.create_date.strftime("%Y-%m-%d")
            if order:
                order_value = order.amount_untaxed
                order_name = order.client_order_ref or order.name
                order_date = order.date_order.strftime("%Y-%m-%d")

            request_url = self._get_whistl_url(
                "Shipment"
            )  # TODO: Check this is correct

            response = requests.post(
                request_url,
                headers={
                    "Content-Type": "text/json",
                },
                json={
                    "Apikey": self.whistl_api_key,
                    "Command": "OrderShipment",
                    "Shipment": {
                        "LabelFormat": self.whistl_label_format,
                        "ShipperReference": picking.name,
                        "OrderReference": order_name,
                        "OrderDate": order_date,
                        "Service": self.whistl_service.ref,
                        "Weight": picking.shipping_weight,
                        "WeightUnit": picking.weight_uom_name,
                        "Value": order_value,
                        "Currency": picking.company_id.currency_id.name,
                        "ConsignorAddress": {
                            "Name": picking.location_id.company_id.name,
                            "Company": picking.location_id.company_id.name,
                        },
                        "ConsigneeAddress": {
                            "Name": picking.partner_id.name,
                            "Company": picking.partner_id.name,
                            "AddressLine1": picking.partner_id.street,
                            "AddressLine2": picking.partner_id.street2,
                            "City": picking.partner_id.city,
                            "State": picking.partner_id.state_id.name,
                            "Zip": picking.partner_id.zip,
                            "Country": picking.partner_id.country_id.code or "",
                            "Phone": picking.partner_id.phone,
                            "Email": picking.partner_id.email,
                            "Vat": picking.partner_id.vat,
                        },
                        "Products": product_list,
                    },
                },
            )
            if not response:
                raise ValidationError(_("Unknown Whistl API Error"))

            json = response.json()

            if json.get("ErrorLevel") != 0:
                raise ValidationError(_("Whistl API Error: %s") % json.get("Error"))

            shipment = json.get("Shipment")
            tracking = shipment.get("TrackingNumber")
            tracking_url = shipment.get("CarrierTrackingUrl")
            attachments_list = None

            if shipment.get("LabelImage"):
                attachments_list = [
                    (
                        "Whistl_%s.%s"
                        % (
                            str(tracking),
                            self.whistl_label_format.replace("2", ""),
                        ),
                        binascii.a2b_base64(str(shipment.get("LabelImage"))),
                    )
                ]

            picking.message_post(
                body=_(
                    "Shipment sent to Whistl<br/>"
                    "Carrier: %(carrier_name)s<br/>"
                    "Tracking Number: %(tracking_ref)s<br/>"
                    "Tracking URL: %(url)s"
                )
                % {
                    "carrier_name": shipment.get("Carrier"),
                    "tracking_ref": tracking,
                    "url": tracking_url,
                },
                attachments=attachments_list,
            )

            picking.write(
                {
                    "carrier_consignment_ref": picking.name,
                    "whistl_carrier": shipment.get("Carrier"),
                    "whistl_tracking_url": tracking_url,
                }
            )
            self.whistl_tracking_state_update(picking)

            res.append(
                {
                    "exact_price": 0.0,
                    "tracking_number": tracking,
                    "date_delivery": fields.Date.today(),
                    "weight": picking.shipping_weight,
                }
            )

        return res

    def whistl_cancel_shipment(self, pickings):
        for picking in pickings:
            request_url = self._get_whistl_url(
                "Shipment"
            )  # TODO: Check this is correct
            response = requests.post(
                request_url,
                headers={
                    "Content-Type": "text/json",
                },
                json={
                    "Apikey": self.whistl_api_key,
                    "Command": "VoidShipment",
                    "Shipment": {
                        "ShipperReference": picking.name,
                    },
                },
            )
            if not response:
                raise ValidationError(_("Unknown Whistl API Error"))

            json = response.json()

            if json.get("ErrorLevel") != 0:
                raise ValidationError(_("Whistl API Error: %s") % json.get("Error"))
            picking.carrier_tracking_url = False

    def whistl_tracking_state_update_scheduled(self):
        pickings = self.env["stock.picking"].search(
            [
                ("carrier_id", "=", self.id),
                ("state", "=", "done"),
                (
                    "delivery_state",
                    "not in",
                    ["customer_delivered", "warehouse_delivered"],
                ),
                ("date_next_tracking_update", "<=", fields.datetime.now()),
                "|",
                ("carrier_consignment_ref", "!=", False),
                ("carrier_tracking_ref", "!=", False),
            ]
        )
        for picking in pickings:
            if picking.delivery_state in ["customer_delivered", "warehouse_delivered"]:
                continue
            self.whistl_tracking_state_update(picking)

    def whistl_tracking_state_update(self, picking):
        request_url = self._get_whistl_url("Shipment")  # TODO: Check this is correct
        response = requests.post(
            request_url,
            headers={
                "Content-Type": "text/json",
            },
            json={
                "Apikey": self.whistl_api_key,
                "Command": "TrackShipment",
                "Shipment": {
                    "ShipperReference": picking.name,
                },
            },
        )
        if not response:
            raise ValidationError(_("Unknown Whistl API Error"))

        json = response.json()

        if json.get("ErrorLevel") != 0:
            picking.message_post(body=_("Whistl API Error: %s") % json.get("Error"))

        shipment = json.get("Shipment", {})
        events = sorted(shipment.get("Events", []), key=lambda e: e.get("DateTime"))
        if len(events) > picking.tracking_history_count:
            for index, event in enumerate(events):
                if index > picking.tracking_history_count - 1:
                    self.env["stock.picking.tracking.history"].create(
                        {
                            "picking_id": picking.id,
                            "date_event": event.get("DateTime"),
                            "description": "%s: %s (%s, %s)"
                            % (
                                event.get("Code"),
                                event.get("Description"),
                                event.get("CarrierCode"),
                                event.get("CarrierDescription"),
                            ),
                        }
                    )
            # latest_event = events[-1]
            # TODO: current_state = WHISTL_DELIVERY_CODE_MAP.get(latest_event.get("Code"))
            # if not current_state:
            #     picking.delivery_state = "unknown"
            # else:
            #     picking.delivery_state = current_state
            #     picking.tracking_state = "%s: %s (%s, %s)" % (
            #         latest_event.get("Code"),
            #         latest_event.get("Description"),
            #         latest_event.get("CarrierCode"),
            #         latest_event.get("CarrierDescription"),
            #     )
            # if current_state in ["customer_delivered", "warehouse_delivered"]:
            #     picking.date_delivered = latest_event.get("DateTime")

    def whistl_tracking_state_calc_next_update(self, picking):
        if picking.delivery_state in ["customer_delivered", "warehouse_delivered"]:
            return False
        return fields.datetime.now() + datetime.timedelta(hours=4)

    def whistl_get_tracking_link(self, picking):
        return picking.whistl_tracking_url


class WhistlService(models.Model):
    _name = "delivery.whistl.service"
    _description = "Whistl Service"

    active = fields.Boolean(default=True)
    name = fields.Char()
    ref = fields.Char()

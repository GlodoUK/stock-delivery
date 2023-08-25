import binascii
import datetime
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

WHISLT_XMLNS = "http://api.parcelhub.net/schemas/api/parcelhub-api-v0.4.xsd"


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("whistl", "Whistl/Parcelhub")], ondelete={"whistl": "cascade"}
    )

    whistl_base_url = fields.Char(compute="_compute_whistl_base_url", store=True)
    whistl_username = fields.Char(string="Whistl/Parcelhub Username")
    whistl_password = fields.Char(string="Whistl/Parcelhub Password")
    whistl_account = fields.Char(string="Whistl/Parcelhub Account Ref")
    whistl_token = fields.Text(string="Whistl/Parcelhub Token")
    whistl_refresh_token = fields.Char(string="Whistl/Parcelhub Refresh Token")
    whistl_token_expiry = fields.Datetime(string="Whistl/Parcelhub Token Expiry")

    whistl_tracking_api_key = fields.Char(
        string="Whistl/Parcelhub Tracking API Key",
        help="This is available from your Whistl/Parcelhub account preferences",
    )

    whistl_service_preference_list = fields.Integer(
        string="Service Preference List ID",
        help=(
            "Configure your service preference list in your Whistl/Parcelhub"
            " account and enter the ID here"
        ),
    )

    whistl_label_format = fields.Selection(
        [
            ("ZML", "ZPL"),
            ("PDF", "PDF"),
            ("PNG", "PNG"),
            ("EPL", "EPL"),
        ],
        required=True,
        default="PDF",
    )

    whistl_label_size = fields.Selection(
        [
            ("8", "Size 8"),
            ("6", "Size 6"),
            ("4", "Size 4"),
            ("2", "Size 2"),
        ],
        required=True,
        default="8",
    )  # TODO: Flesh this out, or pull from API

    @api.depends("prod_environment")
    def _compute_whistl_base_url(self):
        for carrier in self:
            if carrier.prod_environment:
                carrier.whistl_base_url = "https://api.parcelhub.net/1.0/"
            else:
                carrier.whistl_base_url = "https://api.whistl.parcelhub.net/"

    def _get_whistl_url(self, endpoint, args=False):
        self.ensure_one()
        url = urllib.parse.urljoin(self.whistl_base_url, endpoint)
        if self.whistl_account:
            args = args or {}
            args["account"] = self.whistl_account
        if args:
            url += "?" + urllib.parse.urlencode(args)
        return url

    def _get_whistl_headers(self, with_auth=True):
        self.ensure_one()
        headers = {
            "Content-Type": "application/xml; charset=utf-8",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
        }
        if with_auth:
            headers["Authorization"] = "Bearer %s" % self.whistl_get_auth_token()
        return headers

    def whistl_get_auth_token(self):
        request_url = self._get_whistl_url("TokenV2")

        now = fields.datetime.now()

        if self.whistl_token and self.whistl_token_expiry < now + datetime.timedelta(
            seconds=60
        ):
            # We already have a valid token
            return self.whistl_token

        if (
            self.whistl_refresh_token
            and self.whistl_token_expiry < now + datetime.timedelta(seconds=1800)
        ):
            # Token expires in less than 30 minutes, refresh it
            request = ET.Element("RefreshToken")
            ET.SubElement(request, "grant_type").text = "refreshtoken"
            ET.SubElement(request, "username").text = self.whistl_refresh_token
            ET.SubElement(request, "password").text = ""
        else:
            # Get a new token
            request = ET.Element("RequestToken")
            ET.SubElement(request, "grant_type").text = "bearer"
            ET.SubElement(request, "username").text = self.whistl_username
            ET.SubElement(request, "password").text = self.whistl_password

        response = requests.post(
            request_url,
            headers=self._get_whistl_headers(False),
            data=ET.tostring(request),
            timeout=20,
        )
        if not response.status_code == 200:
            raise ValidationError(
                _("Whistl API Error Requesting Token: %s") % response.status_code
            )

        response_xml = ET.fromstring(response.content)

        self.whistl_token = response_xml.find("access_token").text
        self.whistl_refresh_token = response_xml.find("refreshToken").text
        self.whistl_token_expiry = now + datetime.timedelta(
            seconds=int(response_xml.find("expiresIn").text)
        )

        return self.whistl_token

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

            # Build Shipment
            shipment = ET.Element("Shipment")
            shipment.attrib["xmlns"] = WHISLT_XMLNS
            ET.SubElement(shipment, "Account").text = self.whistl_account

            delivery_address = ET.SubElement(shipment, "DeliveryAddress")
            ET.SubElement(
                delivery_address, "ContactName"
            ).text = picking.partner_id.name
            if picking.partner_id.parent_id:
                ET.SubElement(
                    delivery_address, "CompanyName"
                ).text = picking.partner_id.parent_id.name
            if picking.partner_id.email:
                ET.SubElement(delivery_address, "Email").text = picking.partner_id.email
            ET.SubElement(delivery_address, "Phone").text = (
                picking.partner_id.phone or "000000"
            )
            ET.SubElement(delivery_address, "Address1").text = picking.partner_id.street
            if picking.partner_id.street2:
                ET.SubElement(
                    delivery_address, "Address2"
                ).text = picking.partner_id.street2
            ET.SubElement(delivery_address, "City").text = picking.partner_id.city
            ET.SubElement(
                delivery_address, "Area"
            ).text = picking.partner_id.state_id.name
            ET.SubElement(delivery_address, "Postcode").text = picking.partner_id.zip
            ET.SubElement(
                delivery_address, "Country"
            ).text = picking.partner_id.country_id.code

            ET.SubElement(shipment, "Reference1").text = picking.name
            ET.SubElement(shipment, "Reference2").text = order.name
            ET.SubElement(
                shipment, "ContentsDescription"
            ).text = "Clothing/Protective Clothing"

            packages = ET.SubElement(shipment, "Packages")
            for package in picking.package_ids:
                product_list = []
                package_total_value = 0
                package_total_weight = 0
                for line in package.quant_ids:
                    product_list.append(
                        {
                            "Description": line.product_id.name,
                            "Sku": line.product_id.default_code,
                            "OriginCountry": picking.location_id.company_id.country_id.code
                            or "GB",
                            "Quantity": str(int(line.quantity)),
                            "Value": str(line.product_id.lst_price * line.quantity),
                            "Weight": str(line.product_id.weight * line.quantity),
                            "HsCode": line.product_id.hs_code or "",
                        }
                    )
                    package_total_value += line.product_id.lst_price * line.quantity
                    package_total_weight += line.product_id.weight * line.quantity

                package_element = ET.SubElement(packages, "Package")
                shipping_weight = package.shipping_weight
                length = package.package_type_id.packaging_length
                width = package.package_type_id.width
                height = package.package_type_id.height
                dimensions = ET.SubElement(package_element, "Dimensions")
                ET.SubElement(dimensions, "Length").text = str(length or 10)
                ET.SubElement(dimensions, "Width").text = str(width or 10)
                ET.SubElement(dimensions, "Height").text = str(height or 10)
                if shipping_weight:
                    ET.SubElement(package_element, "Weight").text = str(
                        package.shipping_weight
                    )
                else:
                    ET.SubElement(package_element, "Weight").text = str(
                        package_total_weight or 0.01
                    )
                package_value = ET.SubElement(package_element, "Value")
                package_value.text = str(package_total_value)
                package_value.attrib["Currency"] = order.currency_id.name
                ET.SubElement(
                    package_element, "Contents"
                ).text = "Clothing/Protective Clothing"
                package_customs_declaration = ET.SubElement(
                    package_element, "PackageCustomsDeclaration"
                )
                ET.SubElement(package_customs_declaration, "Weight").text = str(
                    package_total_weight or 0.01
                )
                package_customs_value = ET.SubElement(
                    package_customs_declaration, "Value"
                )
                package_customs_value.text = str(package_total_value)
                package_customs_value.attrib["Currency"] = order.currency_id.name
                item_declarations = ET.SubElement(
                    package_element, "ItemLevelDeclarations"
                )
                for product in product_list:
                    item_declaration = ET.SubElement(
                        item_declarations, "ItemLevelDeclaration"
                    )
                    ET.SubElement(
                        item_declaration, "ProductType"
                    ).text = "Clothing/Protective Clothing"
                    ET.SubElement(
                        item_declaration, "ProductDescription"
                    ).text = product.get("Description")
                    ET.SubElement(item_declaration, "ProductSku").text = product.get(
                        "Sku"
                    )
                    ET.SubElement(
                        item_declaration, "ProductCountryOfOrigin"
                    ).text = product.get("OriginCountry")
                    ET.SubElement(item_declaration, "ProductQuantity").text = str(
                        product.get("Quantity")
                    )
                    ET.SubElement(item_declaration, "ProductValue").text = str(
                        product.get("Value")
                    )
                    ET.SubElement(item_declaration, "ProductWeight").text = str(
                        product.get("Weight")
                    )
                    ET.SubElement(
                        item_declaration, "ProductHarmonisedCode"
                    ).text = product.get("HsCode")

            # Get Preferred Service
            preference_list_id = self.whistl_service_preference_list
            if not preference_list_id:
                raise ValidationError(
                    _("No Whistl Service Preference List ID has been configured")
                )
            request_url = self._get_whistl_url(
                "Service/ServiceUsingServicePreference",
                {"ServicePreferenceListId": self.whistl_service_preference_list},
            )
            response = requests.post(
                request_url,
                headers=self._get_whistl_headers(),
                data=ET.tostring(shipment, xml_declaration=True, encoding="utf-8"),
                timeout=20,
            )

            if not response.status_code == 200:
                message = ET.fromstring(response.content).find("Message").text
                raise ValidationError(
                    _(
                        "Whistl API Error Requesting Service: {status_code}\n{message}"
                    ).format(status_code=response.status_code, message=message)
                )

            service_xml = ET.fromstring(response.content)
            ns = {"ns0": WHISLT_XMLNS}

            service_ids = service_xml.find("ns0:ServiceIds", ns)
            service_id = service_ids.find("ns0:ServiceId", ns)
            service_info_xml = ET.SubElement(shipment, "ServiceInfo")
            ET.SubElement(service_info_xml, "ServiceId").text = service_id.text

            # Send to Whistl
            request_url = self._get_whistl_url(
                "Shipment",
                {
                    "RequestedLabelFormat": self.whistl_label_format,
                    "RequestedLabelSize": self.whistl_label_size,
                },
            )
            response = requests.post(
                request_url,
                headers=self._get_whistl_headers(),
                data=ET.tostring(shipment, xml_declaration=True, encoding="utf-8"),
                timeout=20,
            )
            if not response.status_code == 200:
                message = ET.fromstring(response.content).find("Message").text
                raise ValidationError(
                    _(
                        "Whistl API Error Sending Shipment: {status_code}}\n{message}"
                    ).format(status_code=response.status_code, message=message)
                )

            shipment_xml = ET.fromstring(response.content)

            tracking = shipment_xml.find("CourierTrackingNumber").text

            attachments_list = []
            if shipment_xml.find("LabelData"):
                for label in shipment_xml.find("LabelData"):
                    attachments_list.append(
                        (
                            "Whistl_%s.%s"
                            % (
                                str(tracking),
                                self.whistl_label_format.replace("2", ""),
                            ),
                            binascii.a2b_base64(str(label.text)),
                        )
                    )

            picking.message_post(
                body=_(
                    "Shipment sent to Whistl<br/>"
                    "Carrier: %(carrier_name)s<br/>"
                    "Tracking Number: %(tracking_ref)s<br/>"
                )
                % {
                    "carrier_name": shipment.get("Carrier"),
                    "tracking_ref": tracking,
                },
                attachments=attachments_list,
            )

            picking.write(
                {
                    "carrier_consignment_ref": picking.name,
                    "whistl_carrier": shipment_xml.get("ServiceProviderName"),
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
        raise NotImplementedError("We didn't get to this bit yet")
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
        raise NotImplementedError("We didn't get to this bit yet")
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
        raise NotImplementedError("We didn't get to this bit yet")
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
        raise NotImplementedError("We didn't get to this bit yet")
        if picking.delivery_state in ["customer_delivered", "warehouse_delivered"]:
            return False
        return fields.datetime.now() + datetime.timedelta(hours=4)

    def whistl_get_tracking_link(self, picking):
        raise NotImplementedError("We didn't get to this bit yet")
        return picking.whistl_tracking_url

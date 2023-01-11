from odoo import fields, models
from odoo.tools import float_round


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    def _commingled_bom_line(self):
        self.ensure_one()
        commingled_boms_dict = self.env["mrp.bom"]._bom_find(
            self.product_id,
            bom_type="commingled",
        )

        # we always skip the commingled lines as we'll do these ourselves within
        # our super()'d explode
        if commingled_boms_dict.get(self.product_id):
            return True

    def _skip_bom_line(self, product):
        if self._commingled_bom_line():
            return True

        return super()._skip_bom_line(product)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    type = fields.Selection(
        selection_add=[("commingled", "Commingled")],
        ondelete={
            "commingled": "cascade",
        },
    )

    def _commingled_select_line(self, location_id=False):
        self.ensure_one()

        # TODO: FIX ME
        return self.bom_line_ids[0]

    def action_test_explode(self):
        self.ensure_one()
        self.explode(self.product_id, 1)

    def explode(self, product, quantity, picking_type=False):
        boms_done, lines_done = super().explode(product, quantity, picking_type)

        bom_lines_product_ids = self.env["product.product"]

        for bom_id, _bom_dict in boms_done:
            bom_lines_product_ids |= bom_id.mapped("bom_line_ids.product_id")

        boms_dict = self._bom_find(
            bom_lines_product_ids,
        )

        if not boms_dict:
            return boms_done, lines_done

        todo = []

        for bom_id, bom_dict in boms_done:
            for bom_line in bom_id.bom_line_ids:
                commingled_bom_id = boms_dict.get(bom_line.product_id)
                if not commingled_bom_id or commingled_bom_id.type != "commingled":
                    continue

                line_quantity = bom_dict.get("qty") * bom_line.product_qty

                converted_line_quantity = bom_line.product_uom_id._compute_quantity(
                    line_quantity / bom_id.product_qty, bom_id.product_uom_id
                )

                todo.append((converted_line_quantity, bom_line))

        while todo:
            quantity, current_line = todo[0]
            todo = todo[1:]

            if current_line.product_id not in boms_dict:
                boms_dict.update(self._bom_find(current_line.product_id))

            rounding = current_line.product_uom_id.rounding
            line_quantity = float_round(
                quantity, precision_rounding=rounding, rounding_method="UP"
            )

            bom_id = boms_dict.get(current_line.product_id, self.env["mrp.bom"])

            if bom_id.type == "commingled":
                selected_line = bom_id._commingled_select_line()
                todo.append((quantity, selected_line))
                continue

            elif bom_id.type == "phantom":
                phantom_done, phantom_lines_done = bom_id.explode(
                    current_line.product_id,
                    line_quantity,
                )
                # FIXME: the lines_done and probably boms_done may the values
                # updated? Verify how this works where depth > 1
                boms_done += phantom_done
                lines_done += phantom_lines_done
                continue

            elif not bom_id:
                # We round up here because the user expects that if he has to consume a little more, the whole UOM unit
                # should be consumed.
                lines_done.append(
                    (
                        current_line,
                        {
                            "qty": line_quantity,
                            "product": current_line.product_id,
                            "original_qty": quantity,
                            "parent_line": current_line,
                        },
                    )
                )

                boms_done.append(
                    (
                        bom_id,
                        {
                            "qty": line_quantity,
                            "product": current_line.bom_id.product_id,  # FIXME
                            "original_qty": quantity,
                            "parent_line": current_line,
                        },
                    )
                )

                continue

        __import__("wdb").set_trace()

        return boms_done, lines_done

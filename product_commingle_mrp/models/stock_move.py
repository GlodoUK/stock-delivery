import itertools

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _skip_action_commingled(self):
        res = super()._skip_action_commingled()

        return res or (
            self.production_id and self.production_id.product_id == self.product_id
        )

    def _action_commingled(self):
        before_commingling = set(self.ids)
        # support phantom kits within commingled
        moves = super()._action_commingled()
        if before_commingling != set(moves.ids):
            moves = moves.action_explode()
        return moves

    def action_explode(self):
        before_explosion = set(self.ids)
        moves = super().action_explode()
        if before_explosion != set(moves.ids) and moves.filtered(
            lambda m: not m._skip_action_commingled()
        ):
            # support commingled within phantom kits
            moves = moves._action_commingled()
        return moves

    def _compute_commingled_quantities(self, product_id, qty, filters):
        if not self.filtered(lambda m: m.bom_line_id):
            return super()._compute_commingled_quantities(product_id, filters)

        done = 0

        moves = self.sorted(lambda m: (m.product_commingled_id, m.bom_line_id.bom_id))
        for (commingled_id, bom_id), g in itertools.groupby(
            moves, key=lambda m: (m.product_commingled_id, m.bom_line_id.bom_id)
        ):
            g = list(g)
            todo = self.env["stock.move"]
            for m in g:
                todo |= m

            if bom_id:
                done += todo._compute_kit_quantities(
                    bom_id,
                    filters,
                )
                continue

            if commingled_id:
                done += todo._compute_commingled_quantities(
                    commingled_id.parent_product_id, filters
                )
                continue

            raise NotImplementedError()

        return done

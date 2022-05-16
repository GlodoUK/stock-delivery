{
    "name": "Sale Order Alternative Products",
    "summary": """
        Module to propose alternative products at the
         time of Sale Order Line  product selection.
    """,
    "author": "Glo Networks",
    "website": "https://github.com/OCA/stock-delivery",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/
    # odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Base",
    "version": "15.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "sale",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order.xml",
        "wizards/wizard_suggest_alternatives.xml",
        "views/product.xml",
    ],
    "license": "AGPL-3",
}

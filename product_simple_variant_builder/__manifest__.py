{
    "name": "product_simple_variant_builder",
    "summary": """
        Simple wizard to build dynamic variants from a product template""",
    "author": "Glo Networks",
    "website": "https://glo.systems",
    "category": "Inventory",
    "version": "17.0.1.0.0",
    "depends": ["product", "product_variant_configurator"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/wizard_simple_create_variant.xml",
        "views/product_template_view.xml",
    ],
    "demo": [],
    "license": "Other proprietary",
}

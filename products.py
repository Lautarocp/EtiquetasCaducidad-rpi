"""Presets de productos por defecto (semilla inicial).

Cada preset define una caducidad como valor + unidad:
  - unit "dias"  → se suman N días a la fecha de realización
  - unit "meses" → se suman N meses (el calendario se ajusta solo)

El usuario puede crear/editar/borrar presets desde el frontend; esos cambios se
guardan en products.json (ver app.py). Esta lista solo se usa la primera vez,
cuando todavía no existe products.json.
"""

DEFAULT_PRODUCTS = [
    {"name": "Tortilla",          "value": 3, "unit": "dias"},
    {"name": "Ensalada",          "value": 2, "unit": "dias"},
    {"name": "Carne cocinada",    "value": 3, "unit": "dias"},
    {"name": "Pollo cocinado",    "value": 3, "unit": "dias"},
    {"name": "Pescado cocinado",  "value": 2, "unit": "dias"},
    {"name": "Sopa / Caldo",      "value": 3, "unit": "dias"},
    {"name": "Arroz cocinado",    "value": 3, "unit": "dias"},
    {"name": "Pasta cocinada",    "value": 3, "unit": "dias"},
    {"name": "Patatas cocidas",   "value": 3, "unit": "dias"},
    {"name": "Verduras cocidas",  "value": 3, "unit": "dias"},
]

# Compatibilidad: algunos módulos antiguos importaban PRODUCTS.
PRODUCTS = DEFAULT_PRODUCTS

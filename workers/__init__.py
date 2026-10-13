"""Background workers for CloudCostLens.

Each worker is an independently runnable entry point. They share ``core/`` services and
coordinate through DB-backed jobs. Workers must never import Web/API concerns.
"""

__version__ = "0.1.0"
"""The role catalog: every entry-level role AnalystOS intends to offer, and the
rules that decide when one may be hired (Slice 108). See validate.py."""

from analystos.catalog.validate import CATALOG_PATH, FORMAT, load_catalog, summary, validate_catalog

__all__ = ["CATALOG_PATH", "FORMAT", "load_catalog", "summary", "validate_catalog"]

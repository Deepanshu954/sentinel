"""
Sentinel Dataset Adapter Registry.

Maps adapter names (used in dataset_manifest.json) to concrete adapter classes.
If a source config has no 'adapter' key, the GenericCSVAdapter is used.
"""

from .base import BaseAdapter, GenericCSVAdapter, _empty
from .wikimedia import WikimediaAdapter
from .azure import AzureFunctionsAdapter, AzureVMAdapter
from .google_cluster import GoogleClusterAdapter
from .alibaba import AlibabaClusterAdapter
from .apache_access import ApacheAccessLogAdapter

# ── Adapter registry ────────────────────────────────────────────────────────
# Keys match the 'adapter' field in dataset_manifest.json source entries.
ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    "wikimedia": WikimediaAdapter,
    "wikimedia_pageviews": WikimediaAdapter,
    "azure_functions": AzureFunctionsAdapter,
    "azure_vm": AzureVMAdapter,
    "google_cluster": GoogleClusterAdapter,
    "google_cluster_2019": GoogleClusterAdapter,
    "alibaba": AlibabaClusterAdapter,
    "alibaba_cluster": AlibabaClusterAdapter,
    "apache_access": ApacheAccessLogAdapter,
    "nasa_http": ApacheAccessLogAdapter,
    "apache_log": ApacheAccessLogAdapter,
    "generic": GenericCSVAdapter,
}


def get_adapter(source_config: dict) -> BaseAdapter:
    """Resolve the correct adapter for a source config entry.

    Looks up the 'adapter' key in source_config. If missing, falls back to
    GenericCSVAdapter.
    """
    adapter_name = source_config.get("adapter", "generic")
    adapter_cls = ADAPTER_REGISTRY.get(adapter_name, GenericCSVAdapter)
    return adapter_cls(source_config)


__all__ = [
    "BaseAdapter",
    "GenericCSVAdapter",
    "WikimediaAdapter",
    "AzureFunctionsAdapter",
    "AzureVMAdapter",
    "GoogleClusterAdapter",
    "AlibabaClusterAdapter",
    "ApacheAccessLogAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
    "_empty",
]

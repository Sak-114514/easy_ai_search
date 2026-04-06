from importlib import import_module

search_module = import_module(".search", __name__)
search = search_module.search

__all__ = ["search", "search_module"]

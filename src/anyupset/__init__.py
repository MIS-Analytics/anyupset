"""Interactive UpSet plots for marimo and Jupyter notebooks."""

from importlib.metadata import PackageNotFoundError, version

from ._upset import UpSet

try:
    __version__ = version("anyupset")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"

__all__ = ["UpSet", "__version__"]

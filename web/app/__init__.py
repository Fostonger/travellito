# Compatibility shim for Python 3.12 where stdlib 'distutils' was removed
# Some third-party libraries (e.g. pydantic < 2.6, aiogram < 3.4) still do
# `import distutils.util`.  Instead of pinning older Python we alias the
# vendored copy that ships with `setuptools`.

from __future__ import annotations

import importlib
import sys

try:
    import distutils  # noqa: F401 – attempt stdlib import first
except ModuleNotFoundError:  # pragma: no cover
    # Fall back to the shim provided by setuptools.
    shim = importlib.import_module("setuptools._distutils")
    sys.modules["distutils"] = shim
    sys.modules.setdefault("distutils.util", importlib.import_module("setuptools._distutils.util"))

# Keep the module import side-effect only.  Avoid polluting public API.
__all__: list[str] = []

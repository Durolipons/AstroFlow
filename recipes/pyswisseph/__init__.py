"""p4a recipe for pyswisseph.

pyswisseph bundles pre-generated C sources (pyswisseph.c plus the Swiss
Ephemeris C library and an internal sqlite3), so no Cython step is needed.
:class:`CompiledComponentsPythonRecipe`'s default build already runs
``hostpython setup.py build_ext -v`` with the correct cross-compile
environment, which is exactly what this module needs.
"""

import os

from pythonforandroid.logger import info as logger
from pythonforandroid.recipe import CompiledComponentsPythonRecipe


class PySwissephRecipe(CompiledComponentsPythonRecipe):
    """Python wrapper for the Swiss Ephemeris C library."""

    version = "2.10.3.2"
    url = (
        "https://files.pythonhosted.org/packages/source/p/"
        "pyswisseph/pyswisseph-{version}.tar.gz"
    )
    depends = ["setuptools"]
    site_packages_name = "swisseph"

    def build_arch(self, arch):
        """Patch setup.py before the standard build.

        With ``sqlite3_detection = True`` (the default), setup.py asks the
        *host* system for libsqlite3 via pkg-config.  On the CI runner the
        host has libsqlite3-dev, so setup.py thinks sqlite3 is available and
        compiles against the host header -- but the Android NDK sysroot has
        no sqlite3.h, so the cross-compile fails with::

            swephelp/swhatlas.c:26:10: fatal error: 'sqlite3.h' file not found

        pyswisseph bundles a complete internal sqlite3 amalgamation under
        ``swephelp/sqlite3/``; setting ``sqlite3_detection = False`` makes
        setup.py compile that amalgamation with the NDK toolchain instead,
        which is fully self-contained.
        """
        setup_py = os.path.join(self.get_build_dir(arch.arch), "setup.py")
        with open(setup_py, "r", encoding="utf-8") as f:
            src = f.read()
        if "sqlite3_detection = True" in src:
            src = src.replace(
                "sqlite3_detection = True", "sqlite3_detection = False", 1
            )
            with open(setup_py, "w", encoding="utf-8") as f:
                f.write(src)
            logger.info("pyswisseph: forced bundled internal sqlite3")
        super().build_arch(arch)


recipe = PySwissephRecipe()



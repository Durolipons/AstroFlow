"""p4a recipe for pyswisseph.

pyswisseph bundles pre-generated C sources (pyswisseph.c plus the Swiss
Ephemeris C library and an internal sqlite3), so no Cython step is needed.
:class:`CompiledComponentsPythonRecipe`'s default build already runs
``hostpython setup.py build_ext -v`` with the correct cross-compile
environment, which is exactly what this module needs.
"""

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


recipe = PySwissephRecipe()



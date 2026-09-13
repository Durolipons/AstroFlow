from pythonforandroid.recipe import CompiledComponentsPythonRecipe


class PySwissephRecipe(CompiledComponentsPythonRecipe):
    """Recipe for pyswisseph — Python wrapper for the Swiss Ephemeris C library.

    pyswisseph bundles the Swiss Ephemeris C source in its source distribution,
    so we use CompiledComponentsPythonRecipe which calls ``setup.py build_ext``
    with the correct Android NDK cross-compiler.
    """

    version = "2.10.3.2"
    url = (
        "https://files.pythonhosted.org/packages/source/p/"
        "pyswisseph/pyswisseph-{version}.tar.gz"
    )
    depends = ["setuptools"]
    site_packages_name = "swisseph"


recipe = PySwissephRecipe()



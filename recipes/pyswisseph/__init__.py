import os
import sh
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.logger import shprint, info, warning
from pythonforandroid.util import current_directory, ensure_dir


class PySwissephRecipe(CompiledComponentsPythonRecipe):
    """Recipe for pyswisseph — Python wrapper for the Swiss Ephemeris C library."""

    version = "2.10.3.2"
    url = (
        "https://files.pythonhosted.org/packages/source/p/"
        "pyswisseph/pyswisseph-{version}.tar.gz"
    )
    depends = ["setuptools"]
    site_packages_name = "swisseph"

    def build_compiled_components(self, arch, **kwargs):
        info("PySwisseph: building C extension for %s", arch)
        env = self.get_recipe_env(arch)
        build_dir = self.get_build_dir(arch)

        with current_directory(build_dir):
            try:
                shprint(
                    sh.Command(env["PYTHON"]), "setup.py",
                    "build_ext", "--inplace",
                    _env=env,
                )
            except sh.ErrorReturnCode as exc:
                warning(
                    "PySwisseph: build_ext failed (exit %s): %s",
                    exc.exit_code, exc,
                )
                raise

        super().build_compiled_components(arch, **kwargs)


recipe = PySwissephRecipe()



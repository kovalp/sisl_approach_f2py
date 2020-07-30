#!/usr/bin/env python3

import sys
import subprocess
import multiprocessing
import os
import os.path as osp
import argparse

# pkg_resources are part of setuptools
import pkg_resources

# We should *always* import setuptools prior to Cython/distutils
import setuptools


min_version ={
    "numpy": "1.13",
}

macros = []
import Cython
# if available we can cythonize stuff

_CYTHON_VERSION = Cython.__version__
from Cython.Build import cythonize
from Cython.Distutils.old_build_ext import old_build_ext as cython_build_ext
directives = {"linetrace": False, "language_level": 3}


# Although setuptools is not shipped with the standard library, I think
# this is ok since it should get installed pretty easily.
from setuptools import Command, Extension
from setuptools import find_packages

# Patch to allow fortran sources in setup
# build_ext requires numpy setup
# Also for extending build schemes we require build_ext from numpy.distutils
from distutils.command.sdist import sdist
from numpy.distutils.command.build_ext import build_ext as numpy_build_ext
from numpy.distutils.core import Extension as FortranExtension
from numpy.distutils.core import setup

# Custom command classes
cmdclass = {}

# Now create the build extensions
class CythonCommand(cython_build_ext):
    """
    Custom distutils command subclassed from Cython.Distutils.build_ext
    to compile pyx->c, and stop there. All this does is override the
    C-compile method build_extension() with a no-op.
    """

    def build_extension(self, ext):
        pass

cmdclass["cython"] = CythonCommand
suffix = ".pyx"


# Retrieve the compiler information
from numpy.distutils.system_info import get_info
# use flags defined in numpy
all_info = get_info('ALL')

class EnsureSource_sdist(sdist):
    """Ensure Cython has runned on all pyx files (i.e. we need c sources)."""

    def initialize_options(self):
        super().initialize_options()

    def run(self):
        if "cython" in cmdclass:
            self.run_command("cython")
        else:
            pyx_files = [(_pyxfiles, "c"), (self._cpp_pyxfiles, "cpp")]

            for pyxfiles, extension in [(_pyxfiles, "c")]:
                for pyxfile in pyxfiles:
                    sourcefile = pyxfile[:-3] + extension
                    msg = (f"{extension}-source file '{sourcefile}' not found.\n"
                           "Run 'setup.py cython' before sdist."
                    )
                    assert os.path.isfile(sourcefile), msg
        super().run()

cmdclass["sdist"] = EnsureSource_sdist

macros.append(("NPY_NO_DEPRECATED_API", "0"))
macros.append(("CYTHON_NO_PYINIT_EXPORT", "1"))

extensions = []
numpy_incl = pkg_resources.resource_filename("numpy", "core/include")


ext_cython = {
    "package1._csources": {
        "pyxfile": "package1/_cstuff.pyx",
    },
}

for name, data in ext_cython.items():
    sources = [data["pyxfile"]] + data.get("sources", [])

    ext = Extension(name,
        sources=sources,
        depends=data.get("depends", []),
        include_dirs=data.get("include", None),
        language=data.get("language", "c"),
        define_macros=macros + data.get("macros", []),
    )

    extensions.append(ext)


# Specific Fortran extensions
ext_fortran = {
    "package1._sources": {
        "sources": ["package1/_src/hello_world.f90"]
    },
}

for name, data in ext_fortran.items():
    ext = FortranExtension(name,
        sources=data.get("sources"),
        depends=data.get("depends", []),
        include_dirs=data.get("include", None),
        define_macros=macros + data.get("macros", []),
    )

    extensions.append(ext)


class EnsureBuildExt(numpy_build_ext):
    """
    Override build-ext to check whether compilable sources are present
    This merely pretty-prints a better error message.

    Note we require build_ext to inherit from numpy.distutils since
    we need fortran sources.
    """

    def check_cython_extensions(self, extensions):
        for ext in extensions:
            for src in ext.sources:
                if not os.path.exists(src):
                    print(f"{ext.name}: -> {ext.sources}")
                    raise Exception(
                        f"""Cython-generated file '{src}' not found.
                        Cython is required to compile sisl from a development branch.
                        Please install Cython or download a release package of sisl.
                        """)

    def build_extensions(self):
        self.check_cython_extensions(self.extensions)
        numpy_build_ext.build_extensions(self)

    
# Override build_ext command (typically called by setuptools)
cmdclass["build_ext"] = EnsureBuildExt


# The install_requires should also be the
# requirements for the actual running of sisl
setuptools_kwargs = {
    "install_requires": [
        "setuptools",
        "numpy >= " + min_version["numpy"],
    ],
    "setup_requires": [
        "numpy >= " + min_version["numpy"],
    ],
}



# Run cythonizer
def cythonizer(extensions, *args, **kwargs):
    """
    Skip cythonizer (regardless) when running

    * clean
    * sdist

    Otherwise if `cython` is True, we will cythonize sources.
    """
    if "clean" in sys.argv or "sdist" in sys.argv:
        # https://github.com/cython/cython/issues/1495
        return extensions

    # Retrieve numpy include directories for headesr
    numpy_incl = pkg_resources.resource_filename("numpy", "core/include")

    # Allow parallel flags to be used while cythonizing
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", type=int, dest="parallel")
    parser.add_argument("--parallel", type=int, dest="parallel")
    parsed, _ = parser.parse_known_args()

    if parsed.parallel:
        kwargs["nthreads"] = max(0, parsed.parallel)

    # Extract Cython extensions
    # And also other extensions to store them
    other_extensions = []
    cython_extensions = []
    for ext in extensions:
        if ext.name in ext_cython:
            cython_extensions.append(ext)
        else:
            other_extensions.append(ext)

    return other_extensions + cythonize(cython_extensions, *args, quiet=False, **kwargs)


metadata = dict(
    name="package1",
    maintainer="foo",
    description="bar",
    long_description="snthaoe",
    long_description_content_type="text/markdown",
    packages=find_packages(include=["package1", "package1.*"]),
    ext_modules=cythonizer(extensions, compiler_directives=directives),
    cmdclass=cmdclass,
    zip_safe=False,
    **setuptools_kwargs
)


if __name__ == "__main__":

    metadata["version"] = "1.0"

    # Freeze to support parallel compilation when using spawn instead of fork
    multiprocessing.freeze_support()
    setup(**metadata)

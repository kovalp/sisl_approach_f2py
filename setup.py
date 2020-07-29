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

suffix = ".c"


# Retrieve the compiler information
from numpy.distutils.system_info import get_info
# use flags defined in numpy
all_info = get_info('ALL')

cmdclass["sdist"] = sdist

macros = []

extensions = []
# Specific Fortran extensions
ext_fortran = {
    "package1._sources": {
        "sources": [f"package1/_src/{f}" for f in
                    ("hello_world.f90")
        ],
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


# Override build_ext command (typically called by setuptools)
cmdclass["build_ext"] = numpy_build_ext


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



metadata = dict(
    name="package1",
    maintainer="foo",
    description="bar",
    long_description="snthaoe",
    long_description_content_type="text/markdown",
    packages=find_packages(include=["package1", "package1.*"]),
    ext_modules=extensions,
    cmdclass=cmdclass,
    **setuptools_kwargs
)


if __name__ == "__main__":

    metadata["version"] = "1.0"

    # Freeze to support parallel compilation when using spawn instead of fork
    multiprocessing.freeze_support()
    setup(**metadata)

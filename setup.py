"""Build the C parser extension. Metadata lives in pyproject.toml."""

from __future__ import annotations

import sys

from setuptools import Extension, setup

if sys.platform == "win32":
    extra_compile_args = ["/O2"]
else:
    extra_compile_args = ["-O3", "-std=c11"]

setup(
    ext_modules=[
        Extension(
            "clear_outside_apy._parser",
            sources=["src/clear_outside_apy/_parser.c"],
            extra_compile_args=extra_compile_args,
        )
    ]
)

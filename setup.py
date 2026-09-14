"""Build the C parser extension. Metadata lives in pyproject.toml."""

from __future__ import annotations

import platform
import sys

from setuptools import Extension, setup

extra_link_args: list[str] = []
if sys.platform == "win32":
    extra_compile_args = ["/O2"]
else:
    extra_compile_args = ["-O3", "-std=c11"]
    # Baseline x86-64 so auditwheel can emit a manylinux tag instead of
    # linux_x86_64 (PyPI rejects the latter).
    if platform.machine().lower() in {"x86_64", "amd64"}:
        extra_compile_args.append("-march=x86-64")
    # Arch/Python LDFLAGS enable DT_RELR (GLIBC 2.38). Disable it so the
    # wheel can be tagged for older glibc.
    extra_link_args = ["-Wl,-z,nopack-relative-relocs"]

setup(
    ext_modules=[
        Extension(
            "clear_outside_apy._parser",
            sources=["src/clear_outside_apy/_parser.c"],
            extra_compile_args=extra_compile_args,
            extra_link_args=extra_link_args,
        )
    ]
)

"""
Minimal pkg_resources shim for Python 3.12+ compatibility.

Python 3.12 removed pkg_resources from setuptools.
The ccp (Petrobras) library imports 'from pkg_resources import get_distribution'.
This shim provides that function using importlib.metadata (stdlib).
"""

from importlib.metadata import distribution, PackageNotFoundError


def get_distribution(name: str):
    try:
        return distribution(name)
    except PackageNotFoundError:
        return None

# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Smoke checks for the installed APRS package."""

import unittest
from importlib import import_module
from importlib.metadata import version


class PackageTests(unittest.TestCase):
    def test_namespace_import(self) -> None:
        module = import_module("hamkit.aprs")
        self.assertEqual(module.__name__, "hamkit.aprs")

    def test_distribution_version(self) -> None:
        about = import_module("hamkit.aprs.__about__")
        self.assertEqual(version("hamkit-aprs"), about.__version__)

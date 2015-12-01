# This file is part of the aeat_303 module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class Aeat303TestCase(ModuleTestCase):
    'Test Aeat 303 module'
    module = 'aeat_303'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        Aeat303TestCase))
    return suite
#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends


class Aeat303TestCase(unittest.TestCase):
    'Test AEAT 303 module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('aeat_303')

    def test0005views(self):
        'Test views'
        test_view('aeat_303')

    def test0006depends(self):
        'Test depends'
        test_depends()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            Aeat303TestCase))
    return suite

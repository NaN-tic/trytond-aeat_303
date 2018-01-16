# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
try:
    from trytond.modules.aeat_303.tests.test_aeat_303 import suite
except ImportError:
    from .test_aeat_303 import suite

__all__ = ['suite']

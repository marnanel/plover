# Copyright (c) 2017 Thomas Thurman
# See LICENSE.txt for details.

import unittest

EXPECTED = {
   ('TKPWHREPB',): 'glen',
   ('A',): 'a',
   ('TK*EB', 'TK*EB', 'R-R'):
        # no, I don't know why; it was in the sample dct
        '"Debbie \'Do Anything for Hillary\' Wasserman Schultz"',
   ('TKEUGZ/AER',):
        'dictionary',
   ('HAOER',): 'here',
   ('SEZ',): 'says',
   ('S',): 'is',
   # XXX These are wrong; fix the (prefix)(suffix) thing
   ('SKW-FRPBLGTS',): '<suffix>{A}And',
   ('STKPWHRAEPBG',): '<suffix>{Q}What, if anything,<prefix>',
   ('SPHAUL',): 'small',
}

from plover.dictionary.jet_dict import JetDictionary

class TestCase(unittest.TestCase):

    def test_load_dictionary(self):

        filename = 'test/jet-test.dct'
        d = JetDictionary.load(filename)
        self.assertEqual(dict(d.items()), EXPECTED)

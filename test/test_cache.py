# -*- coding: utf-8 -*-
# Copyright (c) 2017 Thomas Thurman
# See LICENSE.txt for details.

"""Unit tests for the dictionary cache."""

import unittest

from plover.dictcache import CollectionCache

class CollectionCacheTestCase(unittest.TestCase):

    def test_create_cache(self):

        # XXX temp filename!
        c = CollectionCache('/tmp/test.sqlite3')


# -*- coding: utf-8 -*-
# Copyright (c) 2017 Thomas Thurman
# See LICENSE.txt for details.

"""Unit tests for the dictionary cache."""

import unittest
import tempfile
import os
import sys

from plover.dictcache import CollectionCache

class CollectionCacheForTesting():

    def __enter__(self):
        self.dirname = tempfile.mkdtemp(suffix='dictcache')
        self.dbname = os.path.join(self.dirname, "test.sqlite3")
        self.db = CollectionCache(self.dbname)
        return self.db

    def __exit__(self, *args):
        del self.db
        os.unlink(self.dbname)
        os.rmdir(self.dirname)

class CollectionCacheTestCase(unittest.TestCase):

    def test_length(self):

        with CollectionCacheForTesting() as c:
            db = c.get_dictionary('red', 1)

            db.update([
                    ('FRED', 'fred'),
                    ('JIM', 'jim'),
                    ('SHEILA', 'sheila')])

            self.assertEqual(len(db), 3)

    def test_longest_key_length(self):

        with CollectionCacheForTesting() as c:
            db = c.get_dictionary('red', 1)

            self.assertEqual(db.longest_key_length(), 0)

            db.update([
                    ('FRED', 'fred'),
                    ('JIM', 'jim'),
                    ('SHEI/LA', 'sheila')])

            self.assertEqual(db.longest_key_length(), 2)

            db.update([
                    ('SPING', 'sping'),
                    ('SPONG', 'spong')])
 
            self.assertEqual(db.longest_key_length(), 2)

            db.update([
                    ('WOM/BAT', 'wombat'),
                    ('TAR/ANT/UL/A', 'bigspider')])
 
            self.assertEqual(db.longest_key_length(), 4)

    def test_iteration(self):

        with CollectionCacheForTesting() as c:
            db = c.get_dictionary('red', 1)

            strokes = [
                    ('FRED', 'fred'),
                    ('JIM', 'jim'),
                    ('SHEILA', 'sheila'),
                    ]

            db.update(strokes)

            for (x, y) in zip(strokes, db):
                self.assertEqual(x, y)



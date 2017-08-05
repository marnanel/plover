import sys
import os
import sqlite3
from plover.steno_dictionary import StenoDictionary

class _Cache(object):

    def __init__(self):
        self._db = None
        self._cursor = None

    def _execute(self, command, *args,
            do_commit = True):

        if self._cursor is None:
            self._cursor = self._db.cursor()

        sys.stderr.write("%s\n%s\n" % (command, str(args)))
        result = self._cursor.execute(command, args)

        if do_commit:
            self._db.commit()
            self._cursor = None

        return result

    def _commit(self):
        if self._cursor is not None:
            self._db.commit()
            self._cursor = None

class DictionaryCache(_Cache):
    def __init__(self,
            collection_cache,
            db,
            primary_key,
            should_be_filled):

        _Cache.__init__(self)

        self._parent = collection_cache
        self._db = db
        self._primary_key = primary_key
        self._should_be_filled = should_be_filled

    def should_be_filled(self):
        return self._should_be_filled

    def __len__(self):
        result = self._execute("""SELECT
            COUNT(*)
            FROM translations
            WHERE dictionary=?;""",
            self._primary_key)

        return result.fetchone()[0]

    def longest_key_length(self):

        # The length of a key is the number of slashes, plus one.
        # We can find the number of slashes by taking the same string
        # with all the slashes removed, and subtracting its length
        # from the length of the original key. It looks contrived,
        # but it lets us do the whole operation in sqlite.

        select = self._execute("""SELECT
            MAX(LENGTH(stroke)-LENGTH(REPLACE(stroke, '/', '')))
            FROM translations
            WHERE dictionary=?;""",
            self._primary_key)

        result = select.fetchone()[0]

        if result is None:
            return 0
        else:
            # Add one: no slashes means one stroke, etc.
            return result+1

    def __iter__(self):
        select = self._execute("""SELECT
            stroke, translation
            FROM translations
            WHERE dictionary=?;""",
            self._primary_key)

        result = select.fetchall()

        for (k,v) in result:
            yield (k,v)

    def __getitem__(self, key):
        result = self.get(key)

        if result is None:
            raise KeyError()

        return result

    def clear(self):
        self._execute("""DELETE
            FROM translations
            WHERE dictionary=?""",
            self._primary_key)

    def update(self, *args, **kwargs):
        for iterable in args + (kwargs,):
            if isinstance(iterable, (dict, StenoDictionary)):
                iterable = iterable.items()

            for stroke, translation in iterable:
                # XXX there is almost certainly a better way
                # XXX to do bulk inserts
                self.__setitem__(stroke, translation,
                        do_commit=False)

        self._commit()

    def __setitem__(self, stroke, translation, do_commit=False):

        # This isn't as inefficient as it looks.

        # in case it exists
        self._execute("""UPDATE
            translations
            SET translation=?
            WHERE dictionary=? AND stroke=?""",
                translation,
                self._primary_key,
                stroke,
                do_commit=False)

        # in case it doesn't exist
        self._execute("""INSERT OR IGNORE INTO
            translations
            (dictionary, stroke, translation)
            VALUES (?,?,?)""",
                self._primary_key,
                stroke, translation,
                do_commit=do_commit)

        q=self._execute("""SELECT * FROM translations""")
        sys.stderr.write(repr(q.fetchall()))

    def get(self, stroke, fallback=None):
        select = self._execute("""SELECT
            translation
            FROM translations
            WHERE stroke=?
            AND dictionary=?""",
            stroke, self._primary_key)

        result = select.fetchone()

        if result is None:
            return fallback
        else:
            return result[0]

    def __delitem__(self, key):
        self._execute("""DELETE
            FROM translations
            WHERE stroke=?
            AND dictionary=?""",
            key, self._primary_key)

    def __contains__(self, key):
        result = self._execute("""SELECT
            COUNT(*)
            FROM translations
            WHERE stroke=?
            AND dictionary=?;""",
            key, self._primary_key)

        return result.fetchone()[0]==1

    def reverse_lookup(self, translation):
        result = self._execute("""SELECT
            stroke
            FROM translations
            WHERE dictionary=?
            AND translation=?;""",
            self._primary_key,
            translation).fetchall()

        if len(result)==0:
            raise KeyError()

        return [x[0] for x in result]

    def casereverse_lookup(self, translation):
        result = self._execute("""SELECT
            stroke
            FROM translations
            WHERE dictionary=?
            AND translation=?
            COLLATE NOCASE;""",
            self._primary_key,
            translation).fetchall()

        if len(result)==0:
            raise KeyError()

        return [x[0] for x in result]

class CollectionCache(_Cache):
    def __init__(self,
            filename,
            ):

        super()

        pre_existing = os.path.exists(filename)

        self._filename = filename
        self._db = sqlite3.Connection(filename)
        self._cursor = None

        self._initialise()

    def _initialise(self):
        COMMANDS = [
                """CREATE TABLE IF NOT EXISTS
                    dictionary
                    (id INTEGER PRIMARY KEY,
                    filename TEXT,
                    timestamp NUM);
                    """,

                """CREATE UNIQUE INDEX IF NOT EXISTS
                    dictfilename
                    ON dictionary(filename);
                    """,

                """CREATE TABLE IF NOT EXISTS
                    translations
                    (dictionary NUM,
                    stroke TEXT,
                    translation TEXT);
                    """,

                """CREATE UNIQUE INDEX IF NOT EXISTS
                    translationsidx
                    ON translations(dictionary, stroke);
                    """,

                ]

        for command in COMMANDS:
            self._execute(command)

    def get_dictionary(self, filename, timestamp):
        """
        Returns a DictionaryCache which represents a dictionary file
        in the cache.

        If the named file is not already in the cache, then a new
        handle will be generated. This will also store the filename
        and timestamp in the database so we know whether to reuse
        the cache next time. The DictionaryCache will be empty
        and have its should_be_filled flag set.

        If the named file is already in the cache, AND if the datestamp
        matches the datestamp given last time, then the DictionaryCache
        will contain the same data as last time. Its should_be_filled
        flag will not be set.

        If the named file is already in the cache, but the
        datestamp differs, then the previous cache will be erased.
        The DictionaryCache will be empty and have its should_be_filled
        flag set.
        """

        previous = self._execute("""SELECT id, timestamp
            FROM dictionary
            WHERE filename=?""", filename).fetchone()

        if previous is not None:

            changed = previous[1]!=timestamp
            if changed:
                self._execute("""DELETE FROM translations
                    WHERE dictionary=?""", previous[0])

            return DictionaryCache(
                    collection_cache = self,
                    db = self._db,
                    primary_key = previous[0],
                    should_be_filled = changed)

        self._execute("""INSERT INTO dictionary (filename, timestamp)
            VALUES (?,?)""", filename, timestamp,
            do_commit = False)

        dictionary_id = self._cursor.lastrowid

        self._commit()

        return DictionaryCache(
                collection_cache = self,
                db = self._db,
                primary_key = dictionary_id,
                should_be_filled = True)


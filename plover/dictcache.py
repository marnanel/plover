import sys
import os
import sqlite3

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

        super()

        self._parent = collection_cache
        self._db = db
        self._id = primary_key
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

        result = self._execute("""SELECT
            MAX(LENGTH(stroke)-LENGTH(REPLACE(stroke, '/', '')))+1
            FROM translations
            WHERE dictionary=?;""",
            self._primary_key)

        return result.fetchone()[0]

    def __iter__(self):
        result = self._execute("""SELECT
            (stroke, translation)
            FROM translations
            WHERE dictionary=?""",
            self._primary_key)

        for (k,v) in result.fetchone():
            yield (k,v)

    def __getitem__(self, key):
        result = self.get(key)

        if result is None:
            raise KeyError()

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
                self._execute("""INSERT OR REPLACE INTO
                translations(stroke,translation)
                VALUES (?,?,?)""",
                    self._primary_key,
                    stroke, translation,
                    do_commit = False)

        self._commit()

    def __setitem__(self, stroke, translation):
        self._execute("""INSERT OR REPLACE INTO
            translations(stroke,translation)
            VALUES (?,?,?)""",
                self._primary_key,
                stroke, translation)

    def get(self, stroke, fallback=None):
        result = self._execute("""SELECT
            translation
            FROM translations
            WHERE stroke=?
            AND dictionary=?""",
            self._primary_key, stroke)

        if result is None:
            return fallback

        return result.fetchone()[0]

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
            translation).fetchone()

        if result is None:
            raise KeyError()

        return result[0].fetchall()

    def casereverse_lookup(self, value):
        result = self._execute("""SELECT
            stroke
            FROM translations
            WHERE dictionary=?
            AND translation=?
            COLLATE NOCASE;""",
            self._primary_key,
            translation).fetchall()

        return result

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
                    timestamp NUM)
                    """,

                """CREATE UNIQUE INDEX IF NOT EXISTS
                    dictfilename
                    ON dictionary(filename)
                    """,

                """CREATE TABLE IF NOT EXISTS
                    translations
                    (dictionary NUM,
                    stroke TEXT,
                    translation TEXT)
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
        the cache next time.

        If the named file is already in the cache, AND if the datestamp
        matches the datestamp given last time, then the handle will be
        the same integer as last time.

        If the named file is already in the cache, but the
        datestamp differs, then the previous cache will be erased
        and a new cache handle will be generated.
        """

        previous = self._execute("""SELECT id, timestamp
            FROM dictionary
            WHERE filename=?""", filename).fetchone()

        if previous is not None:

            changed = previous[1]!=timestamp
            if changed:
                self._execute("""DELETE * FROM translations
                    WHERE dictionary=?""", previous[0])

            return DictionaryCache(
                    collection_cache = self,
                    db = self._db,
                    primary_key = previous[0],
                    should_be_filled = changed)

        self._execute("""INSERT INTO dictionary (filename, timestamp)
            VALUES (?,?)""", filename, timestamp,
            do_commit = False)

        dictionary_id = cursor.lastrowid

        self._commit()

        return DictionaryCache(
                collection_cache = self,
                db = self._db,
                primary_key = dictionary_id,
                should_be_filled = True)


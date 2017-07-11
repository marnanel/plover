import os
import sqlite3

class CollectionCache(object):
    def __init__(self,
            filename,
            ):

        pre_existing = os.path.exists(filename)

        self._filename = filename
        self._db = sqlite3.Connection(filename)

        if not pre_existing:
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

    def _execute(self, command, *args,
            do_commit = True):
        result = self._db.execute(command, args)

        if do_commit:
            self._db.commit()

        return result    


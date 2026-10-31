# PostgreSQL driver evaluation

Decision status: owner approved pinned psycopg3 after evaluation on 2026-10-30. pgBackRest was separately approved. Stable psycopg3.3.6 was verified through the package index.

## Finding

A PostgreSQL-capable driver is necessary for this Python application to connect to PostgreSQL. Its current sqlite3 module only speaks SQLite. The local environment contains no psycopg, psycopg2, pg8000, asyncpg or SQLAlchemy installation to reuse.

## Recommendation

Use a pinned stable psycopg 3 release with its binary extra, without adding an ORM or pooling package. Its synchronous DB-API fits the existing helper architecture. The binary installation avoids adding a compiler and separate libpq installation to the current Python3.12 slim application image. Bundled client libraries must be kept current through dependency updates and the hash-locked requirements.

pg8000 is a valid pure-Python DB-API alternative. It would still be a new dependency and would require its own tested adapter. asyncpg targets asyncio and would increase the change to this synchronous persistence layer. Neither removes the need to verify SQL, transaction and schema compatibility.

The driver does not perform a schema/data migration or provide backups; those remain explicit0455/0456 work. PostgreSQL remains opt-in until the owner performs the rehearsed cutover.

## Sources

- Python sqlite3: https://docs.python.org/3.12/library/sqlite3.html
- Psycopg installation and supported runtimes: https://www.psycopg.org/psycopg3/docs/basic/install.html
- Psycopg DB-API and binding behavior: https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html
- pg8000: https://pypi.org/project/pg8000/
- asyncpg: https://magicstack.github.io/asyncpg/current/

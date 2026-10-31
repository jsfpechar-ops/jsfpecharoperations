"""Small psycopg 3 adapter for the SQLite-shaped db.py call surface.

This module is imported only when ``UBYHOST_DATABASE_URL`` selects PostgreSQL.
Application SQL remains written with SQLite's ``?`` placeholders; the lexer
below translates only placeholders outside SQL strings, identifiers and
comments, and also preserves SQLite's ASCII-only LIKE case folding.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Optional, Sequence


WRITER_LOCK_ID = 593217221
STARTUP_LOCK_ID = 593217222
LOCK_TIMEOUT = "30s"


def _sql_words(sql: str) -> list[str]:
    """SQL keyword-like words outside literals, identifiers and comments."""
    words: list[str] = []
    i = 0
    while i < len(sql):
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            i = len(sql) if end < 0 else end + 1
        elif sql.startswith("/*", i):
            depth = 1
            i += 2
            while i < len(sql) and depth:
                if sql.startswith("/*", i):
                    depth += 1
                    i += 2
                elif sql.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
        elif sql[i] in ("'", '"'):
            quote = sql[i]
            i += 1
            while i < len(sql):
                if sql[i] == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
        elif sql[i].isalpha() or sql[i] == "_":
            match = re.match(r"[A-Za-z_][A-Za-z_0-9]*", sql[i:])
            words.append(match.group(0).upper())
            i += len(match.group(0))
        else:
            i += 1
    return words


def _first_word(sql: str) -> str:
    """Return the first SQL command, ignoring leading whitespace/comments."""
    words = _sql_words(sql)
    return words[0] if words else ""


def _is_write(sql: str) -> bool:
    """Conservatively serialize every non-read/control statement."""
    first = _first_word(sql)
    if first in {"SELECT", "SHOW", "EXPLAIN", "VALUES", "BEGIN", "COMMIT", "END", "ROLLBACK", "ABORT", "SET", "RESET", "SAVEPOINT", "RELEASE", "DISCARD"}:
        return False
    if first == "WITH":
        # Application CTEs are reads today; recognize DML CTEs conservatively.
        return any(word in {"INSERT", "UPDATE", "DELETE", "MERGE"} for word in _sql_words(sql)[1:])
    return True


class PostgresRow:
    """A row with sqlite3.Row name/position/indexing behavior."""

    __slots__ = ("_names", "_values", "_first")

    def __init__(self, names: Sequence[str], values: Sequence[Any]) -> None:
        self._names = tuple(names)
        self._values = tuple(values)
        first = {}
        for index, name in enumerate(self._names):
            first.setdefault(name.lower(), index)
        self._first = first

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, (int, slice)):
            return self._values[key]
        if not isinstance(key, str):
            raise TypeError("row indices must be integers, slices, or column names")
        try:
            return self._values[self._first[key.lower()]]
        except KeyError:
            raise KeyError(key) from None

    def keys(self) -> tuple[str, ...]:
        return self._names

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def adapt_sql(sql: str, params: Optional[Sequence[Any]] = ()) -> tuple[str, Optional[Sequence[Any]]]:
    """Convert bound markers and SQLite LIKE outside quoted/comment regions.

    Psycopg treats percent signs in a query passed with parameters as its
    placeholder grammar even when those signs are inside SQL literals or
    comments. Each literal percent is therefore escaped for psycopg while
    existing SQLite question marks remain literal unless they are real binds.
    """
    if params is None:
        return sql, None
    out: list[str] = []
    i = 0
    binds = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            end = n if end < 0 else end
            out.append(sql[i:end].replace("%", "%%"))
            i = end
            continue
        if sql.startswith("/*", i):
            depth = 1
            j = i + 2
            while j < n and depth:
                if sql.startswith("/*", j):
                    depth += 1
                    j += 2
                elif sql.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            out.append(sql[i:j].replace("%", "%%"))
            i = j
            continue
        if ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < n:
                if sql[j] == quote:
                    if j + 1 < n and sql[j + 1] == quote:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(sql[i:j].replace("%", "%%"))
            i = j
            continue
        if ch == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$", sql[i:])
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                end = n if end < 0 else end + len(tag)
                out.append(sql[i:end].replace("%", "%%"))
                i = end
                continue
        if ch == "?":
            # PostgreSQL cannot infer the type of ``%s IS NULL`` for a None
            # parameter. A text cast preserves the predicate for every
            # supported scalar value and keeps None a NULL.
            suffix = sql[i + 1 :]
            out.append("%s::text" if re.match(r"\s+IS\s+NULL\b", suffix, re.I) else "%s")
            binds += 1
            i += 1
            continue
        if ch == "%":
            out.append("%%")
            i += 1
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "_$"):
                j += 1
            word = sql[i:j]
            out.append("ILIKE" if word.upper() == "LIKE" else word)
            i = j
            continue
        out.append(ch)
        i += 1
    if binds != len(params):
        raise ValueError(f"SQL has {binds} bind markers but {len(params)} values were supplied")
    return "".join(out), tuple(params)


def render_ddl(sql: str) -> Optional[str]:
    """Translate the frozen SQLite DDL subset; reject unknown SQLite syntax.

    ``None`` means one of the six SQLite invoice triggers, whose equivalent
    PostgreSQL definitions are installed separately.
    """
    visible = sql
    while True:
        visible = visible.lstrip()
        if visible.startswith("--"):
            end = visible.find("\n")
            visible = "" if end < 0 else visible[end + 1 :]
        elif visible.startswith("/*"):
            end = visible.find("*/", 2)
            if end < 0:
                raise ValueError("unterminated SQL block comment")
            visible = visible[end + 2 :]
        else:
            break
    if re.match(r"CREATE\s+TRIGGER\b", visible, re.I):
        match = re.match(r"CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z_0-9]*)", visible, re.I)
        if not match or match.group(1) not in PG_TRIGGER_NAMES:
            raise ValueError("unsupported SQLite trigger in schema source")
        return None
    is_create_table = bool(re.match(r"CREATE\s+TABLE\b", visible, re.I))
    is_alter_add_column = bool(re.match(r"ALTER\s+TABLE\b", visible, re.I))

    # The input DDL comes only from SCHEMA, ADDED_COLUMNS and numbered
    # migrations. Lex the normal tokens and preserve comments/quoted strings.
    out: list[str] = []
    tokens: list[tuple[str, str]] = []
    paren_depth = 0
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            end = n if end < 0 else end
            out.append(sql[i:end])
            i = end
            continue
        if ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < n:
                if sql[j] == quote:
                    if j + 1 < n and sql[j + 1] == quote:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(sql[i:j])
            tokens.append(("literal", ""))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            word = sql[i:j]
            upper = word.upper()
            type_position = (
                is_create_table and paren_depth == 1 and bool(tokens)
                and tokens[-1][0] == "word"
            ) or (
                is_alter_add_column
                and bool(re.search(r"\bADD\s+COLUMN\s+[A-Za-z_][A-Za-z_0-9]*\s+$", sql[:i], re.I))
            )
            if upper == "AUTOINCREMENT" and type_position:
                raise ValueError("AUTOINCREMENT must follow an INTEGER PRIMARY KEY")
            if upper == "INTEGER" and type_position:
                # The three tokens are recognized before individual type
                # translation so identity syntax stays in PostgreSQL order.
                tail = re.match(r"(\s+PRIMARY\s+KEY\s+)AUTOINCREMENT\b", sql[j:], re.I)
                if tail:
                    out.append("BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
                    consumed = len(tail.group(0))
                    tokens.extend((("word", "INTEGER"), ("word", "PRIMARY"), ("word", "KEY")))
                    i = j + consumed
                    continue
                out.append("BIGINT")
                tokens.append(("word", upper))
                i = j
                continue
            if upper == "BLOB" and type_position:
                out.append("BYTEA")
                tokens.append(("word", upper))
                i = j
                continue
            if upper == "REAL" and type_position:
                out.append("DOUBLE PRECISION")
                tokens.append(("word", upper))
                i = j
                continue
            if upper == "NOCASE":
                # Remove only the collation token; the following UNIQUE is
                # retained and an ASCII-only expression index is added later.
                if tokens and tokens[-1] == ("word", "COLLATE"):
                    while out and out[-1].isspace():
                        out.pop()
                    if not out or out[-1].strip().upper() != "COLLATE":
                        raise ValueError("unsupported NOCASE collation position")
                    out.pop()
                    tokens.pop()
                    i = j
                    continue
                raise ValueError("unsupported NOCASE token outside COLLATE")
            if upper == "TEXT" and type_position:
                out.append('TEXT COLLATE "C"')
            else:
                out.append(word)
            tokens.append(("word", upper))
            i = j
            continue
        out.append(ch)
        if not ch.isspace():
            tokens.append(("punct", ch))
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
        i += 1
    rendered = "".join(out)
    if re.search(r"\bWITHOUT\s+ROWID\b|\bVIRTUAL\s+TABLE\b|\bRAISE\s*\(", rendered, re.I):
        raise ValueError("unsupported SQLite-only DDL construct")
    # Transfer may defer only FK constraints to preserve SQLite's ability to
    # import self-referencing rows. Unique constraints stay immediate.
    rendered = re.sub(
        r"(\bREFERENCES\s+[A-Za-z_][A-Za-z_0-9]*\s*\([^)]*\)(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|RESTRICT|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT))*)",
        r"\1 DEFERRABLE INITIALLY IMMEDIATE", rendered, flags=re.I,
    )
    return rendered


def _without_comments(sql: str) -> str:
    """Remove SQL comments while preserving literals and statement layout."""
    out: list[str] = []
    i = 0
    while i < len(sql):
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            if end < 0:
                break
            out.append("\n")
            i = end + 1
        elif sql.startswith("/*", i):
            depth = 1
            j = i + 2
            while j < len(sql) and depth:
                if sql.startswith("/*", j):
                    depth += 1
                    j += 2
                elif sql.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            out.append(" ")
            i = j
        elif sql[i] in ("'", '"'):
            quote = sql[i]
            j = i + 1
            while j < len(sql):
                if sql[j] == quote:
                    if j + 1 < len(sql) and sql[j + 1] == quote:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(sql[i:j])
            i = j
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)


def order_table_ddl(statements: Sequence[str]) -> list[str]:
    """Create all tables in FK dependency order, then retain other DDL order.

    The only forward FK in the frozen baseline is ``guest.submission_id``;
    the ordering is derived from the actual SQL rather than a handwritten
    exception. Cross-table cycles fail closed. Self-references are allowed.
    """
    table_rows: list[tuple[str, set[str], str]] = []
    others: list[str] = []
    for statement in statements:
        clean = _without_comments(statement)
        match = re.search(
            r"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(",
            clean,
            re.I,
        )
        if not match:
            others.append(statement)
            continue
        table = match.group(1).lower()
        parents = {
            name.lower()
            for name in re.findall(r"\bREFERENCES\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(", clean, re.I)
            if name.lower() != table
        }
        table_rows.append((table, parents, statement))
    table_names = {table for table, _parents, _statement in table_rows}
    pending = list(table_rows)
    ordered: list[str] = []
    created: set[str] = set()
    while pending:
        ready_index = next(
            (i for i, (_table, parents, _statement) in enumerate(pending)
             if parents <= (created | (parents - table_names))),
            None,
        )
        if ready_index is None:
            raise ValueError("PostgreSQL DDL contains a cross-table foreign-key cycle")
        table, _parents, statement = pending.pop(ready_index)
        ordered.append(statement)
        created.add(table)
    return ordered + others


PG_TRIGGER_NAMES = frozenset({
    "invoice_issued_guard", "invoice_note_guard", "invoice_delete_guard",
    "invoice_item_insert_guard", "invoice_item_update_guard", "invoice_item_delete_guard",
})

PG_TRIGGERS = (
    """CREATE OR REPLACE FUNCTION ubyhost_invoice_issued_guard() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
  IF OLD.issued_at IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$""",
    """CREATE OR REPLACE FUNCTION ubyhost_invoice_note_guard() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
  IF OLD.issued_at IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$""",
    """CREATE OR REPLACE FUNCTION ubyhost_invoice_delete_guard() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
  IF OLD.issued_at IS NOT NULL AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1' THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN OLD;
END $$""",
    """CREATE OR REPLACE FUNCTION ubyhost_invoice_item_insert_guard() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
  IF (SELECT issued_at FROM invoice WHERE id = NEW.invoice_id) IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$""",
    """CREATE OR REPLACE FUNCTION ubyhost_invoice_item_update_guard() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
  IF (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN NEW;
END $$""",
    """CREATE OR REPLACE FUNCTION ubyhost_invoice_item_delete_guard() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
  IF (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL
     AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1' THEN
    RAISE EXCEPTION USING ERRCODE = 'integrity_constraint_violation', MESSAGE = 'invoice is issued and immutable';
  END IF;
  RETURN OLD;
END $$""",
)

PG_TRIGGER_DDL = (
    ("invoice_issued_guard", "invoice", "BEFORE UPDATE OF legal_entity_id, apartment_id, kind, corrects_invoice_id, correction_reason, correction_date, seq_year, seq_no, number, vs, lang, currency, vat_status, issue_date, duzp, due_date, paid_on, paid_via, seller_name, seller_seat, seller_ico, seller_dic, seller_registry, seller_bank_account, seller_iban, seller_bic, seller_email, seller_phone, buyer_name, buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email, stay_from, stay_to, stay_label, total_base_haler, total_vat_haler, total_haler, pdf_blob, pdf_sha256, issued_at, issued_by", "ubyhost_invoice_issued_guard"),
    ("invoice_note_guard", "invoice", "BEFORE UPDATE OF note", "ubyhost_invoice_note_guard"),
    ("invoice_delete_guard", "invoice", "BEFORE DELETE", "ubyhost_invoice_delete_guard"),
    ("invoice_item_insert_guard", "invoice_item", "BEFORE INSERT", "ubyhost_invoice_item_insert_guard"),
    ("invoice_item_update_guard", "invoice_item", "BEFORE UPDATE", "ubyhost_invoice_item_update_guard"),
    ("invoice_item_delete_guard", "invoice_item", "BEFORE DELETE", "ubyhost_invoice_item_delete_guard"),
)

PG_SQLITE_DATE_FUNCTION = r"""CREATE OR REPLACE FUNCTION ubyhost_sqlite_date(value text)
RETURNS text LANGUAGE plpgsql STABLE STRICT AS $$
DECLARE parsed timestamptz;
        parsed_local timestamp without time zone;
BEGIN
  IF value !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}([ T][0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]{1,6})?)?(Z|[+-][0-9]{2}:[0-9]{2})?)?$' THEN
    RETURN NULL;
  END IF;
  IF value ~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN
    parsed := value::timestamptz;
    RETURN to_char(parsed AT TIME ZONE 'UTC', 'YYYY-MM-DD');
  END IF;
  parsed_local := value::timestamp without time zone;
  RETURN to_char(parsed_local, 'YYYY-MM-DD');
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END $$"""


def sqlite_date_expr(expression: str) -> str:
    """A trusted SQL expression that matches SQLite date() for app ISO dates."""
    return f"ubyhost_sqlite_date({expression})"


def install_pg_support(connection: "PostgresConnection", *, include_triggers: bool = True) -> None:
    """Install backend-only date/collation objects and optionally invoice guards."""
    connection.execute(PG_SQLITE_DATE_FUNCTION)
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ubyhost_user_account_username_sqlite_nocase "
        "ON user_account (translate(username, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))"
    )
    if include_triggers:
        install_pg_triggers(connection)


def install_pg_triggers(connection: "PostgresConnection") -> None:
    """Install the six frozen invoice immutability guards exactly once per schema."""
    for definition in PG_TRIGGERS:
        connection.execute(definition)
    for name, table, event, function in PG_TRIGGER_DDL:
        connection.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
        connection.execute(
            f"CREATE TRIGGER {name} {event} ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )


class PostgresCursor:
    def __init__(self, connection: "PostgresConnection", raw: Any) -> None:
        self._connection = connection
        self._raw = raw

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    @property
    def description(self):
        return self._raw.description

    def execute(self, sql: str, params: Optional[Iterable[Any]] = ()) -> "PostgresCursor":
        values = None if params is None else tuple(params)
        command = sql.strip().upper()
        if command == "BEGIN IMMEDIATE":
            self._connection._raw.execute("BEGIN")
            self._connection._begin_immediate()
            self._connection._trace(sql)
            return self
        if command in {"BEGIN", "START TRANSACTION"}:
            self._connection._raw.execute(sql)
            self._connection._writer_lock_held = False
            self._connection._trace(sql)
            return self
        if command in {"COMMIT", "END", "ROLLBACK", "ABORT"}:
            self._connection._raw.execute(sql)
            self._connection._writer_lock_held = False
            self._connection._trace(sql)
            return self
        converted, adapted_values = adapt_sql(sql, values)
        self._connection._trace(sql)
        write = _is_write(sql)
        owns_transaction = write and not self._connection.in_transaction
        savepoint = None
        if owns_transaction:
            self._connection._raw.execute("BEGIN")
            self._connection._transaction_lock_reset()
            self._connection._ensure_writer_lock()
        elif write:
            self._connection._ensure_writer_lock()
            savepoint = self._connection._next_savepoint()
            self._connection._raw.execute(f"SAVEPOINT {savepoint}")
        try:
            if adapted_values is None:
                self._raw.execute(converted)
            else:
                self._raw.execute(converted, adapted_values)
        except BaseException:
            if savepoint:
                self._connection._raw.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self._connection._raw.execute(f"RELEASE SAVEPOINT {savepoint}")
            elif owns_transaction:
                self._connection._raw.rollback()
                self._connection._writer_lock_held = False
            raise
        else:
            if savepoint:
                self._connection._raw.execute(f"RELEASE SAVEPOINT {savepoint}")
            elif owns_transaction:
                self._connection._raw.commit()
                self._connection._writer_lock_held = False
        return self

    def executemany(self, sql: str, params: Iterable[Iterable[Any]]) -> "PostgresCursor":
        batches = [tuple(row) for row in params]
        if not batches:
            return self
        converted, _ = adapt_sql(sql, batches[0])
        self._connection._trace(sql)
        write = _is_write(sql)
        owns_transaction = write and not self._connection.in_transaction
        savepoint = None
        if owns_transaction:
            self._connection._raw.execute("BEGIN")
            self._connection._transaction_lock_reset()
            self._connection._ensure_writer_lock()
        elif write:
            self._connection._ensure_writer_lock()
            savepoint = self._connection._next_savepoint()
            self._connection._raw.execute(f"SAVEPOINT {savepoint}")
        try:
            self._raw.executemany(converted, batches)
        except BaseException:
            if savepoint:
                self._connection._raw.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self._connection._raw.execute(f"RELEASE SAVEPOINT {savepoint}")
            elif owns_transaction:
                self._connection._raw.rollback()
                self._connection._transaction_lock_reset()
            raise
        else:
            if savepoint:
                self._connection._raw.execute(f"RELEASE SAVEPOINT {savepoint}")
            elif owns_transaction:
                self._connection._raw.commit()
                self._connection._transaction_lock_reset()
        return self

    def _row(self, values: Any) -> Any:
        if values is None:
            return None
        names = tuple(col.name for col in (self._raw.description or ()))
        if isinstance(values, dict):
            return PostgresRow(tuple(values.keys()), tuple(values.values()))
        return PostgresRow(names, values)

    def fetchone(self) -> Any:
        return self._row(self._raw.fetchone())

    def fetchall(self) -> list[Any]:
        return [self._row(row) for row in self._raw.fetchall()]

    def fetchmany(self, size: Optional[int] = None) -> list[Any]:
        rows = self._raw.fetchmany() if size is None else self._raw.fetchmany(size)
        return [self._row(row) for row in rows]

    def __iter__(self):
        for row in self._raw:
            yield self._row(row)

    def close(self) -> None:
        self._raw.close()

    def __enter__(self) -> "PostgresCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class PostgresConnection:
    """Connection facade exposing the helper subset used by db.py."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw
        self._trace_callback: Optional[Callable[[str], None]] = None
        self._writer_lock_held = False
        self._writer_session_lock_held = False
        self._savepoint_counter = 0

    @property
    def in_transaction(self) -> bool:
        return self._raw.info.transaction_status.name != "IDLE"

    def _trace(self, sql: str) -> None:
        if self._trace_callback is not None:
            self._trace_callback(sql)

    def set_trace_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self._trace_callback = callback

    def _begin_immediate(self) -> None:
        self._ensure_writer_lock()

    def _ensure_writer_lock(self) -> None:
        if self._writer_lock_held or self._writer_session_lock_held:
            return
        self._raw.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
        self._raw.execute("SELECT pg_advisory_xact_lock(%s)", (WRITER_LOCK_ID,))
        self._writer_lock_held = True

    def _transaction_lock_reset(self) -> None:
        self._writer_lock_held = False

    def acquire_session_lock(self, lock_id: int) -> None:
        self._raw.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
        self._raw.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
        # End psycopg's implicit transaction without releasing the session lock.
        self._raw.commit()

    def release_session_lock(self, lock_id: int) -> None:
        self._raw.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
        self._raw.commit()

    def acquire_startup_lock(self) -> None:
        self.acquire_session_lock(STARTUP_LOCK_ID)

    def acquire_writer_session_lock(self) -> None:
        self.acquire_session_lock(WRITER_LOCK_ID)
        self._writer_session_lock_held = True

    def release_writer_session_lock(self) -> None:
        if self._writer_session_lock_held:
            self.release_session_lock(WRITER_LOCK_ID)
            self._writer_session_lock_held = False

    def _next_savepoint(self) -> str:
        self._savepoint_counter += 1
        return f"ubyhost_stmt_{self._savepoint_counter}"

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self, self._raw.cursor())

    def execute(self, sql: str, params: Optional[Iterable[Any]] = ()) -> PostgresCursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql: str, params: Iterable[Iterable[Any]]) -> PostgresCursor:
        return self.cursor().executemany(sql, params)

    def execute_native(self, sql: str, params: Optional[Iterable[Any]] = None) -> PostgresCursor:
        """Execute adapter-owned psycopg SQL using native ``%s`` markers."""
        self._trace(sql)
        raw = self._raw.cursor()
        if params is None:
            raw.execute(sql)
        else:
            raw.execute(sql, tuple(params))
        return PostgresCursor(self, raw)

    def executescript(self, script: str) -> None:
        raise NotImplementedError("PostgreSQL schema scripts must use db.py's strict DDL renderer")

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()
        self._writer_lock_held = False

    def close(self) -> None:
        self._raw.close()
        self._writer_lock_held = False


def is_identity_table(table: str) -> bool:
    """Whether an application table uses SQLite AUTOINCREMENT for id."""
    from . import db as app_db
    import sqlite3
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(app_db.SCHEMA)
        for version, _name, path in app_db.migration_files():
            conn.executescript(path.read_text(encoding="utf-8"))
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        return bool(row and re.search(r"\bid\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", row[0], re.I))
    finally:
        conn.close()


def connect(conninfo: str) -> PostgresConnection:
    try:
        import psycopg
        from psycopg.rows import tuple_row
    except ImportError:
        raise RuntimeError("PostgreSQL was selected but the approved psycopg 3 driver is not installed") from None
    try:
        raw = psycopg.connect(conninfo, autocommit=True, row_factory=tuple_row)
        raw.execute("SET TIME ZONE 'UTC'")
        raw.execute("SET search_path TO public")
        encoding = raw.execute("SHOW server_encoding").fetchone()[0]
        if str(encoding).upper() != "UTF8":
            raw.close()
            raise RuntimeError("PostgreSQL server encoding is not UTF8")
        return PostgresConnection(raw)
    except Exception:
        raise ConnectionError("Unable to connect to the configured PostgreSQL database") from None


def integrity_error_types() -> tuple[type[BaseException], ...]:
    try:
        from psycopg import IntegrityError
    except ImportError:
        raise RuntimeError("PostgreSQL was selected but the approved psycopg 3 driver is not installed") from None
    return (IntegrityError,)


def current_schema() -> str:
    return "current_schema()"

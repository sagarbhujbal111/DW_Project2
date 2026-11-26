import os
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit

from database import DB, ROOT, options
from seed import seed


def mysql_config(cloud):
    if not cloud:
        return dict(database=DB, **options(reader=True))
    raw = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
    if not raw and not os.getenv("DB_HOST"):
        return None
    config = options()
    config.update(database=DB, connection_timeout=4, ssl_verify_cert=True, ssl_verify_identity=True)
    if raw:
        url = urlsplit(raw)
        if url.scheme.split("+")[0] != "mysql":
            raise ValueError("A MySQL connection URL is required.")
        config.update(host=url.hostname, port=url.port or 3306, user=unquote(url.username or ""),
                      password=unquote(url.password or ""), database=unquote(url.path.lstrip("/")) or DB)
    if os.getenv("DB_SSL_CA"):
        config["ssl_ca"] = os.environ["DB_SSL_CA"]
    return config


def initialize(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript((ROOT/"schema_sqlite.sql").read_text())
        seed(conn)


@contextmanager
def replica_reader(path):
    with closing(sqlite3.connect(Path(path).as_uri()+"?mode=ro&immutable=1",uri=True)) as conn:
        conn.row_factory = lambda cur,row: dict(zip((col[0] for col in cur.description),row))
        deadline = time.monotonic()+4
        conn.set_progress_handler(lambda: time.monotonic()>deadline, 1000)
        conn.execute("PRAGMA query_only=ON")
        yield conn.cursor()


def replica_sql(sql):
    for field in ("first_day","full_date"):
        sql = sql.replace(f"CAST(DATE_FORMAT({field},'%Y-%m-01') AS DATE)", f"date({field},'start of month')")
    return (sql.replace("%s","?").replace("TIMESTAMPDIFF(MONTH,v.cohort,v.visit)",
        "(12*(strftime('%Y',v.visit)-strftime('%Y',v.cohort))+strftime('%m',v.visit)-strftime('%m',v.cohort))")
        .replace("100*","100.0*").replace(" / NULLIF"," * 1.0 / NULLIF"))

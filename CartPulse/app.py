from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
import logging
import os
import sqlite3
from tempfile import TemporaryDirectory
from cloud import initialize, mysql_config, replica_reader, replica_sql
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mysql.connector import Error, pooling
from mysql.connector.errors import PoolError
from pydantic import BaseModel, Field
import sqlglot
from sqlglot import exp

from analytics import statements
from database import DB, options

STATIC = Path(__file__).parent / "static"
IST = timezone(timedelta(hours=5, minutes=30))
TAGLINE = "From first order to forever customer"
log = logging.getLogger("cartpulse")
sandbox_slots = BoundedSemaphore(2)


@asynccontextmanager
async def lifespan(app):
    cloud = os.getenv("RENDER") == "true"
    settings = mysql_config(cloud)
    app.state.replica = None
    if settings:
        try:
            app.state.pool = pooling.MySQLConnectionPool(pool_name="cartpulse", pool_size=8,
                pool_reset_session=True, **settings)
        except Error as exc:
            if not cloud:
                raise
            log.warning("Cloud MySQL unavailable (code %s). Starting the synthetic replica.", exc.errno)
        else:
            yield
            return
    with TemporaryDirectory(prefix="cartpulse-") as directory:
        app.state.replica = Path(directory)/"warehouse.db"
        initialize(app.state.replica)
        yield


app = FastAPI(title="CartPulse — Pune E-Commerce & Customer Retention Data Warehouse",
              version="1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(Error)
def database_error(request: Request, error: Error):
    log.error("MySQL error %s", error.errno)
    return JSONResponse(status_code=503, content={"detail":"Warehouse is busy or unavailable. Please retry."})


@contextmanager
def reader():
    if app.state.replica:
        with replica_reader(app.state.replica) as cur:
            yield cur
        return
    with app.state.pool.get_connection() as conn:
        with conn.cursor(dictionary=True, buffered=True) as cur:
            cur.execute("SET SESSION MAX_EXECUTION_TIME = 4000")
            conn.start_transaction(readonly=True, isolation_level="REPEATABLE READ", consistent_snapshot=True)
            try:
                yield cur
            finally:
                conn.rollback()


@app.get("/")
def index():
    return FileResponse(STATIC/"index.html")


@app.get("/api/health")
def health():
    with reader() as cur:
        if app.state.replica:
            cur.execute("SELECT COUNT(*) AS orders FROM fact_orders")
            return {**cur.fetchone(),"engine":"SQLite","version":sqlite3.sqlite_version,"warehouse":DB,"status":"online","tagline":TAGLINE}
        cur.execute("SELECT VERSION() AS version, DATABASE() AS warehouse")
        return {**cur.fetchone(), "engine":"MySQL","status":"online","tagline":TAGLINE}


@app.get("/api/filters")
def filters():
    with reader() as cur:
        cur.execute("SELECT region_key, zone_name, pin_code FROM dim_regions ORDER BY region_key")
        zones = cur.fetchall()
        cur.execute("SELECT DISTINCT category FROM dim_products ORDER BY category")
        categories = [r["category"] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT year FROM dim_date ORDER BY year DESC")
        return {"engine":"SQLite" if app.state.replica else "MySQL","zones":zones,"categories":categories,"years":[r["year"] for r in cur.fetchall()]}


@app.get("/api/dashboard")
def dashboard(zone: int | None = Query(None, ge=1), category: str | None = Query(None, max_length=64),
              year: int | None = Query(None,ge=1900,le=9999), quarter: int | None = Query(None,ge=1,le=4)):
    result, queries = {}, {}
    with reader() as cur:
        for key, (sql, args) in statements(dict(zone=zone, category=category, year=year, quarter=quarter)).items():
            if app.state.replica:
                sql = replica_sql(sql)
            cur.execute(sql,args)
            result[key] = cur.fetchone() if key=="kpis" else cur.fetchall()
            queries[key] = {"sql":sql, "parameters":args}
    return {**result, "queries":queries, "as_of":datetime.now(IST).isoformat(timespec="seconds")}


TABLES = {"fact_orders","dim_customers","dim_products","dim_date","dim_regions",
          "vw_monthly_revenue","vw_pune_zone_sales","vw_category_performance","vw_customer_retention"}
ALLOWED = set("""select from from_ table identifier column star alias literal null boolean
distinct order ordered group having where limit offset and or not is in between eq neq gt gte lt lte
add sub mul div mod neg paren join on with with_ cte tablealias subquery union case if
count sum avg min max round coalesce nullif abs upper lower length year month day
window rownumber rank denserank lag lead firstvalue lastvalue partition tuple exists like""".split())


class Statement(BaseModel):
    sql: str = Field(min_length=1, max_length=8000)


def validated_sql(raw):
    try:
        expressions = sqlglot.parse(raw,read="mysql")
    except (sqlglot.errors.SqlglotError, RecursionError):
        raise HTTPException(400,"Check the MySQL syntax and try again.")
    if len(expressions)!=1 or not isinstance(expressions[0],(exp.Select,exp.Union)):
        raise HTTPException(400,"Enter one read-only SELECT statement.")
    tree = expressions[0]
    aliases = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
    for node in tree.walk():
        if node.key not in ALLOWED or node.comments or node.args.get("recursive"):
            raise HTTPException(400,"This sandbox supports read-only warehouse analytics.")
        if isinstance(node,exp.Table) and (node.name.lower() not in TABLES|aliases or
                node.catalog or (node.db and node.db.lower()!=DB.lower())):
            raise HTTPException(400,"Use the CartPulse warehouse tables or views.")
    # Execute only the validated, regenerated AST. MySQL also enforces read-only access.
    return tree.sql(dialect="sqlite" if app.state.replica else "mysql")


@app.post("/api/sandbox")
def sandbox(body: Statement):
    sql = validated_sql(body.sql)
    if not sandbox_slots.acquire(blocking=False):
        raise HTTPException(429,"Both query slots are busy. Please retry.")
    try:
        with reader() as cur:
            if not app.state.replica:
                cur.execute("SET SESSION SQL_SELECT_LIMIT = 201")
            cur.execute(f"SELECT * FROM ({sql}) AS cartpulse_result LIMIT 201")
            rows = cur.fetchall()
            return {"columns":[col[0] for col in cur.description],"rows":rows[:200],"truncated":len(rows)>200}
    except sqlite3.Error as exc:
        raise HTTPException(400,"SQLite could not complete this SELECT within the sandbox limits.") from exc
    except PoolError:
        raise
    except Error as exc:
        if exc.errno == 3024:
            raise HTTPException(408,"The query exceeded four seconds.")
        raise HTTPException(400,"MySQL could not complete this SELECT. Check column names and aliases.")
    finally:
        sandbox_slots.release()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8000")))

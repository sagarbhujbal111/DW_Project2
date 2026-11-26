"""Provision schema and a local SELECT-only runtime account."""
import os
import secrets
from dotenv import set_key
from database import DB, READER, ROOT, admin_connection
from seed import seed


def configure():
    env = ROOT / ".env"
    if not env.exists():
        env.write_text((ROOT / ".env.example").read_text())
    password = os.getenv("DB_READ_PASSWORD") or secrets.token_urlsafe(32)
    if not os.getenv("DB_READ_PASSWORD"):
        set_key(str(env), "DB_READ_PASSWORD", password)
    if os.name != "nt":
        env.chmod(0o600)
    with admin_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT GET_LOCK('cartpulse_bootstrap', 45), VERSION()")
        locked, version = cur.fetchone()
        if not locked or "MariaDB" in version or int(version.split(".")[0]) < 8:
            raise RuntimeError("CartPulse requires MySQL 8+ and an exclusive setup lock.")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        conn.database = DB
        for statement in (ROOT/"schema.sql").read_text(encoding="utf-8").split(";"):
            if statement.strip():
                cur.execute(statement)
        cur.execute(f"CREATE USER IF NOT EXISTS '{READER}'@'localhost' IDENTIFIED BY %s", (password,))
        for table in ("fact_orders","dim_customers","dim_regions","dim_date","dim_products",
                      "vw_monthly_revenue","vw_category_performance","vw_pune_zone_sales","vw_customer_retention"):
            cur.execute(f"GRANT SELECT ON `{DB}`.`{table}` TO '{READER}'@'localhost'")
        print(f"MySQL {version} | {DB} | {seed(conn)} seed orders processed.")
        cur.close()


if __name__ == "__main__":
    configure()

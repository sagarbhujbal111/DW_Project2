import os
import re
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if os.getenv("RENDER") != "true":
    load_dotenv(ROOT / ".env")


def setting(name, default):
    value = os.getenv(name, default)
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,31}", value):
        raise ValueError(f"Invalid identifier in {name}")
    return value


DB = setting("DB_NAME", "ecommerce_dw")
READER = setting("DB_READ_USER", "cartpulse_reader")


def options(reader=False):
    return dict(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT","3306")),
                user=READER if reader else os.getenv("DB_USER","root"),
                password=os.environ["DB_READ_PASSWORD"] if reader else os.getenv("DB_PASSWORD",""),
                charset="utf8mb4", connection_timeout=8, allow_local_infile=False,
                time_zone="+05:30", use_pure=True)


def admin_connection(database=False):
    settings = options()
    if os.environ.get("CARTPULSE_ADMIN_SOCKET"):
        settings["unix_socket"] = os.environ["CARTPULSE_ADMIN_SOCKET"]
    if database:
        settings["database"] = DB
    return mysql.connector.connect(**settings)

"""Start an isolated, loopback-only MySQL server from the official Windows archive."""
import hashlib
import os
import secrets
import socket
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
VERSION = "8.4.8"
DIST = f"mysql-{VERSION}-winx64"
SHA256 = "53685bb61a1efc5ecc1b35c1b6bd0d30ba799f4943a1ef2c34df464f5a774c7f"


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), .5):
            return True
    except OSError:
        return False


def start():
    RUNTIME.mkdir(exist_ok=True)
    env = ROOT / ".env"
    if not env.exists():
        env.write_text((ROOT / ".env.example").read_text())
    cfg = dotenv_values(env)
    port = int(cfg.get("DB_PORT",3306))
    if listening(port):
        return
    base = RUNTIME / DIST
    exe = base / "bin" / "mysqld.exe"
    if not exe.exists():
        archive = RUNTIME / "mysql.zip"
        if not archive.exists():
            urllib.request.urlretrieve(f"https://cdn.mysql.com/archives/mysql-8.4/{DIST}.zip", archive)
        with archive.open("rb") as data:
            if hashlib.file_digest(data,"sha256").hexdigest() != SHA256:
                raise RuntimeError("MySQL archive checksum mismatch.")
        with zipfile.ZipFile(archive) as package:
            package.extractall(RUNTIME)
    data = RUNTIME / "mysql-data"
    args = [str(exe), "--no-defaults", f"--basedir={base}", f"--datadir={data}",
            f"--port={port}", "--bind-address=127.0.0.1", "--mysqlx=OFF",
            "--performance-schema=OFF", "--innodb-buffer-pool-size=64M",
            "--console", f"--pid-file={RUNTIME/'mysql.pid'}"]
    init_file = RUNTIME / "first-start.sql"
    if not (data/"mysql").exists():
        password = cfg.get("DB_PASSWORD") or secrets.token_urlsafe(32)
        if not cfg.get("DB_PASSWORD"):
            set_key(str(env), "DB_PASSWORD", password)
        escaped = password.replace("\\","\\\\").replace("'","''")
        init_file.write_text(f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{escaped}';", encoding="utf-8")
        subprocess.run(args+["--initialize-insecure"], check=True)
    if init_file.exists():
        args.append(f"--init-file={init_file}")
    with (RUNTIME/"mysql.log").open("ab") as quiet:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=quiet, stderr=quiet,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(100):
        if listening(port):
            init_file.unlink(missing_ok=True)
            return
        if process.poll() is not None:
            break
        time.sleep(.3)
    raise RuntimeError(f"MySQL failed to start. See {RUNTIME/'mysql.log'}")


if __name__ == "__main__":
    start()

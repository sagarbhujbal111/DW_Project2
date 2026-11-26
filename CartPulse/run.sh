#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./run.ps1 ;;
esac

umask 077
priv=()
if (( EUID != 0 )); then priv=(sudo); fi
if ! command -v python3 >/dev/null || ! command -v mysqld >/dev/null; then
  if ! command -v apt-get >/dev/null; then
    echo "Install Python 3.11+, venv, and MySQL 8.0+ or use Ubuntu 24.04." >&2
    exit 1
  fi
  "${priv[@]}" apt-get update
  "${priv[@]}" apt-get install -y mysql-server python3 python3-venv
fi
if [[ ! -x .venv/bin/python ]]; then
  if ! python3 -m venv .venv; then
    "${priv[@]}" apt-get install -y python3-venv
    python3 -m venv .venv
  fi
fi
py=.venv/bin/python
"$py" -m pip install --disable-pip-version-check -r requirements.txt
[[ -f .env ]] || cp .env.example .env
chmod 600 .env
if ! mysqladmin ping --silent >/dev/null 2>&1; then
  if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
    "${priv[@]}" systemctl start mysql
  else
    "${priv[@]}" service mysql start
  fi
fi
if "$py" -c 'from database import admin_connection; admin_connection().close()' >/dev/null 2>&1; then
  "$py" bootstrap.py
else
  # Ubuntu's default root account authenticates via the local Unix socket.
  socket=$(mysql_config --socket 2>/dev/null || echo /var/run/mysqld/mysqld.sock)
  owner=$(id -u); group=$(id -g)
  "${priv[@]}" env CARTPULSE_ADMIN_SOCKET="$socket" "$PWD/$py" bootstrap.py
  "${priv[@]}" chown "$owner:$group" .env
fi
port=$("$py" -c 'from database import os; print(os.getenv("APP_PORT","8000"))')
if curl -fsS "http://127.0.0.1:$port/api/health" 2>/dev/null | "$py" -c 'import json,sys; sys.exit(json.load(sys.stdin).get("tagline")!="From first order to forever customer")' 2>/dev/null; then
  echo "CartPulse is running at http://127.0.0.1:$port/"
  exit 0
fi
exec "$py" -m uvicorn app:app --host 127.0.0.1 --port "$port"

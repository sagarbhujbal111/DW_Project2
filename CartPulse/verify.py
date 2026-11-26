"""Exercise the live HTTP surface using curl and validate cross-chart totals."""
import json
import os
import shutil
import subprocess
from decimal import Decimal
from urllib.parse import urlencode

from database import options
import mysql.connector

BASE = "http://127.0.0.1:"+os.getenv("APP_PORT","8000")
CURL = shutil.which("curl.exe") or shutil.which("curl")
DOLLAR = chr(36)


def request(path, body=None, status=200):
    cmd = [CURL,"--noproxy","*","--max-time","15","-sS","-w","\\n%{http_code}",BASE+path]
    if body is not None:
        cmd += ["-H","Content-Type: application/json","--data-binary","@-"]
    result = subprocess.run(cmd,input=json.dumps(body).encode() if body is not None else None,
                            capture_output=True,check=True).stdout.decode()
    raw, code = result.rsplit("\n",1)
    assert int(code)==status, (path,code,raw[:400])
    assert DOLLAR not in raw, path
    return json.loads(raw) if path.startswith("/api/") else raw


def check():
    home = request("/")
    assert "From first order to forever customer" in home and "CartPulse" in home
    for asset in ("dashboard.js","style.css","mark.svg"):
        request("/static/"+asset)
    health = request("/api/health")
    assert health["warehouse"]=="ecommerce_dw" and int(health["version"].split(".")[0])>=8
    filters = request("/api/filters")
    assert len(filters["zones"])==6 and len(filters["categories"])==5
    data = request("/api/dashboard")
    k = data["kpis"]
    assert k["orders"]>=500 and k["buyers"]>=100 and len(data["trend"])==12
    assert 0 < k["repeat_pct"] < 100
    for dimension in ("trend","zones","categories"):
        assert sum(Decimal(str(r["revenue_inr"])) for r in data[dimension])==Decimal(str(k["revenue_inr"]))
    assert sum(z["orders"] for z in data["zones"])==k["orders"]
    assert all(c["retention_pct"]==100 for c in data["cohorts"] if c["age"]==0)
    for row in filters["zones"]:
        subset=request("/api/dashboard?"+urlencode(dict(zone=row["region_key"],category=filters["categories"][0],year=2025,quarter=4)))
        assert len(subset["zones"])==1 and len(subset["trend"])==3 and len(subset["categories"])<=1
        assert all(0<=c["retention_pct"]<=100 for c in subset["cohorts"])
    empty=request("/api/dashboard?category=NoMatches")
    assert empty["kpis"]["orders"]==0 and not empty["cohorts"]
    request("/api/dashboard?quarter=5",status=422)
    sample=request("/api/sandbox",{"sql":"SELECT customer_name, email, segment FROM dim_customers ORDER BY customer_key LIMIT 6"})
    assert sample["rows"][0]["customer_name"]=="Aarav Kulkarni"
    assert all(r["email"].endswith(".in") for r in sample["rows"])
    for view in ("vw_monthly_revenue","vw_customer_retention","vw_category_performance","vw_pune_zone_sales"):
        assert request("/api/sandbox",{"sql":"SELECT * FROM "+view+" LIMIT 1"})["rows"]
    assert request("/api/sandbox",{"sql":"SELECT order_id FROM fact_orders"})["truncated"]
    request("/api/sandbox",{"sql":"SET SESSION autocommit = 1"},status=400)
    with mysql.connector.connect(database=health["warehouse"],**options(reader=True)) as conn:
        cur=conn.cursor()
        cur.execute("SHOW GRANTS")
        grants=[r[0] for r in cur.fetchall()]
        assert all(g.startswith(("GRANT SELECT ON","GRANT USAGE ON")) for g in grants)
    print("PASS | MySQL",health["version"],"|",k["orders"],"orders |",k["buyers"],"customers | INR",k["revenue_inr"])
    print("PASS | frontend, assets, APIs, views, all six zone filters, cohorts, read-only grants and result cap")


if __name__=="__main__":
    check()

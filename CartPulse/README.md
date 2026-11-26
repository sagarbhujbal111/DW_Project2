# CartPulse

**Pune E-Commerce & Customer Retention Data Warehouse**

_From first order to forever customer_

CartPulse is a FastAPI dashboard backed by MySQL 8. It explores a deterministic, fictional 2025 Pune retail dataset with 1,635 orders, 240 customers, 20 products, six delivery micro-markets and a 365-day calendar. Currency is INR and dashboard timestamps use IST.

## Run locally

**Windows, from this workspace**

```powershell
cd "C:\Users\SAGAR\OneDrive\Documents\ChatGPT\p2\CartPulse"
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Open [CartPulse](http://127.0.0.1:8000/). The workspace already contains the virtual environment, downloaded MySQL distribution, database files and generated credentials. On a fresh Windows x64 checkout, install Python 3.11+ with venv and the Microsoft Visual C++ x64 runtime if your PC lacks it. The first launch downloads and checks the Oracle MySQL 8.4.8 archive, initializes an isolated loopback server, applies the schema, seeds the warehouse and launches Uvicorn. Later launches reuse those files. Port 3306 must be free for the isolated server. If an existing MySQL server occupies that port, setup uses the administrator credentials in .env.

**Ubuntu 24.04**

```bash
cd CartPulse
bash run.sh
```

The launcher installs missing MySQL and Python packages through apt, starts the MySQL service, creates a virtual environment, installs the pinned application dependencies, creates the database and read-only account, applies the schema, seeds it and starts Uvicorn. A fresh machine needs internet access and permission to install packages and start services. Ubuntu’s socket-authenticated root account works through sudo. Git Bash on Windows dispatches to the Windows launcher.

Both launchers reuse a healthy CartPulse web server when one is already running. A newly launched foreground Uvicorn process stops with Ctrl+C. The MySQL instance persists for the next launch.

## Warehouse

| Table | Grain and contents |
| --- | --- |
| fact_orders | One product line per order. Total revenue is quantity × unit price × (1 − fractional discount). |
| dim_customers | One synthetic customer with name, example Indian email address, segment and signup date. |
| dim_products | One product with a category, subcategory and standard unit cost in INR. |
| dim_regions | One Pune delivery micro-market and the representative PIN code supplied for it. |
| dim_date | One calendar day with year, quarter, month and weekday fields. |

All tables use InnoDB and utf8mb4. Foreign keys and indexes cover the joining columns, calendar periods, customer history, product categories and regions. The four MySQL views aggregate monthly revenue, category margin, zone sales and customer repeat purchasing. The dashboard queries the star schema to support simultaneous filters.

| Pune micro-market | Representative PIN |
| --- | --- |
| Hinjawadi IT Park | 411057 |
| Kothrud & Karve Nagar | 411038 |
| Viman Nagar & Koregaon Park | 411014 |
| Pimpri-Chinchwad / PCMC | 411018 |
| Baner & Balewadi | 411045 |
| Hadapsar & Magarpatta | 411028 |

The seed uses stable keys, a fixed random seed and transactional bulk inserts. Reapplying it preserves existing matching seed keys. Use a dedicated ecommerce_dw database for the sample. The fixture models elevated Ganesh festival and Diwali shopping volumes and repeat purchasing. Business results describe synthetic orders.

## Dashboard

- **Overview** shows net revenue, order count, average order value and the share of distinct buyers with two or more matching orders. Sparklines show each metric by month. Monthly repeat rates use purchases within that month.
- **Revenue & order trend** combines revenue bars on the left INR axis with order counts on the right. Darker bars mark August–November festival shopping periods. Peak-month ranking uses RANK and LAG in the query explorer.
- **Category performance** compares net revenue on the lower axis and gross margin percentage on the upper axis. Gross margin is (revenue − quantity × unit cost) divided by revenue.
- **Pune zones** shows order demand by delivery PIN, share of filtered revenue, and each zone’s repeat rate. The source records delivery destinations and order volume. Transit times and courier performance require delivery events.
- **Customer retention** assigns each buyer to the month of their first qualifying purchase in the selected zone/category across their full history. The period filter selects acquisition cohorts and observed activity. Each cell divides distinct active buyers by the cohort’s original size. Observed months without purchases have zero retention. Future months are blanked with a dash.
- **SQL Explorer** shows the star schema, exact parameterized SELECT templates and bound filter values. Its sandbox accepts a bounded subset of MySQL SELECT, including warehouse joins, aggregations and nonrecursive CTEs. It validates a parsed syntax tree, regenerates SQL, uses a SELECT-only account, opens a read-only transaction, limits execution time to four seconds and returns up to 200 rows. Two queries may run concurrently.

The frontend uses Tailwind CSS and Chart.js via CDN. Project CSS and a local Chart.js fallback keep charts and dashboard controls available when those CDNs are unreachable.

## Configuration and operation

.env.example documents DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_READ_USER, DB_READ_PASSWORD and APP_PORT. Setup uses root for provisioning. FastAPI’s eight-connection pool uses the separate read-only account. The generated .env, database, downloads and runtime logs are excluded from Git.

The app binds to 127.0.0.1:8000 and the Windows database binds to 127.0.0.1:3306. This launch is for a trusted local operator. Before publishing customer data to a network, put authentication and HTTPS in front of FastAPI, restrict access to SQL Explorer, store secrets outside synchronized folders, and provision database backups and service supervision. Sites hosting supports static assets and Workers. Running the live Python/MySQL backend on a shared host requires infrastructure that runs those services.

Windows runtime files are under .runtime. mysql.log and mysql.pid identify the isolated server. For a graceful database stop after stopping the web server, run this from the project directory:

```powershell
.\.venv\Scripts\python.exe -c "from database import admin_connection; c=admin_connection(); c.cmd_shutdown()"
```

## Verification

Keep the web server running and use a second terminal.

```powershell
.\.venv\Scripts\python.exe verify.py
```

```bash
.venv/bin/python verify.py
```

The verifier uses curl for the HTML, first-party static assets, health, filters, dashboard and SQL sandbox. It checks all six region filters, a combined category/quarter slice, an empty slice, cross-chart INR totals, cohort rates, Indian customer records, all views, read-only grants, result limits and currency symbols. Re-run the launcher and verifier to check idempotency.

| HTTP route | Purpose |
| --- | --- |
| GET / | Single-page dashboard |
| GET /api/health | Live database version, warehouse and tagline |
| GET /api/filters | Pune zones, categories and calendar years |
| GET /api/dashboard | KPIs, monthly series, categories, zones, cohorts, peaks and SQL using optional zone, category, year and quarter parameters |
| POST /api/sandbox | JSON object with a sql string. Returns columns, rows and truncation state. |

The schema, seed, analytics queries and API live in schema.sql, seed.py, analytics.py and app.py. bootstrap.py handles provisioning. static/ contains the dashboard and browser assets.

## Render deployment

The repository-root render.yaml builds the CartPulse subdirectory and serves it on Render's assigned port. The default free service seeds a temporary SQLite file on startup with the same synthetic fixture as MySQL. Each request opens the replica read-only. The sidebar and /api/health identify the active database.

For an existing provisioned cloud warehouse, configure MYSQL_URL or a MySQL DATABASE_URL, or supply DB_HOST, DB_PORT, DB_NAME, DB_USER and DB_PASSWORD. Use a SELECT-only account with access to the five tables and four views. Cloud MySQL verifies TLS certificates and hostnames. DB_SSL_CA may point to a provider CA certificate file. Set secrets through Render. At startup a failed MySQL connection switches the service to the synthetic replica. Restart the service to retry MySQL after an outage. Local launchers continue using the local .env and MySQL pool.

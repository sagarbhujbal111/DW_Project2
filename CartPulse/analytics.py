"""Dashboard SQL templates. The explorer receives the statements used here verbatim."""
BASE = """FROM fact_orders f
JOIN dim_date d USING (date_key)
JOIN dim_regions r USING (region_key)
JOIN dim_products p USING (product_key)"""


def predicates(filters, keys):
    fields = {"zone":"r.region_key","category":"p.category","year":"d.year","quarter":"d.quarter"}
    active = [k for k in keys if filters.get(k) is not None]
    return (" WHERE " + " AND ".join(fields[k]+" = %s" for k in active) if active else "",
            tuple(filters[k] for k in active))


def statements(filters):
    where, params = predicates(filters, ("zone","category","year","quarter"))
    segment, seg_params = predicates(filters, ("zone","category"))
    period, time_params = predicates(filters, ("year","quarter"))
    base = BASE + where
    kpis = f"""WITH buyers AS (
  SELECT f.customer_key, COUNT(*) AS orders, SUM(f.total_revenue) AS revenue_inr
  {base}
  GROUP BY f.customer_key
)
SELECT COALESCE(SUM(revenue_inr), 0) AS revenue_inr,
       COALESCE(SUM(orders), 0) AS orders, COUNT(*) AS buyers,
       COALESCE(SUM(orders > 1), 0) AS repeat_buyers,
       COALESCE(SUM(revenue_inr) / NULLIF(SUM(orders), 0), 0) AS aov_inr,
       COALESCE(100 * AVG(orders > 1), 0) AS repeat_pct
FROM buyers"""
    trend = f"""WITH buyer_month AS (
  SELECT d.year, d.month_number, f.customer_key, COUNT(*) AS orders,
         SUM(f.total_revenue) AS revenue_inr {base}
  GROUP BY d.year, d.month_number, f.customer_key
), monthly AS (
  SELECT year, month_number, SUM(orders) AS orders, SUM(revenue_inr) AS revenue_inr,
         100*AVG(orders > 1) AS repeat_pct FROM buyer_month GROUP BY year, month_number
), calendar AS (
  SELECT DISTINCT d.year, d.month_number FROM dim_date d{period}
)
SELECT c.year, c.month_number, COALESCE(m.orders,0) AS orders,
       COALESCE(m.revenue_inr,0) AS revenue_inr, COALESCE(m.repeat_pct,0) AS repeat_pct,
       COALESCE(m.revenue_inr / NULLIF(m.orders,0),0) AS aov_inr
FROM calendar c LEFT JOIN monthly m USING (year, month_number)
ORDER BY c.year, c.month_number"""
    categories = f"""SELECT p.category, SUM(f.total_revenue) AS revenue_inr,
       100*SUM(f.total_revenue - f.quantity*p.unit_cost)/NULLIF(SUM(f.total_revenue),0) AS margin_pct
{base}
GROUP BY p.category ORDER BY revenue_inr DESC"""
    zones = f"""WITH buyers AS (
  SELECT r.region_key, f.customer_key, COUNT(*) AS orders, SUM(f.total_revenue) AS revenue_inr
  {base} GROUP BY r.region_key, f.customer_key
), totals AS (
  SELECT region_key, SUM(orders) AS orders, SUM(revenue_inr) AS revenue_inr,
         100*AVG(orders > 1) AS repeat_pct FROM buyers GROUP BY region_key
)
SELECT r.zone_name, r.pin_code, r.region_key, COALESCE(t.orders,0) AS orders,
       COALESCE(t.revenue_inr,0) AS revenue_inr, COALESCE(t.repeat_pct,0) AS repeat_pct,
       COALESCE(100*t.revenue_inr/NULLIF(SUM(t.revenue_inr) OVER (),0),0) AS share_pct
FROM dim_regions r LEFT JOIN totals t USING (region_key)
{('WHERE r.region_key = %s' if filters.get('zone') is not None else '')}
ORDER BY revenue_inr DESC, r.region_key"""
    cohort = f"""WITH history AS (
  SELECT f.customer_key, d.full_date,
         FIRST_VALUE(d.full_date) OVER (PARTITION BY f.customer_key ORDER BY d.full_date, f.order_id) AS first_day
  {BASE}{segment}
), visits AS (
  SELECT DISTINCT customer_key, CAST(DATE_FORMAT(first_day,'%Y-%m-01') AS DATE) AS cohort,
         CAST(DATE_FORMAT(full_date,'%Y-%m-01') AS DATE) AS visit FROM history
), activity AS (
  SELECT v.cohort, TIMESTAMPDIFF(MONTH,v.cohort,v.visit) AS age, COUNT(*) AS buyers
  FROM visits v JOIN dim_date d ON d.full_date=v.visit{period}
  GROUP BY v.cohort, age
), sizes AS (
  SELECT cohort, COUNT(*) AS members FROM visits WHERE visit=cohort GROUP BY cohort
)
SELECT a.cohort, a.age, a.buyers, s.members, 100*a.buyers/s.members AS retention_pct
FROM activity a JOIN sizes s USING (cohort)
JOIN dim_date d ON d.full_date=a.cohort{period}
ORDER BY a.cohort, a.age"""
    # Rank peaks and compare each month with its predecessor using the same filtered series.
    ranking = f"""WITH series AS ({trend})
SELECT year, month_number, revenue_inr,
       RANK() OVER (ORDER BY revenue_inr DESC) AS revenue_rank,
       LAG(revenue_inr) OVER (ORDER BY year, month_number) AS prior_revenue_inr
FROM series ORDER BY revenue_rank, year, month_number"""
    return {
        "kpis": (kpis,params), "trend": (trend,params+time_params),
        "categories": (categories,params),
        "zones": (zones,params+((filters["zone"],) if filters.get("zone") is not None else ())),
        "cohorts": (cohort,seg_params+time_params+time_params), "peaks": (ranking,params+time_params)
    }

CREATE TABLE IF NOT EXISTS dim_customers (
  customer_key INT PRIMARY KEY,
  customer_name VARCHAR(100) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  segment VARCHAR(64) NOT NULL,
  signup_date DATE NOT NULL,
  INDEX idx_customer_segment (segment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_products (
  product_key INT PRIMARY KEY,
  product_name VARCHAR(120) NOT NULL,
  category VARCHAR(64) NOT NULL,
  sub_category VARCHAR(64) NOT NULL,
  unit_cost DECIMAL(10,2) NOT NULL CHECK (unit_cost >= 0),
  INDEX idx_product_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_regions (
  region_key INT PRIMARY KEY,
  zone_name VARCHAR(80) NOT NULL UNIQUE,
  pin_code CHAR(6) NOT NULL,
  city VARCHAR(50) NOT NULL,
  state VARCHAR(50) NOT NULL,
  country VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_date (
  date_key INT PRIMARY KEY,
  full_date DATE NOT NULL UNIQUE,
  year SMALLINT NOT NULL,
  quarter TINYINT NOT NULL,
  month_number TINYINT NOT NULL,
  month_name VARCHAR(12) NOT NULL,
  day_of_week VARCHAR(10) NOT NULL,
  INDEX idx_calendar (year, quarter, month_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fact_orders (
  order_id BIGINT PRIMARY KEY,
  customer_key INT NOT NULL,
  product_key INT NOT NULL,
  region_key INT NOT NULL,
  date_key INT NOT NULL,
  quantity SMALLINT NOT NULL CHECK (quantity > 0),
  unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
  discount DECIMAL(5,4) NOT NULL CHECK (discount BETWEEN 0 AND 1),
  total_revenue DECIMAL(14,2) NOT NULL,
  FOREIGN KEY (customer_key) REFERENCES dim_customers(customer_key),
  FOREIGN KEY (product_key) REFERENCES dim_products(product_key),
  FOREIGN KEY (region_key) REFERENCES dim_regions(region_key),
  FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
  INDEX idx_customer_date (customer_key, date_key),
  INDEX idx_date_region (date_key, region_key),
  INDEX idx_region_product (region_key, product_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW vw_monthly_revenue AS
SELECT d.year, d.month_number, COUNT(*) AS orders, SUM(f.total_revenue) AS revenue_inr
FROM fact_orders f JOIN dim_date d USING(date_key) GROUP BY d.year, d.month_number;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW vw_category_performance AS
SELECT p.category, SUM(f.total_revenue) AS revenue_inr,
ROUND(100 * SUM(f.total_revenue - f.quantity*p.unit_cost)/NULLIF(SUM(f.total_revenue),0),2) AS margin_pct
FROM fact_orders f JOIN dim_products p USING(product_key) GROUP BY p.category;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW vw_pune_zone_sales AS
SELECT r.zone_name, r.pin_code, COUNT(*) AS orders, SUM(f.total_revenue) AS revenue_inr
FROM fact_orders f JOIN dim_regions r USING(region_key) GROUP BY r.zone_name, r.pin_code;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW vw_customer_retention AS
SELECT customer_key, COUNT(*) AS orders, MIN(date_key) AS first_order_date_key,
MAX(date_key) AS last_order_date_key, COUNT(*) > 1 AS repeat_buyer
FROM fact_orders GROUP BY customer_key;

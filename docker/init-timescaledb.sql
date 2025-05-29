-- TimescaleDB initialization script for Origami Composer
-- This script is run when the PostgreSQL container is first created

-- Create the TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create UUID extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create pg_trgm extension for text search optimization
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create btree_gist extension for advanced indexing
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Set default timezone to EST (for trading hours)
SET timezone = 'America/New_York';

-- Performance tuning for TimescaleDB
ALTER SYSTEM SET shared_preload_libraries = 'timescaledb';
ALTER SYSTEM SET timescaledb.max_background_workers = 8;
ALTER SYSTEM SET max_worker_processes = 16;
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET effective_cache_size = '4GB';
ALTER SYSTEM SET random_page_cost = 1.1;

-- Create custom types for enums (will be created by SQLAlchemy, but define here for reference)
-- These will be created automatically by SQLAlchemy when models are created

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON DATABASE origami_composer TO origami;
GRANT ALL ON SCHEMA public TO origami;

-- Create indexes for common queries (these supplement the ones created by SQLAlchemy)
-- Note: These will be created after tables exist, shown here for documentation

-- Performance optimization settings
ALTER DATABASE origami_composer SET log_min_duration_statement = 1000;  -- Log slow queries > 1s
ALTER DATABASE origami_composer SET idle_in_transaction_session_timeout = 600000;  -- 10 min timeout

-- Add comment to database
COMMENT ON DATABASE origami_composer IS 'Origami Composer - Algorithmic Paper Trading Platform';

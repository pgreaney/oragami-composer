"""
Database initialization and TimescaleDB setup for Origami Composer
Creates tables, hypertables, and initial data
"""

import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.database.connection import sync_engine, get_sync_db
from app.models import Base, User, Symphony


def create_timescaledb_hypertables(db_session):
    """
    Convert time-series tables to TimescaleDB hypertables
    
    Args:
        db_session: SQLAlchemy database session
    """
    hypertables = [
        ("positions", "timestamp"),
        ("trades", "executed_at"),
        ("performance_metrics", "calculated_at"),
    ]
    
    for table_name, time_column in hypertables:
        try:
            # Check if TimescaleDB extension exists
            result = db_session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            )
            if not result.first():
                print("TimescaleDB extension not found. Installing...")
                db_session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
                db_session.commit()
            
            # Convert table to hypertable
            db_session.execute(
                text(f"""
                    SELECT create_hypertable(
                        '{table_name}',
                        '{time_column}',
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '1 day'
                    )
                """)
            )
            db_session.commit()
            print(f"✅ Created hypertable for {table_name}")
            
            # Create additional indexes for performance
            if table_name == "positions":
                db_session.execute(
                    text(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table_name}_symphony_symbol_time 
                        ON {table_name} (symphony_id, symbol, {time_column} DESC)
                    """)
                )
            elif table_name == "trades":
                db_session.execute(
                    text(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table_name}_symphony_time 
                        ON {table_name} (symphony_id, {time_column} DESC)
                    """)
                )
            elif table_name == "performance_metrics":
                db_session.execute(
                    text(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table_name}_type_time 
                        ON {table_name} (symphony_id, metric_type, {time_column} DESC)
                    """)
                )
            db_session.commit()
            
        except ProgrammingError as e:
            if "already a hypertable" in str(e):
                print(f"ℹ️  {table_name} is already a hypertable")
            else:
                print(f"❌ Error creating hypertable for {table_name}: {e}")
                raise


def create_database_functions(db_session):
    """
    Create custom PostgreSQL functions for performance
    
    Args:
        db_session: SQLAlchemy database session
    """
    # Function to calculate portfolio value at a point in time
    db_session.execute(text("""
        CREATE OR REPLACE FUNCTION calculate_portfolio_value(
            p_symphony_id UUID,
            p_timestamp TIMESTAMPTZ
        ) RETURNS NUMERIC AS $$
        DECLARE
            total_value NUMERIC := 0;
        BEGIN
            SELECT COALESCE(SUM(market_value), 0)
            INTO total_value
            FROM positions
            WHERE symphony_id = p_symphony_id
              AND timestamp = (
                  SELECT MAX(timestamp)
                  FROM positions
                  WHERE symphony_id = p_symphony_id
                    AND timestamp <= p_timestamp
              );
            
            RETURN total_value;
        END;
        $$ LANGUAGE plpgsql;
    """))
    
    # Function to get latest positions for a symphony
    db_session.execute(text("""
        CREATE OR REPLACE FUNCTION get_latest_positions(p_symphony_id UUID)
        RETURNS TABLE (
            symbol VARCHAR,
            quantity FLOAT,
            market_value FLOAT,
            unrealized_pnl FLOAT,
            weight FLOAT,
            timestamp TIMESTAMPTZ
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT DISTINCT ON (p.symbol)
                p.symbol,
                p.quantity,
                p.market_value,
                p.unrealized_pnl,
                p.weight,
                p.timestamp
            FROM positions p
            WHERE p.symphony_id = p_symphony_id
            ORDER BY p.symbol, p.timestamp DESC;
        END;
        $$ LANGUAGE plpgsql;
    """))
    
    db_session.commit()
    print("✅ Created database functions")


def init_db():
    """
    Initialize database with tables and TimescaleDB configuration
    """
    print("🚀 Initializing Origami Composer database...")
    
    # Create all tables
    Base.metadata.create_all(bind=sync_engine)
    print("✅ Created all tables")
    
    # Get database session
    db = get_sync_db()
    
    try:
        # Set up TimescaleDB hypertables
        create_timescaledb_hypertables(db)
        
        # Create custom functions
        create_database_functions(db)
        
        # Create initial admin user (optional)
        existing_admin = db.query(User).filter_by(email="admin@origamicomposer.com").first()
        if not existing_admin:
            from app.auth.password import get_password_hash
            
            admin_user = User(
                email="admin@origamicomposer.com",
                password_hash=get_password_hash("changeme123!"),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(admin_user)
            db.commit()
            print("✅ Created initial admin user (admin@origamicomposer.com)")
        
        print("✅ Database initialization complete!")
        
    except Exception as e:
        print(f"❌ Error during database initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def drop_db():
    """
    Drop all database tables (use with caution!)
    """
    print("⚠️  Dropping all database tables...")
    Base.metadata.drop_all(bind=sync_engine)
    print("✅ All tables dropped")


if __name__ == "__main__":
    # Run initialization when script is executed directly
    init_db()

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def initialize_database():
    """Creates the necessary tables in the PostgreSQL database."""
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                print("Creating 'orders' table...")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(255) NOT NULL,
                        summary TEXT,
                        delivery TEXT,
                        total INTEGER,
                        paid BOOLEAN DEFAULT FALSE,
                        reference TEXT,
                        timestamp TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                print("Creating 'conversations' table...")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        chat_id VARCHAR(255) NOT NULL UNIQUE,
                        history JSONB,
                        last_updated TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                
                conn.commit()
                print("✅ Database tables created successfully.")
                
    except psycopg.OperationalError as e:
        print(f"❌ Could not connect to the database: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    initialize_database()

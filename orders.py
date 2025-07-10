import aiosqlite
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'orders.db')

async def get_db_conn():
    """Establishes a connection to the SQLite database."""
    conn = await aiosqlite.connect(DATABASE_PATH)
    conn.row_factory = aiosqlite.Row
    return conn

async def init_db():
    """Initializes the database and creates tables if they don't exist."""
    async with await get_db_conn() as conn:
        cursor = await conn.cursor()
        
        # Create orders table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                customer_name TEXT,
                platform TEXT,
                summary TEXT,
                delivery TEXT,
                total INTEGER,
                paid INTEGER DEFAULT 0,
                reference TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create conversations table
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                platform TEXT,
                history TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, platform)
            );
        """)
        
        await conn.commit()
    print("✅ Database initialized successfully.")

if __name__ == '__main__':
    import asyncio
    asyncio.run(init_db())

# app/database/session_store.py
"""
Database persistence layer for transcript sessions.
Supports both PostgreSQL and MongoDB backends.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class SessionStore(ABC):
    """Abstract base class for session storage backends."""
    
    @abstractmethod
    async def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save session information."""
        pass
    
    @abstractmethod
    async def get_session(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get session by meeting ID."""
        pass
    
    @abstractmethod
    async def save_transcript_entries(self, meeting_id: str, entries: List[Dict[str, Any]]) -> bool:
        """Save transcript entries."""
        pass
    
    @abstractmethod
    async def get_transcript_entries(self, meeting_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get transcript entries for a meeting."""
        pass
    
    @abstractmethod
    async def delete_session(self, meeting_id: str) -> bool:
        """Delete a session and all its data."""
        pass

class PostgreSQLStore(SessionStore):
    """PostgreSQL implementation of session store."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._pool = None
        
    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            import asyncpg
            
            self._pool = await asyncpg.create_pool(self.connection_string)
            
            # Create tables if they don't exist
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        status VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        participants TEXT[],
                        total_entries INTEGER DEFAULT 0,
                        metadata JSONB DEFAULT '{}'
                    )
                """)
                
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS transcript_entries (
                        id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        speaker VARCHAR(255) NOT NULL,
                        text TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        confidence FLOAT DEFAULT 1.0,
                        FOREIGN KEY (meeting_id) REFERENCES sessions(meeting_id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_transcript_meeting_id ON transcript_entries(meeting_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_transcript_timestamp ON transcript_entries(timestamp)")
                
            logger.info("PostgreSQL store initialized successfully")
            
        except ImportError:
            logger.error("asyncpg not installed. Run: pip install asyncpg")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL store: {e}")
            raise
    
    async def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save session to PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO sessions (meeting_id, status, created_at, participants, total_entries, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (meeting_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        participants = EXCLUDED.participants,
                        total_entries = EXCLUDED.total_entries,
                        metadata = EXCLUDED.metadata
                """, 
                    session_data['meeting_id'],
                    session_data['status'],
                    datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00')),
                    session_data['participants'],
                    session_data['total_entries'],
                    json.dumps(session_data.get('metadata', {}))
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    async def get_session(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get session from PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM sessions WHERE meeting_id = $1", meeting_id
                )
                if row:
                    return {
                        'meeting_id': row['meeting_id'],
                        'status': row['status'],
                        'created_at': row['created_at'].isoformat(),
                        'participants': row['participants'],
                        'total_entries': row['total_entries'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def save_transcript_entries(self, meeting_id: str, entries: List[Dict[str, Any]]) -> bool:
        """Save transcript entries to PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                for entry in entries:
                    await conn.execute("""
                        INSERT INTO transcript_entries (id, meeting_id, speaker, text, timestamp, confidence)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (id) DO NOTHING
                    """,
                        entry['id'],
                        meeting_id,
                        entry['speaker'],
                        entry['text'],
                        datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00')),
                        entry['confidence']
                    )
            return True
        except Exception as e:
            logger.error(f"Failed to save transcript entries: {e}")
            return False
    
    async def get_transcript_entries(self, meeting_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get transcript entries from PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM transcript_entries 
                    WHERE meeting_id = $1 
                    ORDER BY timestamp DESC 
                    LIMIT $2
                """, meeting_id, limit)
                
                return [
                    {
                        'id': row['id'],
                        'speaker': row['speaker'],
                        'text': row['text'],
                        'timestamp': row['timestamp'].isoformat(),
                        'confidence': row['confidence']
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get transcript entries: {e}")
            return []
    
    async def delete_session(self, meeting_id: str) -> bool:
        """Delete session from PostgreSQL."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("DELETE FROM sessions WHERE meeting_id = $1", meeting_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

class MongoDBStore(SessionStore):
    """MongoDB implementation of session store."""
    
    def __init__(self, connection_string: str, database_name: str = "transcript_db"):
        self.connection_string = connection_string
        self.database_name = database_name
        self._client = None
        self._db = None
    
    async def initialize(self):
        """Initialize MongoDB connection."""
        try:
            import motor.motor_asyncio
            
            self._client = motor.motor_asyncio.AsyncIOMotorClient(self.connection_string)
            self._db = self._client[self.database_name]
            
            # Create indexes
            await self._db.sessions.create_index("meeting_id", unique=True)
            await self._db.transcript_entries.create_index("meeting_id")
            await self._db.transcript_entries.create_index("timestamp")
            
            logger.info("MongoDB store initialized successfully")
            
        except ImportError:
            logger.error("motor not installed. Run: pip install motor")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB store: {e}")
            raise
    
    async def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save session to MongoDB."""
        try:
            await self._db.sessions.replace_one(
                {"meeting_id": session_data["meeting_id"]},
                session_data,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    async def get_session(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get session from MongoDB."""
        try:
            session = await self._db.sessions.find_one({"meeting_id": meeting_id})
            if session:
                # Remove MongoDB's _id field
                session.pop('_id', None)
            return session
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def save_transcript_entries(self, meeting_id: str, entries: List[Dict[str, Any]]) -> bool:
        """Save transcript entries to MongoDB."""
        try:
            for entry in entries:
                entry['meeting_id'] = meeting_id
            
            # Use upsert to avoid duplicates
            operations = [
                {
                    "replaceOne": {
                        "filter": {"id": entry["id"]},
                        "replacement": entry,
                        "upsert": True
                    }
                }
                for entry in entries
            ]
            
            if operations:
                await self._db.transcript_entries.bulk_write(operations)
            return True
        except Exception as e:
            logger.error(f"Failed to save transcript entries: {e}")
            return False
    
    async def get_transcript_entries(self, meeting_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get transcript entries from MongoDB."""
        try:
            cursor = self._db.transcript_entries.find(
                {"meeting_id": meeting_id}
            ).sort("timestamp", -1).limit(limit)
            
            entries = []
            async for entry in cursor:
                entry.pop('_id', None)  # Remove MongoDB's _id
                entry.pop('meeting_id', None)  # Remove meeting_id from response
                entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"Failed to get transcript entries: {e}")
            return []
    
    async def delete_session(self, meeting_id: str) -> bool:
        """Delete session from MongoDB."""
        try:
            await self._db.sessions.delete_one({"meeting_id": meeting_id})
            await self._db.transcript_entries.delete_many({"meeting_id": meeting_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

class FileStore(SessionStore):
    """File-based storage implementation (for development/testing)."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(f"{data_dir}/sessions", exist_ok=True)
        os.makedirs(f"{data_dir}/transcripts", exist_ok=True)
    
    async def initialize(self):
        """Initialize file store."""
        logger.info(f"File store initialized at: {self.data_dir}")
    
    async def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save session to file."""
        try:
            file_path = f"{self.data_dir}/sessions/{session_data['meeting_id']}.json"
            with open(file_path, 'w') as f:
                json.dump(session_data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save session to file: {e}")
            return False
    
    async def get_session(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get session from file."""
        try:
            file_path = f"{self.data_dir}/sessions/{meeting_id}.json"
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to get session from file: {e}")
            return None
    
    async def save_transcript_entries(self, meeting_id: str, entries: List[Dict[str, Any]]) -> bool:
        """Save transcript entries to file."""
        try:
            file_path = f"{self.data_dir}/transcripts/{meeting_id}.json"
            
            # Load existing entries
            existing_entries = []
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    existing_entries = json.load(f)
            
            # Add new entries (avoid duplicates by ID)
            existing_ids = {entry['id'] for entry in existing_entries}
            new_entries = [entry for entry in entries if entry['id'] not in existing_ids]
            
            if new_entries:
                all_entries = existing_entries + new_entries
                with open(file_path, 'w') as f:
                    json.dump(all_entries, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save transcript entries to file: {e}")
            return False
    
    async def get_transcript_entries(self, meeting_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get transcript entries from file."""
        try:
            file_path = f"{self.data_dir}/transcripts/{meeting_id}.json"
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    entries = json.load(f)
                return entries[-limit:] if len(entries) > limit else entries
            return []
        except Exception as e:
            logger.error(f"Failed to get transcript entries from file: {e}")
            return []
    
    async def delete_session(self, meeting_id: str) -> bool:
        """Delete session files."""
        try:
            session_file = f"{self.data_dir}/sessions/{meeting_id}.json"
            transcript_file = f"{self.data_dir}/transcripts/{meeting_id}.json"
            
            if os.path.exists(session_file):
                os.remove(session_file)
            if os.path.exists(transcript_file):
                os.remove(transcript_file)
                
            return True
        except Exception as e:
            logger.error(f"Failed to delete session files: {e}")
            return False

# Factory function to create appropriate store
def create_session_store(store_type: str = None, **kwargs) -> SessionStore:
    """
    Factory function to create session store based on configuration.
    
    Args:
        store_type: Type of store ('postgresql', 'mongodb', 'file')
        **kwargs: Store-specific configuration
    
    Returns:
        Configured session store instance
    """
    
    if store_type is None:
        store_type = os.getenv("SESSION_STORE_TYPE", "file")
    
    if store_type.lower() == "postgresql":
        connection_string = kwargs.get("connection_string") or os.getenv("DATABASE_URL")
        if not connection_string:
            raise ValueError("PostgreSQL connection string required")
        return PostgreSQLStore(connection_string)
    
    elif store_type.lower() == "mongodb":
        connection_string = kwargs.get("connection_string") or os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        database_name = kwargs.get("database_name") or os.getenv("MONGODB_DATABASE", "transcript_db")
        return MongoDBStore(connection_string, database_name)
    
    else:  # Default to file store
        data_dir = kwargs.get("data_dir") or os.getenv("DATA_DIR", "data")
        return FileStore(data_dir)

# Global store instance
_session_store: Optional[SessionStore] = None

async def get_session_store() -> SessionStore:
    """Get the global session store instance."""
    global _session_store
    if _session_store is None:
        _session_store = create_session_store()
        await _session_store.initialize()
    return _session_store
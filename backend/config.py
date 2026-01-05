import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    
    # PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "bidsdb")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "biduser")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "bidpassword")
    
    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

config = Config()
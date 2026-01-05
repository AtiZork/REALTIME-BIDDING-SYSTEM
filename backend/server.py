import asyncio
import json
import logging
from datetime import datetime
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import asyncpg
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Real-Time Bidding System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.redis_client = None
        self.db_pool = None
        self.pubsub = None
        self.listener_task = None

    async def initialize(self):
        try:
            self.redis_client = await redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✓ Redis connected successfully")
            
            self.db_pool = await asyncpg.create_pool(
                config.DATABASE_URL,
                min_size=5,
                max_size=20
            )
            logger.info("✓ PostgreSQL connected successfully")
            
            await self.init_database()
            
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("new_bid")
            self.listener_task = asyncio.create_task(self.redis_listener())
            logger.info("✓ Redis pub/sub listener started")
            
        except Exception as e:
            logger.error(f"✗ Initialization error: {e}")
            raise

    async def init_database(self):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bids (
                    id SERIAL PRIMARY KEY,
                    bidder_name VARCHAR(255) NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bids_timestamp 
                ON bids(timestamp DESC)
            """)
            logger.info("✓ Database schema initialized")

    async def redis_listener(self):
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await self.broadcast(data)
        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    async def get_highest_bid(self):
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT bidder_name, amount, timestamp 
                FROM bids 
                ORDER BY amount DESC, timestamp DESC 
                LIMIT 1
            """)
            if row:
                return {
                    "bidder_name": row["bidder_name"],
                    "amount": float(row["amount"]),
                    "timestamp": row["timestamp"].isoformat()
                }
            return None

    async def get_bid_history(self, limit: int = 50):
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT bidder_name, amount, timestamp 
                FROM bids 
                ORDER BY timestamp DESC 
                LIMIT $1
            """, limit)
            return [
                {
                    "bidder_name": row["bidder_name"],
                    "amount": float(row["amount"]),
                    "timestamp": row["timestamp"].isoformat()
                }
                for row in rows
            ]

    async def save_bid(self, bidder_name: str, amount: float):
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO bids (bidder_name, amount, timestamp)
                VALUES ($1, $2, $3)
                RETURNING id, bidder_name, amount, timestamp
            """, bidder_name, amount, datetime.utcnow())
            
            bid_data = {
                "type": "new_bid",
                "data": {
                    "id": row["id"],
                    "bidder_name": row["bidder_name"],
                    "amount": float(row["amount"]),
                    "timestamp": row["timestamp"].isoformat()
                }
            }
            
            await self.redis_client.publish("new_bid", json.dumps(bid_data))
            
            return bid_data

    async def cleanup(self):
        if self.listener_task:
            self.listener_task.cancel()
        if self.pubsub:
            await self.pubsub.unsubscribe("new_bid")
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.db_pool:
            await self.db_pool.close()
        logger.info("✓ Cleanup completed")

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    await manager.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    await manager.cleanup()

@app.get("/")
async def get():
    return {"message": "Real-Time Bidding System API", "status": "running"}

@app.get("/health")
async def health_check():
    try:
        await manager.redis_client.ping()
        async with manager.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        highest_bid = await manager.get_highest_bid()
        bid_history = await manager.get_bid_history()
        
        await websocket.send_json({
            "type": "initial_data",
            "data": {
                "highest_bid": highest_bid,
                "bid_history": bid_history
            }
        })
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "new_bid":
                bidder_name = data.get("bidder_name", "").strip()
                amount = data.get("amount")
                
                if not bidder_name:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Bidder name is required"
                    })
                    continue
                
                if not amount or amount <= 0:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Bid amount must be greater than 0"
                    })
                    continue
                
                current_highest = await manager.get_highest_bid()
                if current_highest and amount <= current_highest["amount"]:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Bid must be higher than current highest bid: ${current_highest['amount']:.2f}"
                    })
                    continue
                
                await manager.save_bid(bidder_name, amount)
                
            elif data.get("type") == "get_history":
                bid_history = await manager.get_bid_history()
                await websocket.send_json({
                    "type": "bid_history",
                    "data": bid_history
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info"
    )
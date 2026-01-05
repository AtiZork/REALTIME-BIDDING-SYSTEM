# Real-Time Bidding System

A real-time bidding system with WebSocket support, horizontal scalability, and fault tolerance.

## Features

### Frontend
-  Real-time bidding interface
-  Live highest bid display
-  Historical bid list
-  User input for bidder name and amount
-  Browser refresh handling
-  Automatic reconnection on connection loss
-  Responsive design
-  Visual connection status indicator

### Backend
-  WebSocket API for real-time updates
-  Horizontal scalability (multiple server pods)
-  Redis pub/sub for cross-server communication
-  PostgreSQL for persistent storage
-  Automatic reconnection handling
-  Health check endpoints
-  Graceful shutdown handling

## Architecture

```
┌─────────────┐
│   Frontend  │
│  (Browser)  │
└──────┬──────┘
       │
       │ WebSocket
       │
┌──────▼──────────────────────┐
│    Nginx Load Balancer      │
└──────┬──────────────────────┘
       │
       ├─────────┬─────────┐
       │         │         │
┌──────▼────┐ ┌─▼─────┐ ┌─▼─────┐
│ Backend 1 │ │ BE 2  │ │ BE 3  │
└─────┬─────┘ └───┬───┘ └───┬───┘
      │           │         │
      └───────────┼─────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
┌─────▼─────┐         ┌───────▼──────┐
│   Redis   │         │  PostgreSQL  │
│  Pub/Sub  │         │   Database   │
└───────────┘         └──────────────┘
```

## Installation & Setup

### Prerequisites
- Ubuntu/Linux system
- Python 3.11+
- Docker & Docker Compose 

### Option 1: Docker Deployment (Recommended)

1. **Install Docker & Docker Compose**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER
newgrp docker
```

2. **Build and run all services**
```bash
cd realtime-bidding-system
docker-compose up --build
```

3. **Access the application**
- Frontend: http://localhost
- Backend instances: http://localhost:8001, http://localhost:8002, http://localhost:8003
- Health check: http://localhost/health

4. **Test horizontal scaling**
```bash
# Kill a backend instance to simulate pod failure
docker stop bidding_backend1

# The system continues to work with remaining instances
# Restart the instance
docker start bidding_backend1
```

### Option 2: Local Development

1. **Install system dependencies**
```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip redis-server postgresql postgresql-contrib
```

2. **Setup PostgreSQL**
```bash
sudo -u postgres psql
```
```sql
CREATE DATABASE bidsdb;
CREATE USER biduser WITH PASSWORD 'bidpassword';
GRANT ALL PRIVILEGES ON DATABASE bidsdb TO biduser;
\q
```

3. **Start Redis**
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

4. **Setup Python environment**
```bash
cd realtime-bidding-system
python3 -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
```

5. **Run backend servers (multiple terminals)**

Terminal 1:
```bash
cd backend
PORT=8001 python server.py
```

Terminal 2:
```bash
cd backend
PORT=8002 python server.py
```

Terminal 3:
```bash
cd backend
PORT=8003 python server.py
```

6. **Serve frontend**
```bash
cd frontend
python3 -m http.server 8080
```

7. **Access application**
- Frontend: http://localhost:8080
- Update `frontend/index.html` WebSocket URL to point to your backend ports

## Testing the System

### Test Real-Time Updates
1. Open the application in multiple browser windows
2. Place a bid in one window
3. Observe real-time updates in all windows

### Test Browser Refresh
1. Place some bids
2. Refresh the browser
3. All data persists and displays correctly

### Test Connection Resilience
1. Disconnect network (airplane mode)
2. Try to place bids (they queue)
3. Reconnect network
4. System automatically reconnects

### Test Horizontal Scalability
```bash
# With Docker
docker stop bidding_backend1
docker stop bidding_backend2
# System continues working with backend3

docker start bidding_backend1
docker start bidding_backend2
# Instances rejoin seamlessly
```

### Test Pod Rescheduling
```bash
# Simulate k8s pod kill
docker kill bidding_backend1
docker-compose up -d backend1
# New instance starts and joins the cluster
```

## API Endpoints

### WebSocket
- `ws://localhost/ws` - WebSocket connection for real-time bidding

### HTTP
- `GET /` - API information
- `GET /health` - Health check endpoint

### WebSocket Message Format

**Client → Server (New Bid)**
```json
{
  "type": "new_bid",
  "bidder_name": "John Doe",
  "amount": 100.50
}
```

**Server → Client (Initial Data)**
```json
{
  "type": "initial_data",
  "data": {
    "highest_bid": {
      "bidder_name": "Alice",
      "amount": 150.00,
      "timestamp": "2024-01-01T12:00:00"
    },
    "bid_history": [...]
  }
}
```

**Server → Client (New Bid Broadcast)**
```json
{
  "type": "new_bid",
  "data": {
    "id": 1,
    "bidder_name": "Bob",
    "amount": 200.00,
    "timestamp": "2024-01-01T12:05:00"
  }
}
```

**Server → Client (Error)**
```json
{
  "type": "error",
  "message": "Bid must be higher than current highest bid"
}
```

## Technology Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript, WebSocket API
- **Backend**: Python 3.11, FastAPI, WebSockets
- **Database**: PostgreSQL 15
- **Cache/Pub-Sub**: Redis 7
- **Load Balancer**: Nginx
- **Container**: Docker, Docker Compose

## Monitoring & Logs

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend1

# PostgreSQL
docker-compose logs -f postgres

# Redis
docker-compose logs -f redis
```

### Check service health
```bash
curl http://localhost/health
```

## Troubleshooting

### Connection Issues
- Check if all services are running: `docker-compose ps`
- Verify Redis: `docker exec -it bidding_redis redis-cli ping`
- Verify PostgreSQL: `docker exec -it bidding_postgres pg_isready`

### Port Conflicts
If ports are already in use, modify `docker-compose.yml`:
```yaml
ports:
  - "8080:80"  # Change 80 to 8080
```

### Database Issues
Reset database:
```bash
docker-compose down -v
docker-compose up -d
```



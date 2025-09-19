# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start with custom port (as seen in main.py)
python app/main.py  # Runs on port 8001
```

### Docker Development
```bash
# Build and run with Docker Compose (recommended)
docker-compose up -d

# Build and run with Docker
docker build -t gemini-balance .
docker run -d -p 8000:8000 --name gemini-balance \
  -v ./data:/app/data \
  --env-file .env \
  ghcr.io/snailyp/gemini-balance:latest

# Pull and run latest image
docker pull ghcr.io/snailyp/gemini-balance:latest
```

### Configuration
```bash
# Copy environment configuration
cp .env.example .env
# Edit .env file with your specific settings
```

## Application Architecture

### Core Structure
- **FastAPI Application**: Built with Python 3.10+ using FastAPI framework
- **Database**: Supports both MySQL and SQLite with SQLAlchemy ORM
- **Async Architecture**: Uses asyncio for non-blocking I/O operations
- **Modular Design**: Clean separation of concerns with dedicated modules

### Key Components

#### Application Lifecycle (`app/core/application.py`)
- `create_app()`: Main FastAPI app factory with lifespan management
- Database initialization and connection management
- Scheduler startup/shutdown for background tasks
- Update checking and version management
- Static file serving and template configuration

#### Configuration (`app/config/config.py`)
- Pydantic-based settings with environment variable support
- Dynamic configuration sync to database
- Validation for MySQL/SQLite configurations
- Real-time configuration updates without restart

#### Service Layer Architecture
- **Key Management** (`app/service/key/`): API key validation, rotation, and load balancing
- **Chat Service** (`app/service/chat/`): Core conversation handling with Gemini API
- **Proxy Service** (`app/service/proxy/`): HTTP/SOCKS5 proxy support with consistent hashing
- **Stats Service** (`app/service/stats/`): API usage analytics and monitoring
- **Image Service** (`app/service/image/`): Image generation and multi-provider upload (SM.MS, PicGo, CloudFlare, Aliyun OSS)

#### Router Structure (`app/router/`)
- **Gemini Routes**: Direct Gemini API forwarding (`/gemini/v1beta`)
- **OpenAI Compatible Routes**: OpenAI format API (`/openai/v1`, `/hf/v1`)
- **Admin Routes**: Configuration, logs, and key management pages
- **Vertex Express Routes**: Google Vertex AI platform integration

#### Authentication & Security
- Token-based authentication for API access
- Session-based authentication for admin web interface
- Request validation and rate limiting capabilities

### Database Schema
- **Dynamic Configuration**: Settings stored in database with real-time sync
- **Request Logging**: API call tracking with success/failure metrics
- **Error Logging**: Detailed error tracking with automatic cleanup
- **Key Status**: API key health monitoring and failure tracking

### Background Processing
- **Scheduler** (`app/scheduler/`): APScheduler for periodic tasks
- **Key Health Checks**: Automatic validation and recovery of disabled keys
- **Log Cleanup**: Configurable retention policies for request/error logs
- **Update Checking**: Automatic version checking against GitHub releases

### API Compatibility
- **Dual Protocol Support**: Seamless handling of both Gemini and OpenAI API formats
- **Model Translation**: Automatic mapping between different API model names
- **Feature Extensions**: Advanced capabilities like web search, image generation, and thinking process display
- **Streaming Optimization**: Configurable stream output with fake streaming support

### Load Balancing Strategy
- **Sequential Key Rotation**: Round-robin distribution across available API keys
- **Automatic Failover**: Disabled keys bypass with configurable retry limits
- **Proxy Consistency**: Consistent hash mapping of API keys to proxy servers
- **Health Recovery**: Automatic re-enabling of recovered keys

### Environment Configuration
Key settings in `.env` file:
- `DATABASE_TYPE`: mysql or sqlite
- `API_KEYS`: JSON array of Gemini API keys for load balancing (supports per-key proxy)
- `BASE_PROXY_URL`: Template for proxy servers with {port} placeholder
- `ALLOWED_TOKENS`: Authentication tokens for API access
- `IMAGE_MODELS`, `SEARCH_MODELS`: Feature-specific model configurations
- `PROXIES`: HTTP/SOCKS5 proxy configuration with consistency hashing (legacy)
- `MAX_FAILURES`, `MAX_RETRIES`: Resilience configuration

### Per-Key Proxy Support
Enhanced API key configuration supporting individual proxy assignment:
- **Simple format**: `["AIzaSy..."]` - No proxy, uses global proxy settings or direct connection
- **Advanced format**: `[{"key":"AIzaSy...","proxy_port":10001}]` - Per-key proxy configuration
- **BASE_PROXY_URL**: Template like `http://user:pass@proxy.com:{port}` where {port} is replaced
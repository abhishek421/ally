#!/bin/bash
# Quick start script for the admin panel

echo "🚀 Starting AI Analyst with Admin Panel..."
echo ""

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "   ✓ Created .env from .env.example"
        echo "   📝 Please edit .env with your configuration"
    else
        echo "   ❌ .env.example not found"
        exit 1
    fi
fi

# Start docker-compose
echo "🐳 Starting Docker containers..."
docker-compose up --build -d

# Wait for the application to be ready
echo ""
echo "⏳ Waiting for application to start..."
sleep 5

# Check if app is running
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo "✅ Application is running!"
    echo ""
    echo "📊 Admin Panel: http://localhost:8000/admin"
    echo "🏥 Health Check: http://localhost:8000/health"
    echo "📖 API Docs: http://localhost:8000/docs"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f app"
    echo ""
    echo "To stop:"
    echo "  docker-compose down"
else
    echo ""
    echo "⚠️  Application may still be starting..."
    echo "   Check logs: docker-compose logs -f app"
    echo ""
    echo "   Once ready, access:"
    echo "   📊 Admin Panel: http://localhost:8000/admin"
fi

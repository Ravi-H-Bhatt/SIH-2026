#!/bin/bash

# Border Screening API - Local Run Script
# Requires: Python 3.8+, Supabase account configured in .env

set -e

echo "🚀 Border Document Screening API - Local Setup"
echo "================================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📋 Please copy .env.example to .env and configure your Supabase credentials"
    echo "📖 See SUPABASE_SETUP.md for detailed instructions"
    exit 1
fi

# Check Python version
echo "✅ Checking Python installation..."
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "   Python version: $python_version"

# Install dependencies
echo "📦 Installing dependencies..."
python3 -m pip install --user -q -r requirements.txt 2>/dev/null || python3 -m pip install -q -r requirements.txt

# Create uploads directory
echo "📁 Creating uploads directory..."
mkdir -p uploads

# Initialize database (optional - uncomment if needed)
# echo "🗄️  Initializing database..."
# python3 create_db.py

echo ""
echo "🎉 Setup complete!"
echo "================================================"
echo ""
echo "Starting FastAPI server..."
echo "📍 API available at: http://localhost:8000"
echo "📚 Docs available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the server
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

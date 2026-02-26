#!/bin/bash
# Setup script for UniFi Maintenance Dashboard

set -e

echo "=========================================="
echo "UniFi Maintenance Dashboard - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "🔍 Checking Python version..."
python3 --version

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and configure your UniFi controller settings!"
    echo ""
else
    echo ""
    echo "✅ .env file already exists"
    echo ""
fi

# Create required directories
echo "📁 Creating required directories..."
mkdir -p data logs static templates

# Make test script executable
chmod +x test_unifi_connection.py

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your UniFi controller settings:"
echo "     nano .env"
echo ""
echo "  2. Test connection to UniFi controller:"
echo "     source venv/bin/activate"
echo "     python test_unifi_connection.py"
echo ""
echo "  3. Start the application:"
echo "     uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  4. Access dashboard at: http://localhost:8000"
echo ""

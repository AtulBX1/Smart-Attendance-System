#!/bin/bash
# Flask Cache Cleanup Script
# Removes all Python cache and Flask temporary files

echo "🧹 Cleaning Python cache..."

# Remove __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove .pyc files
find . -type f -name "*.pyc" -delete 2>/dev/null

# Remove .pyo files
find . -type f -name "*.pyo" -delete 2>/dev/null

# Remove Flask instance folder
rm -rf instance/ 2>/dev/null

# Remove .webassets-cache
rm -rf .webassets-cache/ 2>/dev/null

echo "✅ Cache cleanup complete!"
echo ""
echo "You can now restart Flask:"
echo "  python backend/app.py"

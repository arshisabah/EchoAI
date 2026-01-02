#!/bin/bash
# Project Cleanup Script - Removes unused files and folders
# EchoAI Project Cleanup
# IMPORTANT: Review PROJECT_AUDIT_REPORT.md before running

set -e

echo "====================================="
echo "EchoAI Project Cleanup Script"
echo "====================================="
echo ""
echo "⚠️  WARNING: This will DELETE unused files permanently"
echo "📋 Please review PROJECT_AUDIT_REPORT.md first"
echo ""
read -p "Continue? (type 'yes' to proceed): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Navigate to project root
cd "$(dirname "$0")"

# Counter for deleted files
deleted_count=0

# 1. Delete backup files
echo "🗑️  Removing backup files..."
if [ -f "backend/app/routers/transcript.py.bak" ]; then
    rm "backend/app/routers/transcript.py.bak"
    echo "   ✓ Deleted transcript.py.bak"
    ((deleted_count++))
fi

# 2. Delete empty auth router
echo "🗑️  Removing empty files..."
if [ -f "backend/app/routers/auth.py" ]; then
    if [ ! -s "backend/app/routers/auth.py" ]; then
        rm "backend/app/routers/auth.py"
        echo "   ✓ Deleted empty auth.py"
        ((deleted_count++))
    else
        echo "   ⚠️  auth.py is not empty, skipping (manual review needed)"
    fi
fi

# 3. Delete unused modules
echo "🗑️  Removing unused modules..."

if [ -f "backend/app/modules/bias_detection.py" ]; then
    rm "backend/app/modules/bias_detection.py"
    echo "   ✓ Deleted bias_detection.py"
    ((deleted_count++))
fi

if [ -f "backend/app/modules/resume_matcher.py" ]; then
    rm "backend/app/modules/resume_matcher.py"
    echo "   ✓ Deleted resume_matcher.py"
    ((deleted_count++))
fi

if [ -f "backend/app/modules/echo_ai_module.py" ]; then
    rm "backend/app/modules/echo_ai_module.py"
    echo "   ✓ Deleted echo_ai_module.py"
    ((deleted_count++))
fi

if [ -f "backend/app/modules/sentiment_analysis.py" ]; then
    rm "backend/app/modules/sentiment_analysis.py"
    echo "   ✓ Deleted sentiment_analysis.py (not using model)"
    ((deleted_count++))
fi

# 4. Delete unused model folders
echo "🗑️  Removing unused model folders..."

if [ -d "backend/app/models/bias" ]; then
    rm -rf "backend/app/models/bias"
    echo "   ✓ Deleted models/bias/ folder"
    ((deleted_count++))
fi

if [ -d "backend/app/models/embedding" ]; then
    rm -rf "backend/app/models/embedding"
    echo "   ✓ Deleted models/embedding/ folder"
    ((deleted_count++))
fi

if [ -d "backend/app/models/sentiment" ]; then
    rm -rf "backend/app/models/sentiment"
    echo "   ✓ Deleted models/sentiment/ folder"
    ((deleted_count++))
fi

# 5. Clean up __pycache__ folders
echo "🧹 Cleaning Python cache..."
find backend/app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "   ✓ Removed __pycache__ folders"

# 6. Clean up .pyc files
find backend -name "*.pyc" -delete 2>/dev/null || true
echo "   ✓ Removed .pyc files"

echo ""
echo "====================================="
echo "✅ Cleanup completed!"
echo "====================================="
echo "📊 Files/folders deleted: $deleted_count"
echo ""
echo "📝 Next steps:"
echo "   1. Review laptop_models_config.py (remove bias_detection refs)"
echo "   2. Review balanced_models_setup.py (remove bias_detection refs)"
echo "   3. Test the backend: cd backend && python app/main.py"
echo "   4. Run tests: cd backend && pytest tests/"
echo ""
echo "💾 All changes are permanent. No backup was created."
echo "====================================="

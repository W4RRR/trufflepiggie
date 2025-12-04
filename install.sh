#!/bin/bash
# TrufflePiggie - Quick Install Script
# =====================================

echo ""
echo "  🐷 TrufflePiggie Installer"
echo "  =========================="
echo ""

# Check Python version
python3 --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Install dependencies
echo "[*] Installing dependencies..."
pip3 install -q requests rich pyyaml

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Add your GitHub token to: config/tokens/my_token.txt"
    echo "  2. Run: python3 trufflepiggie.py -q 'target.com' -o results"
    echo ""
else
    echo "❌ Installation failed"
    exit 1
fi


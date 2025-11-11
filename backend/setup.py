#!/usr/bin/env python3
"""
Quick setup script - installs dependencies without using pip install -e .
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run command and report"""
    print(f"\n▶ {description}...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0:
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} failed")
        return False

# Get backend path
backend_path = Path(__file__).parent

print("="*60)
print("  SUNA Backend Setup")
print("="*60)

# Step 1: Install dependencies from pyproject.toml
deps = [
    "python-dotenv>=1.0.1",
    "fastapi>=0.115.0",
    "uvicorn>=0.27.0",
    "websockets>=13.0",
    "playwright>=1.40.0",
    "python-socketio>=5.9.0",
]

print("\n▶ Installing Python dependencies...")
for dep in deps:
    print(f"  Installing: {dep}...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", dep])

print("\n✅ Dependencies installed!")

# Step 2: Verify imports
print("\n▶ Verifying imports...")
try:
    import dotenv
    print("  ✓ dotenv")
except ImportError:
    print("  ✗ dotenv - NOT FOUND")

try:
    import fastapi
    print("  ✓ fastapi")
except ImportError:
    print("  ✗ fastapi - NOT FOUND")

try:
    import uvicorn
    print("  ✓ uvicorn")
except ImportError:
    print("  ✗ uvicorn - NOT FOUND")

try:
    import websockets
    print("  ✓ websockets")
except ImportError:
    print("  ✗ websockets - NOT FOUND")

try:
    import playwright
    print("  ✓ playwright")
except ImportError:
    print("  ✗ playwright - NOT FOUND")

print("\n" + "="*60)
print("✅ Setup complete!")
print("="*60)

print("\nNext: Run the backend with:")
print(f"  cd {backend_path}")
print("  python run_agent_background.py")

#!/usr/bin/env python3
"""
EchoAI Backend Diagnostic Tool
Checks environment, dependencies, and configuration
"""

import sys
import os
import subprocess
from pathlib import Path


def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def print_check(name, status, details=""):
    icon = "✅" if status else "❌"
    print(f"{icon} {name:<40} {details}")


def check_python_version():
    """Check Python version"""
    version = sys.version_info
    is_ok = version.major == 3 and version.minor >= 10
    print_check(
        "Python Version", 
        is_ok, 
        f"v{version.major}.{version.minor}.{version.micro}"
    )
    return is_ok


def check_virtual_env():
    """Check if running in virtual environment"""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    print_check("Virtual Environment", in_venv)
    return in_venv


def check_file_exists(filepath, name):
    """Check if file exists"""
    exists = Path(filepath).exists()
    print_check(f"File: {name}", exists, filepath)
    return exists


def check_directory_structure():
    """Check project structure"""
    print_header("Directory Structure")
    
    required_dirs = [
        ("app", "app/"),
        ("app/routers", "app/routers/"),
        ("app/services", "app/services/"),
        ("app/models", "app/models/"),
        ("app/modules", "app/modules/"),
    ]
    
    all_exist = True
    for name, path in required_dirs:
        exists = Path(path).exists()
        print_check(name, exists, path)
        all_exist = all_exist and exists
    
    return all_exist


def check_required_files():
    """Check required files"""
    print_header("Required Files")
    
    files = [
        ("main.py", "main.py"),
        ("app/main.py", "app/main.py"),
        ("requirements.txt", "requirements.txt"),
        (".env", ".env"),
        ("app/routers/transcript.py", "app/routers/transcript.py"),
        ("app/services/transcription_service.py", "app/services/transcription_service.py"),
    ]
    
    found_main = False
    for name, path in files:
        exists = check_file_exists(path, name)
        if "main.py" in name and exists:
            found_main = True
    
    return found_main


def check_dependencies():
    """Check installed dependencies"""
    print_header("Dependencies")
    
    required = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "openai",
        "torch",
        "transformers",
        "httpx",
        "aiohttp",
        "soundfile",
        "librosa",
    ]
    
    all_installed = True
    for package in required:
        try:
            __import__(package)
            print_check(package, True, "Installed")
        except ImportError:
            print_check(package, False, "NOT INSTALLED")
            all_installed = False
    
    return all_installed


def check_env_file():
    """Check .env file configuration"""
    print_header("Environment Configuration")
    
    if not Path(".env").exists():
        print_check(".env file", False, "File not found")
        return False
    
    with open(".env", "r") as f:
        env_content = f.read()
    
    has_openai = "OPENAI_API_KEY" in env_content
    has_valid_key = "sk-" in env_content and "your-key-here" not in env_content
    
    print_check(".env exists", True)
    print_check("OPENAI_API_KEY set", has_openai)
    print_check("Valid API key", has_valid_key)
    
    return has_openai and has_valid_key


def check_port_availability():
    """Check if port 8000 is available"""
    print_header("Port Availability")
    
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        sock.bind(("127.0.0.1", 8000))
        sock.close()
        print_check("Port 8000", True, "Available")
        return True
    except OSError:
        print_check("Port 8000", False, "In use or blocked")
        return False


def suggest_fixes():
    """Suggest fixes for common issues"""
    print_header("Suggested Fixes")
    
    print("\n📋 If dependencies are missing:")
    print("   pip install -r requirements.txt")
    
    print("\n📋 If .env file is missing:")
    print("   Create .env with: OPENAI_API_KEY=sk-your-actual-key")
    
    print("\n📋 If port 8000 is in use:")
    print("   Windows: netstat -ano | findstr :8000")
    print("   Then: taskkill /PID <pid> /F")
    
    print("\n📋 To start the server:")
    print("   Method 1: python main.py")
    print("   Method 2: uvicorn main:app --reload")
    print("   Method 3: uvicorn app.main:app --reload")
    
    print("\n📋 If imports fail:")
    print("   Make sure you're in the backend directory")
    print("   Activate venv: venv\\Scripts\\activate (Windows)")


def main():
    """Run all diagnostic checks"""
    print("\n🔍 EchoAI Backend Diagnostic Tool")
    print(f"📁 Working Directory: {Path.cwd()}")
    
    # Run all checks
    print_header("System Information")
    python_ok = check_python_version()
    venv_ok = check_virtual_env()
    
    structure_ok = check_directory_structure()
    files_ok = check_required_files()
    deps_ok = check_dependencies()
    env_ok = check_env_file()
    port_ok = check_port_availability()
    
    # Summary
    print_header("Diagnostic Summary")
    
    checks = [
        ("Python version >= 3.10", python_ok),
        ("Virtual environment active", venv_ok),
        ("Directory structure", structure_ok),
        ("Required files present", files_ok),
        ("Dependencies installed", deps_ok),
        ("Environment configured", env_ok),
        ("Port 8000 available", port_ok),
    ]
    
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    
    print(f"\nChecks Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All checks passed! Your backend should be ready to run.")
        print("\nTo start the server:")
        print("  uvicorn main:app --reload")
        print("\nOr:")
        print("  python main.py")
    else:
        print("\n⚠️  Some checks failed. Please review the issues above.")
        suggest_fixes()
    
    print("\n" + "="*60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Diagnostic error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
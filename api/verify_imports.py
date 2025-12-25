#!/usr/bin/env python3
"""Verify all required packages are installed"""

print("=" * 60)
print("🔍 VERIFYING PYTHON PACKAGES")
print("=" * 60)

required_packages = {
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn', 
    'pydantic': 'Pydantic',
    'stripe': 'Stripe',
    'resend': 'Resend',
    'dateutil': 'python-dateutil',
    'holidays': 'holidays',
    'jinja2': 'Jinja2',
    'psycopg2': 'Psycopg2',
    'dotenv': 'python-dotenv'
}

missing = []
installed = []

for module, name in required_packages.items():
    try:
        __import__(module)
        installed.append(name)
        print(f"✅ {name}")
    except ImportError:
        missing.append(name)
        print(f"❌ {name} - NOT INSTALLED")

print("=" * 60)
if missing:
    print(f"❌ MISSING {len(missing)} PACKAGES: {', '.join(missing)}")
    exit(1)
else:
    print(f"✅ ALL {len(installed)} PACKAGES INSTALLED")
    print("=" * 60)


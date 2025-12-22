#!/usr/bin/env python3
"""
Test script to verify PDF generation for all states in state_rules.json
Tests the /api/v1/guide/{state_code}/pdf endpoint
"""

import json
import requests
import sys
from pathlib import Path
from io import BytesIO

# Try to import PyPDF2 for PDF content validation (optional)
try:
    import PyPDF2
    PDF_VALIDATION_AVAILABLE = True
except ImportError:
    PDF_VALIDATION_AVAILABLE = False
    print("⚠️  PyPDF2 not installed. PDF content validation will be limited.")
    print("   Install with: pip install PyPDF2")

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your production URL if needed
STATE_RULES_FILE = Path("state_rules.json")

def load_state_rules():
    """Load state rules from JSON file"""
    try:
        with open(STATE_RULES_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {STATE_RULES_FILE} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {STATE_RULES_FILE}: {e}")
        sys.exit(1)

def validate_pdf_content(pdf_bytes, state_code, state_name):
    """Validate PDF content contains expected state information"""
    if not PDF_VALIDATION_AVAILABLE:
        return True, "PDF validation skipped (PyPDF2 not installed)"
    
    try:
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Extract text from first page
        if len(pdf_reader.pages) > 0:
            first_page_text = pdf_reader.pages[0].extract_text()
            
            # Check for state name
            if state_name.lower() not in first_page_text.lower():
                return False, f"State name '{state_name}' not found in PDF"
            
            # Check for common keywords
            keywords = ['deadline', 'lien', 'preliminary', 'notice']
            found_keywords = [kw for kw in keywords if kw.lower() in first_page_text.lower()]
            
            if len(found_keywords) < 2:
                return False, f"Expected keywords not found. Found: {found_keywords}"
            
            return True, f"PDF validated: Contains state name and {len(found_keywords)} keywords"
        else:
            return False, "PDF has no pages"
    except Exception as e:
        return False, f"PDF validation error: {str(e)}"

def test_pdf_generation(state_code, state_data):
    """Test PDF generation for a single state"""
    state_name = state_data.get('state_name', state_code)
    url = f"{BASE_URL}/api/v1/guide/{state_code}/pdf"
    
    try:
        # Make request
        response = requests.get(url, timeout=30)
        
        # Check HTTP status
        if response.status_code != 200:
            return {
                'state_code': state_code,
                'state_name': state_name,
                'status': 'FAILED',
                'http_status': response.status_code,
                'error': f"HTTP {response.status_code}: {response.text[:200]}",
                'file_size': 0
            }
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'application/pdf' not in content_type:
            return {
                'state_code': state_code,
                'state_name': state_name,
                'status': 'FAILED',
                'http_status': response.status_code,
                'error': f"Wrong content type: {content_type}",
                'file_size': len(response.content)
            }
        
        # Check file size
        file_size = len(response.content)
        if file_size == 0:
            return {
                'state_code': state_code,
                'state_name': state_name,
                'status': 'FAILED',
                'http_status': response.status_code,
                'error': "PDF file is empty (0 bytes)",
                'file_size': 0
            }
        
        # Validate PDF content
        is_valid, validation_msg = validate_pdf_content(response.content, state_code, state_name)
        
        if not is_valid:
            return {
                'state_code': state_code,
                'state_name': state_name,
                'status': 'WARNING',
                'http_status': response.status_code,
                'error': validation_msg,
                'file_size': file_size
            }
        
        return {
            'state_code': state_code,
            'state_name': state_name,
            'status': 'SUCCESS',
            'http_status': response.status_code,
            'error': None,
            'file_size': file_size,
            'validation': validation_msg
        }
        
    except requests.exceptions.Timeout:
        return {
            'state_code': state_code,
            'state_name': state_name,
            'status': 'FAILED',
            'http_status': None,
            'error': "Request timeout (>30s)",
            'file_size': 0
        }
    except requests.exceptions.ConnectionError:
        return {
            'state_code': state_code,
            'state_name': state_name,
            'status': 'FAILED',
            'http_status': None,
            'error': f"Connection error: Could not connect to {BASE_URL}",
            'file_size': 0
        }
    except Exception as e:
        return {
            'state_code': state_code,
            'state_name': state_name,
            'status': 'FAILED',
            'http_status': None,
            'error': f"Unexpected error: {str(e)}",
            'file_size': 0
        }

def main():
    """Main test function"""
    print("=" * 70)
    print("PDF Generation Test Script")
    print("=" * 70)
    print(f"Testing endpoint: {BASE_URL}/api/v1/guide/{{state_code}}/pdf")
    print(f"State rules file: {STATE_RULES_FILE}")
    print()
    
    # Load state rules
    print("📖 Loading state rules...")
    state_rules = load_state_rules()
    state_codes = sorted(state_rules.keys())
    total_states = len(state_codes)
    
    print(f"✅ Found {total_states} states: {', '.join(state_codes)}")
    print()
    
    # Test each state
    results = []
    print("🧪 Testing PDF generation for each state...")
    print()
    
    for i, state_code in enumerate(state_codes, 1):
        state_data = state_rules[state_code]
        print(f"[{i}/{total_states}] Testing {state_code} ({state_data.get('state_name', state_code)})...", end=' ', flush=True)
        
        result = test_pdf_generation(state_code, state_data)
        results.append(result)
        
        if result['status'] == 'SUCCESS':
            print(f"✅ {result['file_size']:,} bytes")
        elif result['status'] == 'WARNING':
            print(f"⚠️  {result['file_size']:,} bytes - {result['error']}")
        else:
            print(f"❌ {result['error']}")
    
    print()
    print("=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    
    # Count results
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    warning_count = sum(1 for r in results if r['status'] == 'WARNING')
    failed_count = sum(1 for r in results if r['status'] == 'FAILED')
    
    print(f"✅ Success: {success_count}/{total_states}")
    print(f"⚠️  Warnings: {warning_count}/{total_states}")
    print(f"❌ Failed: {failed_count}/{total_states}")
    print()
    
    # Show failed states
    if failed_count > 0:
        print("FAILED STATES:")
        print("-" * 70)
        for result in results:
            if result['status'] == 'FAILED':
                print(f"  {result['state_code']} ({result['state_name']}): {result['error']}")
        print()
    
    # Show warning states
    if warning_count > 0:
        print("WARNING STATES:")
        print("-" * 70)
        for result in results:
            if result['status'] == 'WARNING':
                print(f"  {result['state_code']} ({result['state_name']}): {result['error']}")
        print()
    
    # File size statistics
    successful_results = [r for r in results if r['status'] in ['SUCCESS', 'WARNING']]
    if successful_results:
        file_sizes = [r['file_size'] for r in successful_results]
        avg_size = sum(file_sizes) / len(file_sizes)
        min_size = min(file_sizes)
        max_size = max(file_sizes)
        
        print("FILE SIZE STATISTICS:")
        print("-" * 70)
        print(f"  Average: {avg_size:,.0f} bytes ({avg_size/1024:.1f} KB)")
        print(f"  Min: {min_size:,} bytes ({min_size/1024:.1f} KB)")
        print(f"  Max: {max_size:,} bytes ({max_size/1024:.1f} KB)")
        print()
    
    # Final summary
    working_count = success_count + warning_count
    print("=" * 70)
    print(f"FINAL RESULT: {working_count}/{total_states} PDFs working correctly")
    print("=" * 70)
    
    # Exit code
    if failed_count > 0:
        sys.exit(1)
    elif warning_count > 0:
        sys.exit(0)  # Warnings are acceptable
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()


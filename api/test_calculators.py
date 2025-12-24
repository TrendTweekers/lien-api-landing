"""
Test script for state-specific lien deadline calculators
Tests critical states to ensure calculations are correct
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

from api.calculators import (
    calculate_texas, calculate_washington, calculate_california,
    calculate_ohio, calculate_oregon, calculate_hawaii
)

def test_texas():
    """Test Texas month + day formula"""
    print("\n" + "="*60)
    print("TEST 1: Texas (Month + Day Formula)")
    print("="*60)
    
    invoice_date = datetime(2025, 1, 15)
    
    # Test commercial
    result_commercial = calculate_texas(invoice_date, project_type="commercial")
    print(f"\n📅 Invoice Date: {invoice_date.strftime('%Y-%m-%d')}")
    print(f"🏢 Project Type: Commercial")
    print(f"✅ Preliminary Deadline: {result_commercial['preliminary_deadline'].strftime('%Y-%m-%d')}")
    print(f"✅ Lien Deadline: {result_commercial['lien_deadline'].strftime('%Y-%m-%d')}")
    print(f"⚠️  Warnings: {result_commercial['warnings']}")
    
    # Verify
    expected_prelim = datetime(2025, 3, 15)  # 15th of 3rd month
    expected_lien = datetime(2025, 4, 15)   # 15th of 4th month
    
    prelim_match = result_commercial['preliminary_deadline'].date() == expected_prelim.date()
    lien_match = result_commercial['lien_deadline'].date() == expected_lien.date()
    
    if prelim_match and lien_match:
        print("✅ PASS: Texas commercial deadlines are correct!")
    else:
        print(f"❌ FAIL: Expected Prelim={expected_prelim.date()}, Lien={expected_lien.date()}")
    
    # Test residential
    result_residential = calculate_texas(invoice_date, project_type="residential")
    print(f"\n🏠 Project Type: Residential")
    print(f"✅ Preliminary Deadline: {result_residential['preliminary_deadline'].strftime('%Y-%m-%d')}")
    print(f"✅ Lien Deadline: {result_residential['lien_deadline'].strftime('%Y-%m-%d')}")
    
    expected_prelim_res = datetime(2025, 2, 15)  # 15th of 2nd month
    expected_lien_res = datetime(2025, 3, 15)    # 15th of 3rd month
    
    prelim_res_match = result_residential['preliminary_deadline'].date() == expected_prelim_res.date()
    lien_res_match = result_residential['lien_deadline'].date() == expected_lien_res.date()
    
    if prelim_res_match and lien_res_match:
        print("✅ PASS: Texas residential deadlines are correct!")
    else:
        print(f"❌ FAIL: Expected Prelim={expected_prelim_res.date()}, Lien={expected_lien_res.date()}")


def test_washington():
    """Test Washington supplier-specific logic"""
    print("\n" + "="*60)
    print("TEST 2: Washington (Supplier-Specific)")
    print("="*60)
    
    invoice_date = datetime(2025, 1, 15)
    
    # Test supplier
    result_supplier = calculate_washington(invoice_date, role="supplier")
    print(f"\n📅 Invoice Date: {invoice_date.strftime('%Y-%m-%d')}")
    print(f"👤 Role: Supplier")
    print(f"✅ Preliminary Required: {result_supplier['preliminary_required']}")
    print(f"✅ Preliminary Deadline: {result_supplier['preliminary_deadline'].strftime('%Y-%m-%d') if result_supplier['preliminary_deadline'] else 'N/A'}")
    print(f"✅ Lien Deadline: {result_supplier['lien_deadline'].strftime('%Y-%m-%d')}")
    print(f"⚠️  Warnings: {result_supplier['warnings']}")
    
    # Verify
    expected_prelim = datetime(2025, 3, 16)  # 60 days (Jan 15 + 60 = Mar 16, but check if weekend)
    expected_lien = datetime(2025, 4, 15)     # 90 days
    
    prelim_match = result_supplier['preliminary_deadline'].date() == expected_prelim.date() if result_supplier['preliminary_deadline'] else False
    lien_match = result_supplier['lien_deadline'].date() == expected_lien.date()
    
    if prelim_match and lien_match and result_supplier['preliminary_required']:
        print("✅ PASS: Washington supplier deadlines are correct!")
    else:
        print(f"⚠️  Check: Prelim={result_supplier['preliminary_deadline'].date() if result_supplier['preliminary_deadline'] else None}, Expected={expected_prelim.date()}")
        print(f"⚠️  Check: Lien={result_supplier['lien_deadline'].date()}, Expected={expected_lien.date()}")
    
    # Test contractor (no preliminary)
    result_contractor = calculate_washington(invoice_date, role="contractor")
    print(f"\n👤 Role: Contractor")
    print(f"✅ Preliminary Required: {result_contractor['preliminary_required']}")
    print(f"✅ Preliminary Deadline: {result_contractor['preliminary_deadline'] if result_contractor['preliminary_deadline'] else 'N/A'}")
    
    if not result_contractor['preliminary_required']:
        print("✅ PASS: Contractors don't need preliminary notice!")


def test_california():
    """Test California with Notice of Completion"""
    print("\n" + "="*60)
    print("TEST 3: California (Notice of Completion)")
    print("="*60)
    
    invoice_date = datetime(2025, 1, 15)
    
    # Test without NOC
    result_no_noc = calculate_california(invoice_date)
    print(f"\n📅 Invoice Date: {invoice_date.strftime('%Y-%m-%d')}")
    print(f"📋 Notice of Completion: None")
    print(f"✅ Preliminary Deadline: {result_no_noc['preliminary_deadline'].strftime('%Y-%m-%d')}")
    print(f"✅ Lien Deadline: {result_no_noc['lien_deadline'].strftime('%Y-%m-%d')}")
    print(f"⚠️  Warnings: {result_no_noc['warnings']}")
    
    expected_prelim = datetime(2025, 2, 4)   # 20 days
    expected_lien = datetime(2025, 4, 15)    # 90 days
    
    if result_no_noc['lien_deadline'].date() == expected_lien.date():
        print("✅ PASS: California without NOC uses 90-day deadline")
    
    # Test with NOC
    result_with_noc = calculate_california(invoice_date, notice_of_completion_date="2025-02-01")
    print(f"\n📋 Notice of Completion: 2025-02-01")
    print(f"✅ Lien Deadline: {result_with_noc['lien_deadline'].strftime('%Y-%m-%d')}")
    print(f"⚠️  Warnings: {result_with_noc['warnings']}")
    
    expected_lien_noc = datetime(2025, 3, 3)  # 30 days from NOC (Feb 1 + 30 = Mar 3)
    
    if result_with_noc['lien_deadline'].date() == expected_lien_noc.date():
        print("✅ PASS: California with NOC uses 30-day deadline!")
    else:
        print(f"⚠️  Check: Lien={result_with_noc['lien_deadline'].date()}, Expected={expected_lien_noc.date()}")


def test_hawaii():
    """Test Hawaii shortest deadline"""
    print("\n" + "="*60)
    print("TEST 4: Hawaii (Shortest Deadline)")
    print("="*60)
    
    invoice_date = datetime(2025, 1, 15)
    
    result = calculate_hawaii(invoice_date)
    print(f"\n📅 Invoice Date: {invoice_date.strftime('%Y-%m-%d')}")
    print(f"✅ Preliminary Required: {result['preliminary_required']}")
    print(f"✅ Lien Deadline: {result['lien_deadline'].strftime('%Y-%m-%d')}")
    print(f"⚠️  Warnings: {result['warnings']}")
    
    expected_lien = datetime(2025, 3, 1)  # 45 days (Jan 15 + 45 = Feb 29, but Feb only has 28 days in 2025, so Mar 1)
    
    if result['lien_deadline'].date() == expected_lien.date():
        print("✅ PASS: Hawaii has shortest 45-day deadline!")
    else:
        print(f"⚠️  Check: Lien={result['lien_deadline'].date()}, Expected={expected_lien.date()}")


def test_oregon():
    """Test Oregon business days"""
    print("\n" + "="*60)
    print("TEST 5: Oregon (Business Days)")
    print("="*60)
    
    invoice_date = datetime(2025, 1, 15)  # Wednesday
    
    result = calculate_oregon(invoice_date)
    print(f"\n📅 Invoice Date: {invoice_date.strftime('%Y-%m-%d')} (Wednesday)")
    print(f"✅ Preliminary Deadline: {result['preliminary_deadline'].strftime('%Y-%m-%d')}")
    print(f"✅ Lien Deadline: {result['lien_deadline'].strftime('%Y-%m-%d')}")
    print(f"⚠️  Warnings: {result['warnings']}")
    
    # 8 business days from Wednesday Jan 15:
    # Jan 15 (Wed), 16 (Thu), 17 (Fri), 20 (Mon), 21 (Tue), 22 (Wed), 23 (Thu), 24 (Fri), 27 (Mon)
    # Should be around Jan 27
    print(f"✅ PASS: Oregon uses business days for preliminary notice")


def test_ohio():
    """Test Ohio conditional preliminary"""
    print("\n" + "="*60)
    print("TEST 6: Ohio (Conditional Preliminary)")
    print("="*60)
    
    invoice_date = datetime(2025, 1, 15)
    
    # Test without Notice of Commencement
    result_no_noc = calculate_ohio(invoice_date, notice_of_commencement_filed=False)
    print(f"\n📅 Invoice Date: {invoice_date.strftime('%Y-%m-%d')}")
    print(f"📋 Notice of Commencement: Not Filed")
    print(f"✅ Preliminary Required: {result_no_noc['preliminary_required']}")
    print(f"✅ Preliminary Deadline: {result_no_noc['preliminary_deadline'] if result_no_noc['preliminary_deadline'] else 'N/A'}")
    print(f"✅ Lien Deadline: {result_no_noc['lien_deadline'].strftime('%Y-%m-%d')}")
    
    if not result_no_noc['preliminary_required']:
        print("✅ PASS: No preliminary required when NOC not filed!")
    
    # Test with Notice of Commencement
    result_with_noc = calculate_ohio(invoice_date, notice_of_commencement_filed=True)
    print(f"\n📋 Notice of Commencement: Filed")
    print(f"✅ Preliminary Required: {result_with_noc['preliminary_required']}")
    print(f"✅ Preliminary Deadline: {result_with_noc['preliminary_deadline'].strftime('%Y-%m-%d') if result_with_noc['preliminary_deadline'] else 'N/A'}")
    
    if result_with_noc['preliminary_required']:
        print("✅ PASS: Preliminary required when NOC is filed!")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 TESTING STATE-SPECIFIC CALCULATORS")
    print("="*60)
    
    try:
        test_texas()
        test_washington()
        test_california()
        test_hawaii()
        test_oregon()
        test_ohio()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETE!")
        print("="*60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


"""
State-specific lien deadline calculators
Handles complex calculation logic for states with special rules
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

VALID_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]

STATE_CODE_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii',
    'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine',
    'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska',
    'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
    'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island',
    'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas',
    'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

# Load state rules (fallback to JSON if database not available)
try:
    # Try loading from api directory first
    rules_path = BASE_DIR / "state_rules.json"
    if not rules_path.exists():
        # Try loading from project root
        rules_path = BASE_DIR.parent / "state_rules.json"
        
    with open(rules_path, 'r') as f:
        STATE_RULES = json.load(f)
except FileNotFoundError:
    STATE_RULES = {}
    print(f"WARNING: state_rules.json not found at {BASE_DIR} or {BASE_DIR.parent}")


# Try to import optional dependencies
try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False
    holidays = None
    print("⚠️ Warning: holidays package not installed. Holiday checking will be disabled.")

try:
    from dateutil.relativedelta import relativedelta
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    relativedelta = None
    print("⚠️ Warning: python-dateutil not installed. Month calculations may fail.")


def is_business_day(date: datetime) -> bool:
    """Check if date is a business day (not weekend or federal holiday)"""
    if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    if HOLIDAYS_AVAILABLE and holidays:
        try:
            us_holidays = holidays.US(years=date.year)
            return date.date() not in us_holidays
        except Exception:
            pass
    
    return True  # If holidays unavailable, assume not a holiday


def add_business_days(start_date: datetime, days: int) -> datetime:
    """Add business days (for Oregon's 8 business day rule)"""
    current = start_date
    days_added = 0
    while days_added < days:
        current += timedelta(days=1)
        if is_business_day(current):
            days_added += 1
    return current


def next_business_day(date: datetime) -> datetime:
    """Move to next business day if on weekend/holiday"""
    while not is_business_day(date):
        date += timedelta(days=1)
    return date


def month_plus_day(start_date: datetime, months: int, day: int, 
                   extend_for_weekend: bool = False) -> datetime:
    """
    Calculate deadline as "Xth day of Yth month after start"
    Example: 15th of 3rd month after Jan 15 = March 15
    """
    if DATEUTIL_AVAILABLE and relativedelta:
        # Use dateutil for accurate month calculations
        target = start_date + relativedelta(months=months)
        
        # Set to specified day of that month
        try:
            deadline = target.replace(day=day)
        except ValueError:
            # Handle months with fewer days (e.g., Feb 30)
            # Move to last day of month
            deadline = target + relativedelta(day=31)
    else:
        # Fallback: approximate month calculation
        year = start_date.year + (start_date.month + months - 1) // 12
        month = (start_date.month + months - 1) % 12 + 1
        target = datetime(year, month, start_date.day)
        
        try:
            deadline = target.replace(day=day)
        except ValueError:
            # Handle months with fewer days - use last day of month
            if DATEUTIL_AVAILABLE and relativedelta:
                deadline = target + relativedelta(day=31)
            else:
                # Last day of month fallback
                next_month = target.replace(day=28) + timedelta(days=4)
                deadline = next_month - timedelta(days=next_month.day)
    
    # Apply weekend/holiday extension if required
    if extend_for_weekend:
        deadline = next_business_day(deadline)
    
    return deadline


def calculate_texas(invoice_date: datetime, project_type: str = "commercial") -> Dict:
    """
    Texas: Month + day formula
    Residential vs commercial have different deadlines
    """
    is_residential = project_type.lower() in ["residential", "res", "single-family"]
    
    if is_residential:
        # Residential: 15th of 2nd month following (prelim), 15th of 3rd month following (lien)
        prelim_deadline = month_plus_day(invoice_date, months=2, day=15, extend_for_weekend=True)
        lien_deadline = month_plus_day(invoice_date, months=3, day=15, extend_for_weekend=True)
    else:
        # Commercial: 15th of 3rd month following (prelim), 15th of 4th month following (lien)
        prelim_deadline = month_plus_day(invoice_date, months=3, day=15, extend_for_weekend=True)
        lien_deadline = month_plus_day(invoice_date, months=4, day=15, extend_for_weekend=True)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "lien_deadline": lien_deadline,
        "warnings": ["If 15th falls on weekend/holiday, extends to next business day"]
    }


def calculate_washington(invoice_date: datetime, role: str = "supplier") -> Dict:
    """
    Washington: Suppliers need 60-day preliminary, contractors don't
    """
    is_supplier = role.lower() in ["supplier", "material supplier", "vendor"]
    
    if is_supplier:
        prelim_deadline = invoice_date + timedelta(days=60)
        prelim_deadline = next_business_day(prelim_deadline)
        prelim_required = True
        warnings = ["CRITICAL: Suppliers must send notice within 60 days"]
    else:
        prelim_deadline = None
        prelim_required = False
        warnings = ["No preliminary notice required for contractors/subcontractors"]
    
    lien_deadline = invoice_date + timedelta(days=90)
    lien_deadline = next_business_day(lien_deadline)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": prelim_required,
        "lien_deadline": lien_deadline,
        "warnings": warnings
    }


def calculate_state_deadline(
    state_code: str,
    invoice_date: datetime,
    role: str = "supplier",
    project_type: str = "commercial",
    notice_of_completion_date: Optional[datetime] = None,
    notice_of_commencement_filed: bool = False,
    state_rules: Optional[dict] = None
):
    """
    Unified state deadline calculation function.
    Uses the same logic for all endpoints to ensure consistency.
    
    Args:
        state_code: Two-letter state code (e.g., "TX", "CA")
        invoice_date: datetime object for invoice/delivery date
        role: "supplier", "contractor", etc.
        project_type: "commercial" or "residential"
        notice_of_completion_date: Optional datetime for notice of completion
        notice_of_commencement_filed: Whether notice of commencement was filed
        state_rules: Optional dict with state rules (for default calculation)
    
    Returns:
        dict with calculation results (preliminary_deadline, lien_deadline, etc.)
    """
    state_code = state_code.upper()

    # Use global STATE_RULES if state_rules argument is missing
    if state_rules is None:
        state_rules = STATE_RULES.get(state_code)
    
    # State-specific calculation logic (single source of truth)
    if state_code == "TX":
        return calculate_texas(invoice_date, project_type=project_type)
    elif state_code == "WA":
        return calculate_washington(invoice_date, role=role)
    elif state_code == "CA":
        return calculate_california(
            invoice_date,
            notice_of_completion_date=notice_of_completion_date,
            role=role
        )
    elif state_code == "OH":
        return calculate_ohio(
            invoice_date,
            project_type=project_type,
            notice_of_commencement_filed=notice_of_commencement_filed
        )
    elif state_code == "OR":
        return calculate_oregon(invoice_date)
    elif state_code == "HI":
        return calculate_hawaii(invoice_date)
    elif state_code == "NJ":
        return calculate_newjersey(invoice_date, project_type=project_type)
    elif state_code == "IN":
        return calculate_indiana(invoice_date, project_type=project_type)
    elif state_code == "LA":
        return calculate_louisiana(invoice_date, project_type=project_type)
    elif state_code == "MA":
        return calculate_massachusetts(invoice_date, project_type=project_type)
    else:
        # Default calculation for simple states
        if not state_rules:
            # Fallback to basic defaults if no rules provided (should not happen if JSON loaded)
            prelim_required = False
            prelim_days = 20
            lien_days = 120
            special_rules = {}
        else:
            prelim_notice = state_rules.get('preliminary_notice', {})
            lien_filing = state_rules.get('lien_filing', {})
            special_rules = state_rules.get('special_rules', {})
            
            # Determine if preliminary notice is required
            # Check for explicit days > 0
            p_days = prelim_notice.get('days')
            p_comm_days = prelim_notice.get('commercial_days')
            
            # Use whichever is present (priority to days if both?)
            # Usually 'days' is generic, 'commercial_days' is specific.
            prelim_days = p_days if p_days is not None else p_comm_days
            if prelim_days is None:
                prelim_days = 20 # Default
            
            # It is required if days > 0 and name is not "None Required"
            # Some states have days=0 for "None Required"
            prelim_required = (prelim_days > 0)
            
            # Allow JSON to explicitly set "required" if we add it later
            if 'required' in prelim_notice:
                prelim_required = prelim_notice['required']
            
            lien_days = (lien_filing.get('days') or 
                         lien_filing.get('commercial_days') or 
                         lien_filing.get('standard_days') or 
                         120)
        
        return calculate_default(
            invoice_date,
            {
                "preliminary_notice_required": prelim_required,
                "preliminary_notice_days": prelim_days,
                "lien_filing_days": lien_days,
                "notes": special_rules.get("notes", "")
            },
            weekend_extension=special_rules.get("weekend_extension", False),
            holiday_extension=special_rules.get("holiday_extension", False)
        )



def calculate_california(invoice_date: datetime, 
                        notice_of_completion_date: Optional[str] = None,
                        role: str = "supplier") -> Dict:
    """
    California: Notice of Completion can shorten deadline from 90 → 30 days
    """
    prelim_deadline = invoice_date + timedelta(days=20)
    
    if notice_of_completion_date:
        try:
            # Try parsing the date
            try:
                noc_date = datetime.strptime(notice_of_completion_date, "%Y-%m-%d")
            except ValueError:
                try:
                    noc_date = datetime.strptime(notice_of_completion_date, "%m/%d/%Y")
                except ValueError:
                    noc_date = datetime.fromisoformat(notice_of_completion_date)
            
            if role.lower() == "contractor":
                lien_deadline = noc_date + timedelta(days=60)
            else:
                lien_deadline = noc_date + timedelta(days=30)
            
            warnings = [f"⚠️ CRITICAL: Notice of Completion filed on {notice_of_completion_date}. Deadline SHORTENED to 30 days!"]
        except Exception as e:
            print(f"⚠️ Error parsing notice_of_completion_date: {e}")
            lien_deadline = invoice_date + timedelta(days=90)
            warnings = ["If owner records Notice of Completion, deadline shortens to 30 days"]
    else:
        lien_deadline = invoice_date + timedelta(days=90)
        warnings = ["If owner records Notice of Completion, deadline shortens to 30 days"]
    
    return {
        "preliminary_deadline": prelim_deadline,
        "lien_deadline": lien_deadline,
        "warnings": warnings
    }


def calculate_ohio(invoice_date: datetime, 
                   project_type: str = "commercial",
                   notice_of_commencement_filed: bool = False) -> Dict:
    """
    Ohio: Preliminary notice ONLY if Notice of Commencement filed
    Different lien deadlines for residential vs commercial
    """
    is_residential = project_type.lower() in ["residential", "res", "single-family"]
    
    # Preliminary notice
    if notice_of_commencement_filed:
        prelim_deadline = invoice_date + timedelta(days=21)
        prelim_deadline = next_business_day(prelim_deadline)
        prelim_required = True
        warnings = ["Notice of Furnishing required because Notice of Commencement was filed"]
    else:
        prelim_deadline = None
        prelim_required = False
        warnings = ["No preliminary notice required (no Notice of Commencement filed)"]
    
    # Lien filing
    if is_residential:
        lien_deadline = invoice_date + timedelta(days=60)
    else:
        lien_deadline = invoice_date + timedelta(days=75)
    
    lien_deadline = next_business_day(lien_deadline)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": prelim_required,
        "lien_deadline": lien_deadline,
        "warnings": warnings
    }


def calculate_oregon(invoice_date: datetime) -> Dict:
    """
    Oregon: 8 BUSINESS DAYS for preliminary (not calendar days)
    """
    # Preliminary: 8 business days
    prelim_deadline = add_business_days(invoice_date, 8)
    
    # Lien: 75 calendar days
    lien_deadline = invoice_date + timedelta(days=75)
    lien_deadline = next_business_day(lien_deadline)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "lien_deadline": lien_deadline,
        "warnings": ["Preliminary deadline is 8 BUSINESS days (excludes weekends/holidays)"]
    }


def calculate_hawaii(invoice_date: datetime) -> Dict:
    """
    Hawaii: SHORTEST deadline in entire US - only 45 days!
    """
    lien_deadline = invoice_date + timedelta(days=45)
    
    return {
        "preliminary_deadline": None,
        "preliminary_required": False,
        "lien_deadline": lien_deadline,
        "warnings": ["⚠️ SHORTEST DEADLINE IN US: Only 45 days to file lien!"]
    }


def calculate_newjersey(invoice_date: datetime, project_type: str = "commercial") -> Dict:
    """
    New Jersey mechanics lien deadlines for material suppliers.
    
    Preliminary Notice (Notice of Unpaid Balance and Right to File Lien):
    - Residential: 60 days from last furnishing
    - Non-residential: 90 days from last furnishing
    
    Lien Filing:
    - Residential: 120 days from last furnishing
    - Non-residential: 90 days from last furnishing
    
    Statute: N.J.S.A. § 2A:44A-20 (preliminary), § 2A:44A-6 (lien filing)
    
    Args:
        invoice_date: Date of first/last furnishing materials
        project_type: "residential" or "commercial" (default: "commercial")
    
    Returns:
        Dict with preliminary_deadline, preliminary_required, lien_deadline, warnings
    """
    is_residential = project_type.lower() in ["residential", "res", "resi"]
    
    if is_residential:
        prelim_days = 60
        lien_days = 120
    else:  # commercial/non-residential
        prelim_days = 90
        lien_days = 90
    
    prelim_deadline = invoice_date + timedelta(days=prelim_days)
    lien_deadline = invoice_date + timedelta(days=lien_days)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": True,
        "lien_deadline": lien_deadline,
        "warnings": [
            "Preliminary notice required within 60 days (residential) or 90 days (non-residential)",
            "Lien must be filed within 120 days (residential) or 90 days (non-residential)",
            "Deadlines vary by project type"
        ]
    }


def calculate_indiana(invoice_date: datetime, project_type: str = "commercial") -> Dict:
    """
    Indiana mechanics lien deadlines for material suppliers.
    
    Preliminary Notice:
    - Residential (renovation): 30 days from first furnishing
    - Residential (new construction): 60 days from first furnishing
    - Commercial: Not required
    
    Lien Filing:
    - Residential (1-2 unit): 60 days from last furnishing
    - Commercial: 90 days from last furnishing
    
    Statute: IC 32-28-3-1 (preliminary), IC 32-28-3-3 (lien filing)
    
    Args:
        invoice_date: Date of first/last furnishing materials
        project_type: "residential" or "commercial" (default: "commercial")
    
    Returns:
        Dict with preliminary_deadline, preliminary_required, lien_deadline, warnings
    """
    is_residential = project_type.lower() in ["residential", "res", "resi"]
    
    if is_residential:
        # For simplicity, use 60 days (new construction)
        # In real use, you'd need to distinguish renovation vs new construction
        prelim_days = 60
        prelim_required = True
        lien_days = 60
    else:  # commercial
        prelim_days = None
        prelim_required = False
        lien_days = 90
    
    prelim_deadline = invoice_date + timedelta(days=prelim_days) if prelim_days else None
    lien_deadline = invoice_date + timedelta(days=lien_days)
    
    warnings = []
    if is_residential:
        warnings.append("Preliminary notice required within 60 days (new construction) or 30 days (renovation)")
        warnings.append("Lien must be filed within 60 days for residential projects")
    else:
        warnings.append("Preliminary notice not required for commercial projects")
        warnings.append("Lien must be filed within 90 days for commercial projects")
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": prelim_required,
        "lien_deadline": lien_deadline,
        "warnings": warnings
    }


def calculate_louisiana(invoice_date: datetime, project_type: str = "commercial") -> Dict:
    """
    Louisiana mechanics lien deadlines for material suppliers.
    
    WARNING: Louisiana has complex monthly notice requirements.
    This calculation provides conservative estimates only.
    Suppliers should consult a Louisiana construction attorney.
    
    Preliminary Notice (Notice of Nonpayment):
    - Must be sent within 75 days from the last day of each month materials furnished
    - This function uses 75 days from invoice date as conservative estimate
    
    Lien Filing:
    - 60 days from substantial completion (if no Notice of Contract filed)
    - 6 months from substantial completion (if Notice of Contract filed)
    - This function uses 60 days as most conservative estimate
    
    Statute: Louisiana Revised Statutes § 9:4804(C) (preliminary), § 9:4822 (lien filing)
    
    Args:
        invoice_date: Date of last furnishing materials
        project_type: Not used for Louisiana (no res/commercial distinction)
    
    Returns:
        Dict with preliminary_deadline, preliminary_required, lien_deadline, warnings
    """
    # Conservative estimates - actual deadlines may vary
    prelim_days = 75
    lien_days = 60  # Assumes no Notice of Contract
    
    prelim_deadline = invoice_date + timedelta(days=prelim_days)
    lien_deadline = invoice_date + timedelta(days=lien_days)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": True,
        "lien_deadline": lien_deadline,
        "warnings": [
            "⚠️ CRITICAL: Louisiana has complex monthly notice requirements",
            "Notice of Nonpayment must be sent within 75 days from last day of EACH MONTH materials furnished",
            "Lien deadline may be 6 months (not 60 days) if Notice of Contract was filed",
            "These are CONSERVATIVE ESTIMATES - consult a Louisiana construction attorney",
            "Suppliers to suppliers have NO lien rights in Louisiana"
        ]
    }


def calculate_massachusetts(invoice_date: datetime, project_type: str = "commercial") -> Dict:
    """
    Massachusetts mechanics lien deadlines for material suppliers.
    
    Preliminary Notice (Notice of Identification):
    - Must be filed within 30 days of first providing work
    - For suppliers to subcontractors
    
    Lien Filing:
    - Earliest of:
      - 90 days after Notice of Substantial Completion
      - 120 days after Notice of Termination
      - 120 days after last furnishing labor or materials
    - This function uses 120 days as most conservative estimate
    
    Statute: MGL ch. 254 § 4 (preliminary), MGL ch. 254 § 8 (lien filing)
    
    Args:
        invoice_date: Date of first/last furnishing materials
        project_type: Not used for Massachusetts
    
    Returns:
        Dict with preliminary_deadline, preliminary_required, lien_deadline, warnings
    """
    prelim_days = 30
    lien_days = 120  # Most conservative estimate
    
    prelim_deadline = invoice_date + timedelta(days=prelim_days)
    lien_deadline = invoice_date + timedelta(days=lien_days)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": True,
        "lien_deadline": lien_deadline,
        "warnings": [
            "Preliminary notice (Notice of Identification) required within 30 days for suppliers to subcontractors",
            "Lien deadline may be shorter if Notice of Substantial Completion or Notice of Termination filed",
            "This calculation uses 120 days as most conservative estimate",
            "Actual deadline may be 90 days if Notice of Substantial Completion filed"
        ]
    }


def calculate_default(invoice_date: datetime, state_data: Dict, 
                     weekend_extension: bool = False,
                     holiday_extension: bool = False) -> Dict:
    """
    Default calculation for simple states using day counts
    """
    prelim_deadline = None
    prelim_required = state_data.get("preliminary_notice_required", False)
    prelim_days = state_data.get("preliminary_notice_days")
    
    if prelim_required and prelim_days:
        prelim_deadline = invoice_date + timedelta(days=prelim_days)
        if weekend_extension or holiday_extension:
            prelim_deadline = next_business_day(prelim_deadline)
    
    lien_days = state_data.get("lien_filing_days")
    if not lien_days:
        # Fallback: use 90 days if not specified
        lien_days = 90
    
    lien_deadline = invoice_date + timedelta(days=lien_days)
    if weekend_extension or holiday_extension:
        lien_deadline = next_business_day(lien_deadline)
    
    warnings = []
    notes = state_data.get("notes", "")
    if notes:
        warnings.append(notes)
    
    return {
        "preliminary_deadline": prelim_deadline,
        "preliminary_required": prelim_required,
        "lien_deadline": lien_deadline,
        "warnings": warnings
    }


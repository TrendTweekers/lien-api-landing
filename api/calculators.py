"""
State-specific lien deadline calculators
Handles complex calculation logic for states with special rules
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
try:
    import holidays
except ImportError:
    holidays = None
    print("⚠️ Warning: holidays package not installed. Holiday checking will be disabled.")

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    relativedelta = None
    print("⚠️ Warning: python-dateutil not installed. Month calculations may fail.")


def is_business_day(date: datetime) -> bool:
    """Check if date is a business day (not weekend or federal holiday)"""
    if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    if holidays:
        try:
            us_holidays = holidays.US(years=date.year)
            return date.date() not in us_holidays
        except Exception:
            pass
    
    return True


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
    if not relativedelta:
        # Fallback: approximate with days (less accurate)
        approx_days = months * 30
        deadline = start_date + timedelta(days=approx_days)
        # Try to set day
        try:
            deadline = deadline.replace(day=day)
        except ValueError:
            # If day doesn't exist in that month, use last day
            if day > 28:
                deadline = deadline.replace(day=28)
    else:
        # Add months
        target = start_date + relativedelta(months=months)
        
        # Set to specified day of that month
        try:
            deadline = target.replace(day=day)
        except ValueError:
            # Handle months with fewer days (e.g., Feb 30)
            # Move to last day of month
            deadline = target + relativedelta(day=31)
    
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
        # Residential: 15th of 2nd month (prelim), 15th of 3rd month (lien)
        prelim_deadline = month_plus_day(invoice_date, months=1, day=15, extend_for_weekend=True)
        lien_deadline = month_plus_day(invoice_date, months=2, day=15, extend_for_weekend=True)
    else:
        # Commercial: 15th of 3rd month (prelim), 15th of 4th month (lien)
        prelim_deadline = month_plus_day(invoice_date, months=2, day=15, extend_for_weekend=True)
        lien_deadline = month_plus_day(invoice_date, months=3, day=15, extend_for_weekend=True)
    
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


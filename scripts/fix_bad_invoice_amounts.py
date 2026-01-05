#!/usr/bin/env python3
"""
Fix bad invoice_amount values in the calculations table.

This script identifies records where invoice_amount >= 10000 (dollars),
which are likely cents that were incorrectly stored as dollars.

Usage:
    # Dry run (default - shows what would be changed)
    python scripts/fix_bad_invoice_amounts.py
    
    # Apply changes
    python scripts/fix_bad_invoice_amounts.py --apply
"""

import os
import sys
import argparse
from pathlib import Path
from decimal import Decimal

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import get_db, get_db_cursor, DB_TYPE


def check_table_has_column(conn, table_name, column_name):
    """Check if table has the specified column"""
    cursor = get_db_cursor(conn)
    if DB_TYPE == 'postgresql':
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))
        return cursor.fetchone() is not None
    else:
        # SQLite: PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        columns = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                columns.append(row[1])  # name is at index 1
            elif hasattr(row, 'keys'):  # sqlite3.Row
                columns.append(row['name'])
            else:
                columns.append(row[1] if len(row) > 1 else None)
        return column_name in columns


def find_bad_invoice_amounts():
    """Find all records with invoice_amount >= 10000"""
    with get_db() as conn:
        # Check if invoice_amount column exists
        if not check_table_has_column(conn, 'calculations', 'invoice_amount'):
            raise ValueError(
                "The calculations table does not have an 'invoice_amount' column. "
                "This script is designed for the production database schema with invoice_amount, "
                "project_name, client_name, etc. Your local database may have an older schema."
            )
        
        cursor = get_db_cursor(conn)
        
        if DB_TYPE == 'postgresql':
            # PostgreSQL query
            cursor.execute("""
                SELECT 
                    id,
                    invoice_amount,
                    project_name,
                    client_name,
                    invoice_date,
                    state_code
                FROM calculations
                WHERE invoice_amount >= 10000
                ORDER BY id
            """)
        else:
            # SQLite query
            cursor.execute("""
                SELECT 
                    id,
                    invoice_amount,
                    project_name,
                    client_name,
                    invoice_date,
                    state_code
                FROM calculations
                WHERE invoice_amount >= 10000
                ORDER BY id
            """)
        
        rows = cursor.fetchall()
        
        # Convert to list of dicts for consistent handling
        results = []
        for row in rows:
            if isinstance(row, dict):
                results.append({
                    'id': row.get('id'),
                    'invoice_amount': float(row.get('invoice_amount', 0)) if row.get('invoice_amount') else None,
                    'project_name': row.get('project_name') or '',
                    'client_name': row.get('client_name') or '',
                    'invoice_date': row.get('invoice_date') or '',
                    'state_code': row.get('state_code') or '',
                })
            else:
                # SQLite tuple
                results.append({
                    'id': row[0] if len(row) > 0 else None,
                    'invoice_amount': float(row[1]) if len(row) > 1 and row[1] else None,
                    'project_name': row[2] if len(row) > 2 else '',
                    'client_name': row[3] if len(row) > 3 else '',
                    'invoice_date': row[4] if len(row) > 4 else '',
                    'state_code': row[5] if len(row) > 5 else '',
                })
        
        return results


def update_invoice_amount(record_id: int, new_amount: float):
    """Update invoice_amount for a specific record"""
    with get_db() as conn:
        cursor = get_db_cursor(conn)
        
        if DB_TYPE == 'postgresql':
            cursor.execute("""
                UPDATE calculations
                SET invoice_amount = %s
                WHERE id = %s
            """, (new_amount, record_id))
        else:
            cursor.execute("""
                UPDATE calculations
                SET invoice_amount = ?
                WHERE id = ?
            """, (new_amount, record_id))
        
        conn.commit()


def print_summary_table(records, applied=False):
    """Print a formatted summary table"""
    if not records:
        print("✅ No records found with invoice_amount >= 10000")
        return
    
    print(f"\n{'=' * 100}")
    print(f"{'SUMMARY TABLE' + (' (APPLIED)' if applied else ' (DRY RUN)')}")
    print(f"{'=' * 100}")
    print(f"{'ID':<6} {'Old Amount':<15} {'New Amount':<15} {'Project Name':<30} {'Client Name':<25}")
    print(f"{'-' * 100}")
    
    for record in records:
        old = record['old_amount']
        new = record['new_amount']
        project_name = (record['project_name'] or '')[:28]
        client_name = (record['client_name'] or '')[:23]
        
        print(f"{record['id']:<6} ${old:<14,.2f} ${new:<14,.2f} {project_name:<30} {client_name:<25}")
    
    print(f"{'=' * 100}")
    print(f"Total records: {len(records)}")
    if not applied:
        print("\n⚠️  This is a DRY RUN. No changes were made.")
        print("   Run with --apply to perform updates.")


def main():
    parser = argparse.ArgumentParser(
        description='Fix bad invoice_amount values (cents stored as dollars)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/fix_bad_invoice_amounts.py          # Dry run
  python scripts/fix_bad_invoice_amounts.py --apply  # Apply changes
        """
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply the changes (default is dry-run)'
    )
    
    args = parser.parse_args()
    
    print("=" * 100)
    print("FIX BAD INVOICE AMOUNTS")
    print("=" * 100)
    print(f"Database Type: {DB_TYPE}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print("=" * 100)
    
    # Find bad records
    print("\n🔍 Searching for records with invoice_amount >= 10000...")
    records = find_bad_invoice_amounts()
    
    if not records:
        print("✅ No records found with invoice_amount >= 10000")
        return
    
    print(f"📊 Found {len(records)} record(s) to fix\n")
    
    # Prepare update data
    updates = []
    for record in records:
        old_amount = record['invoice_amount']
        # Divide by 100 to convert cents (stored as dollars) back to dollars
        new_amount = float(Decimal(str(old_amount)) / Decimal('100'))
        
        updates.append({
            'id': record['id'],
            'old_amount': old_amount,
            'new_amount': new_amount,
            'project_name': record['project_name'],
            'client_name': record['client_name'],
        })
    
    # Print summary table
    print_summary_table(updates, applied=False)
    
    # Apply changes if requested
    if args.apply:
        print("\n🔄 Applying changes...")
        for update in updates:
            try:
                update_invoice_amount(update['id'], update['new_amount'])
                print(f"✅ Updated record {update['id']}: ${update['old_amount']:,.2f} → ${update['new_amount']:,.2f}")
            except Exception as e:
                print(f"❌ Error updating record {update['id']}: {e}")
        
        print("\n" + "=" * 100)
        print("✅ CHANGES APPLIED")
        print("=" * 100)
        print_summary_table(updates, applied=True)
    else:
        print("\n💡 To apply these changes, run:")
        print("   python scripts/fix_bad_invoice_amounts.py --apply")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


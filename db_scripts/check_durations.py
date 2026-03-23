#!/usr/bin/env python3
"""Check duration_minutes for all future bookings of a company."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from src.services.database import get_database

def main():
    company_id = int(sys.argv[1]) if len(sys.argv) > 1 else 19
    db = get_database()
    bookings = db.get_all_bookings(company_id=company_id)
    now = datetime.now()

    print(f"\nFuture bookings for company {company_id}:")
    print(f"{'ID':>5}  {'Duration':>8}  {'Branch':>10}  {'Status':>10}  {'Appointment Time':>20}  {'Service':>25}  {'Customer'}")
    print("-" * 110)

    for b in bookings:
        appt = b.get('appointment_time')
        if not appt:
            continue
        if isinstance(appt, str):
            try:
                appt = datetime.fromisoformat(appt.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                continue
        if appt <= now:
            continue

        dur = b.get('duration_minutes', '?')
        status = b.get('status', '?')
        service = (b.get('service_type') or '')[:25]
        customer = b.get('client_name') or b.get('customer_name') or '?'

        # Which branch does this hit?
        if isinstance(dur, int):
            if dur > 1440:
                branch = "MULTI-DAY"
            elif dur >= 480:
                branch = "FULL-DAY"
            else:
                branch = "regular"
        else:
            branch = "?"

        print(f"{b['id']:>5}  {str(dur):>8}  {branch:>10}  {status:>10}  {appt.strftime('%Y-%m-%d %H:%M'):>20}  {service:>25}  {customer}")

if __name__ == '__main__':
    main()

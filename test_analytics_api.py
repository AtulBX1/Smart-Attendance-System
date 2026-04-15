#!/usr/bin/env python
"""Test script to verify analytics data loading works correctly."""

import sys
import os
import json

sys.path.insert(0, 'backend')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

print("=" * 60)
print("TESTING ANALYTICS DATA LOADING")
print("=" * 60)

# Test CSV loading
print("\n1. Testing CSV files...")
try:
    processed_path = os.path.join('data', 'processed', 'processed_attendance.csv')
    att_df = pd.read_csv(processed_path)
    print(f"   ✓ Loaded processed_attendance.csv: {len(att_df)} records")
    
    anomaly_path = os.path.join('data', 'processed', 'anomaly_results.csv')
    anom_df = pd.read_csv(anomaly_path)
    print(f"   ✓ Loaded anomaly_results.csv: {len(anom_df)} records")
except Exception as e:
    print(f"   ✗ ERROR: {e}")
    sys.exit(1)

# Test JSON loading
print("\n2. Testing JSON file...")
try:
    json_path = os.path.join('data', 'processed', 'analytics_synthetic.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    students = json_data.get('students', [])
    print(f"   ✓ Loaded analytics_synthetic.json: {len(students)} students")
    
    if students:
        s = students[0]
        print(f"\n   Sample student:")
        print(f"     - ID: {s.get('id')}")
        print(f"     - Name: {s.get('name')}")
        print(f"     - Score: {s.get('score')}%")
        print(f"     - Risk: {s.get('risk')}")
        print(f"     - Anomaly: {s.get('isAnomaly')}")
except Exception as e:
    print(f"   ✗ ERROR: {e}")
    sys.exit(1)

# Test risk distribution
print("\n3. Testing risk distribution extraction...")
try:
    distribution = {
        'critical': 0,
        'atrisk': 0,
        'watch': 0,
        'stable': 0,
        'exemplary': 0
    }
    
    for student in students:
        risk = student.get('risk', '').lower()
        if risk in distribution:
            distribution[risk] += 1
    
    print("   Risk Distribution:")
    for risk, count in distribution.items():
        print(f"     - {risk}: {count} students")
except Exception as e:
    print(f"   ✗ ERROR: {e}")
    sys.exit(1)

# Test anomaly filtering
print("\n4. Testing anomaly filtering...")
try:
    anomalies = [s for s in students if s.get('isAnomaly') == True]
    print(f"   ✓ Found {len(anomalies)} anomaly students")
except Exception as e:
    print(f"   ✗ ERROR: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED - Data loading working correctly!")
print("=" * 60)

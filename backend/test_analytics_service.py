#!/usr/bin/env python
"""
Test Script for Smart Attendance System Analytics Dashboard
Validates DBSCAN clustering and data processing
"""
import os
import sys
import json

# Add parent directory to path
base_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, 'backend'))

from backend.analytics_service import AnalyticsService

def test_analytics():
    print("🧪 Testing Analytics Service...")
    print("=" * 60)
    
    # Initialize service
    service = AnalyticsService(base_dir)
    print(f"\n✓ AnalyticsService initialized")
    print(f"  Data path: {service.data_path}")
    
    # Test 1: Load students
    print("\n📚 Test 1: Loading Student Data")
    try:
        students = service.get_students_with_synthetic_data()
        print(f"  ✓ Loaded {len(students)} students")
        print(f"    - Sample student: {students[0]['id']} ({students[0]['name']}) - Risk: {students[0]['risk']}")
        print(f"    - Score range: {min(s['score'] for s in students):.1f}% - {max(s['score'] for s in students):.1f}%")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Test 2: Risk distribution
    print("\n📊 Test 2: Risk Distribution")
    try:
        dist = service.get_risk_distribution()
        print(f"  ✓ Distribution calculated:")
        total = sum(dist.values())
        for risk, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            pct = (count/total)*100 if total > 0 else 0
            print(f"    - {risk.upper()}: {count} students ({pct:.1f}%)")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Test 3: Weekly trends
    print("\n📈 Test 3: Weekly Trends")
    try:
        trends = service.get_weekly_trends()
        print(f"  ✓ {len(trends)} weeks of trends calculated:")
        for trend in trends[:3]:
            print(f"    - {trend['week_label']}: {trend['avg_attendance']:.1f}% avg attendance")
        if len(trends) > 3:
            print(f"    - ... and {len(trends)-3} more weeks")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Test 4: DBSCAN Clustering (CRITICAL)
    print("\n🔬 Test 4: DBSCAN Anomaly Detection (CRITICAL)")
    try:
        result = service.perform_dbscan_clustering(eps=0.3, min_samples=5)
        stats = result['cluster_stats']
        print(f"  ✓ DBSCAN clustering completed:")
        print(f"    - Total points: {stats['total_points']}")
        print(f"    - Anomalies detected: {stats['anomaly_count']}")
        print(f"    - Normal clusters: {stats['normal_count']}")
        print(f"    - Contamination rate: {stats['contamination_rate']:.1f}%")
        print(f"    - Parameters: eps={stats['eps']}, min_samples={stats['min_samples']}")
        
        if stats['anomaly_count'] > 0:
            print(f"\n  📍 Top anomalies (by lowest score):")
            for anomaly in result['anomalies'][:3]:
                print(f"    - {anomaly['id']}: Score={anomaly['score']:.1f}%, Weekly Change={anomaly['y']:.1f}%")
        
        # Data validation
        print(f"\n  📊 Data validation:")
        for anomaly in result['anomalies'][:1]:
            print(f"    - Anomaly has 'x' (score): {anomaly.get('x')}")
            print(f"    - Anomaly has 'y' (weekly_change): {anomaly.get('y')}")
            print(f"    - Anomaly has 'normalized_score': {anomaly.get('normalized_score')}")
            print(f"    - Anomaly has 'clusterLabel': {anomaly.get('clusterLabel')}")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Critical, At-Risk, Watch, etc.
    print("\n🎯 Test 5: Risk Category Filtering")
    try:
        critical = service.get_critical_students(threshold=60)
        at_risk = service.get_at_risk_students()
        watch = service.get_watch_zone_students()
        stable = service.get_stable_students()
        exemplary = service.get_exemplary_students()
        
        print(f"  ✓ Risk categories filtered:")
        print(f"    - Critical (<60%): {len(critical)} students")
        print(f"    - At Risk (50-74%): {len(at_risk)} students")
        print(f"    - Watch Zone (75-79%): {len(watch)} students")
        print(f"    - Stable (75-89%): {len(stable)} students")
        print(f"    - Exemplary (≥90%): {len(exemplary)} students")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Test 6: Full Report
    print("\n📋 Test 6: Full Analytics Report")
    try:
        report = service.get_full_analytics_report()
        print(f"  ✓ Full report generated with sections:")
        print(f"    - timestamp: {report['timestamp']}")
        print(f"    - students: {len(report['students'])} total")
        print(f"    - distribution: {sum(report['distribution'].values())} total")
        print(f"    - weekly_trends: {len(report['weekly_trends'])} weeks")
        print(f"    - dbscan: {report['dbscan']['cluster_stats']['anomaly_count']} anomalies")
        print(f"    - critical: {len(report['critical'])} students")
        print(f"    - at_risk: {len(report['at_risk'])} students")
        print(f"    - watch_zone: {len(report['watch_zone'])} students")
        print(f"    - stable: {len(report['stable'])} students")
        print(f"    - exemplary: {len(report['exemplary'])} students")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_analytics()
    sys.exit(0 if success else 1)

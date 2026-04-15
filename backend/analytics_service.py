"""
Analytics Service for Smart Attendance System
Handles data loading, processing, and DBSCAN anomaly detection
"""
import os
import json
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from datetime import datetime, timedelta
import random

class AnalyticsService:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.data_path = os.path.join(base_dir, 'data', 'processed', 'analytics_synthetic.json')
        self._cache = {}
        self._cache_time = None
        
    def _load_synthetic_data(self):
        """Load synthetic data from JSON file"""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        print(f"📂 Loading data from: {self.data_path}")
        with open(self.data_path, 'r') as f:
            data = json.load(f)
        print(f"✓ Loaded {len(data.get('students', []))} students")
        return data
    
    def _generate_weekly_history(self, score):
        """Generate synthetic weekly history based on current score"""
        weeks = []
        # Base trend: weekly changes that average to the current score
        base_score = score
        for week in range(8):
            # Add some randomness while maintaining trend toward current score
            variance = random.uniform(-2, 2)
            weekly_score = max(0, min(100, base_score + variance))
            weeks.append(round(weekly_score, 1))
        return weeks
    
    def _generate_attendance_streak(self, score):
        """Generate attendance streak based on score"""
        if score >= 90:
            return random.randint(10, 32)  # Exemplary
        elif score >= 75:
            return random.randint(5, 15)   # Stable
        elif score >= 65:
            return random.randint(2, 7)    # Watch
        elif score >= 50:
            return random.randint(0, 3)    # At risk
        else:
            return random.randint(0, 2)    # Critical
    
    def _categorize_risk(self, score):
        """Categorize attendance score into risk tier"""
        if score >= 90:
            return 'exemplary'
        elif score >= 75:
            return 'stable'
        elif score >= 65:
            return 'watch'
        elif score >= 50:
            return 'atrisk'
        else:
            return 'critical'
    
    def get_students_with_synthetic_data(self):
        """Load students and enrich with synthetic weekly data"""
        data = self._load_synthetic_data()
        students = data.get('students', [])
        
        # Ensure each student has required fields
        for student in students:
            student['id'] = student.get('id', '')
            student['name'] = student.get('name', '')
            student['section'] = student.get('section', '')
            student['score'] = float(student.get('score', 0))
            
            # Ensure risk is categorized
            if 'risk' not in student or not student['risk']:
                student['risk'] = self._categorize_risk(student['score'])
            
            # Generate synthetic weekly history if missing
            if not student.get('weeklyHistory'):
                student['weeklyHistory'] = self._generate_weekly_history(student['score'])
            else:
                student['weeklyHistory'] = [float(x) for x in student['weeklyHistory']]
            
            # Generate weekly change
            if len(student['weeklyHistory']) >= 2:
                weekly_change = ((student['weeklyHistory'][-1] - student['weeklyHistory'][-2]) / 
                                 max(student['weeklyHistory'][-2], 1)) * 100
                student['weeklyChange'] = round(weekly_change, 2)
            else:
                student['weeklyChange'] = 0.0
            
            # Generate attendance streak if missing
            if not student.get('attendanceStreak'):
                student['attendanceStreak'] = self._generate_attendance_streak(student['score'])
            
            student['isAnomaly'] = student.get('isAnomaly', False)
        
        return students
    
    def get_risk_distribution(self):
        """Get count of students per risk category"""
        students = self.get_students_with_synthetic_data()
        distribution = {
            'exemplary': 0,
            'stable': 0,
            'watch': 0,
            'atrisk': 0,
            'critical': 0
        }
        
        for student in students:
            risk = student.get('risk', 'atrisk')
            if risk in distribution:
                distribution[risk] += 1
        
        return distribution
    
    def get_weekly_trends(self):
        """Get average attendance trends over last 8 weeks"""
        students = self.get_students_with_synthetic_data()
        
        # Initialize 8 weeks of data
        weeks_data = [[] for _ in range(8)]
        
        for student in students:
            weekly = student.get('weeklyHistory', [])
            for week_idx, score in enumerate(weekly[:8]):
                weeks_data[week_idx].append(score)
        
        # Calculate averages per week
        trends = []
        for week_idx, week_scores in enumerate(weeks_data):
            if week_scores:
                avg = round(np.mean(week_scores), 1)
                trends.append({
                    'week_num': f'W{week_idx + 1}',
                    'week_label': f'Week {week_idx + 1}',
                    'avg_attendance': float(avg),
                    'total_students': len([s for s in students if len(s.get('weeklyHistory', [])) > week_idx])
                })
        
        return trends
    
    def perform_dbscan_clustering(self, eps=0.3, min_samples=5):
        """
        Perform DBSCAN clustering on students
        Features: attendance score and weekly change %
        """
        students = self.get_students_with_synthetic_data()
        
        if not students:
            return {
                'anomalies': [],
                'normal': [],
                'cluster_stats': {
                    'total_points': 0,
                    'anomaly_count': 0,
                    'normal_count': 0,
                    'eps': eps,
                    'min_samples': min_samples
                }
            }
        
        # Prepare features: [score, weeklyChange]
        X = []
        student_ids = []
        
        for student in students:
            score = float(student.get('score', 0))
            weekly_change = float(student.get('weeklyChange', 0))
            
            X.append([score, weekly_change])
            student_ids.append(student.get('id'))
        
        X = np.array(X)
        
        # Normalize features using StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        print(f"\n🔬 DBSCAN Clustering:")
        print(f"  Total students: {len(student_ids)}")
        print(f"  Features shape: {X_scaled.shape}")
        print(f"  Score range: {X[:, 0].min():.1f} - {X[:, 0].max():.1f}")
        print(f"  Weekly change range: {X[:, 1].min():.1f} - {X[:, 1].max():.1f}")
        print(f"  Parameters: eps={eps}, min_samples={min_samples}")
        
        # Perform DBSCAN
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(X_scaled)
        
        # Separate anomalies (label == -1) from normal points (label >= 0)
        anomalies = []
        normal = []
        
        for idx, label in enumerate(labels):
            student = students[idx]
            point_data = {
                'id': student.get('id'),
                'name': student.get('name'),
                'section': student.get('section'),
                'score': float(student.get('score', 0)),
                'weeklyChange': float(student.get('weeklyChange', 0)),
                'risk': student.get('risk', 'unknown'),
                'x': float(X[idx, 0]),  # Score for scatter plot
                'y': float(X[idx, 1]),  # Weekly change for scatter plot
                'clusterLabel': int(label),
                'normalized_score': float(X_scaled[idx, 0]),
                'normalized_change': float(X_scaled[idx, 1])
            }
            
            if label == -1:
                anomalies.append(point_data)
            else:
                normal.append(point_data)
        
        print(f"  Results:")
        print(f"    ✓ Anomalies detected: {len(anomalies)}")
        print(f"    ✓ Normal clusters: {len(normal)}")
        if anomalies:
            print(f"    Sample anomalies: {[a['id'] for a in anomalies[:3]]}")
        
        # Sort anomalies by severity (lowest score)
        anomalies.sort(key=lambda x: x['score'])
        
        return {
            'anomalies': anomalies,
            'normal': normal,
            'cluster_stats': {
                'total_points': len(student_ids),
                'anomaly_count': len(anomalies),
                'normal_count': len(normal),
                'eps': eps,
                'min_samples': min_samples,
                'contamination_rate': round((len(anomalies) / len(student_ids)) * 100, 1) if len(student_ids) > 0 else 0
            }
        }
    
    def get_critical_students(self, threshold=60):
        """Get students with attendance below threshold"""
        students = self.get_students_with_synthetic_data()
        critical = [s for s in students if s.get('score', 0) < threshold]
        return sorted(critical, key=lambda x: x.get('score', 0))
    
    def get_at_risk_students(self, min_score=50, max_score=74):
        """Get at-risk students in score range"""
        students = self.get_students_with_synthetic_data()
        at_risk = [s for s in students if min_score <= s.get('score', 0) <= max_score]
        return sorted(at_risk, key=lambda x: x.get('score', 0))
    
    def get_watch_zone_students(self, min_score=75, max_score=79):
        """Get watch zone students"""
        students = self.get_students_with_synthetic_data()
        watch = [s for s in students if min_score <= s.get('score', 0) <= max_score]
        return sorted(watch, key=lambda x: x.get('score', 0), reverse=True)
    
    def get_stable_students(self):
        """Get stable students"""
        students = self.get_students_with_synthetic_data()
        stable = [s for s in students if s.get('risk') == 'stable']
        return stable
    
    def get_exemplary_students(self):
        """Get exemplary students"""
        students = self.get_students_with_synthetic_data()
        exemplary = [s for s in students if s.get('risk') == 'exemplary']
        return sorted(exemplary, key=lambda x: x.get('score', 0), reverse=True)
    
    def get_full_analytics_report(self):
        """Get complete analytics report for dashboard"""
        return {
            'timestamp': datetime.now().isoformat(),
            'students': self.get_students_with_synthetic_data(),
            'distribution': self.get_risk_distribution(),
            'weekly_trends': self.get_weekly_trends(),
            'dbscan': self.perform_dbscan_clustering(),
            'critical': self.get_critical_students(),
            'at_risk': self.get_at_risk_students(),
            'watch_zone': self.get_watch_zone_students(),
            'stable': self.get_stable_students(),
            'exemplary': self.get_exemplary_students()
        }

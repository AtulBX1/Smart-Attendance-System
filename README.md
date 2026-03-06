# Smart Attendance System

An AI-powered attendance analytics system that predicts students at risk of falling below attendance requirements using machine learning and behavioral trend analysis.

This project transforms traditional attendance tracking into a **predictive monitoring system** that helps mentors and faculty identify students who may require intervention before attendance issues become critical.

---

## Key Features

### Predictive Risk Detection

Uses machine learning models to estimate the probability of a student becoming attendance-deficient.

### Attendance Trend Analysis

Tracks rolling attendance patterns to detect declining participation.

### Mentor Dashboard

Displays students categorized into:

* High Risk
* Watchlist
* Safe

This allows mentors to focus attention on students who need help.

### Automated Intervention Suggestions

Provides recommended actions such as:

* Parent contact
* Counseling session
* Advisory monitoring

### Student Attendance Visualization

Interactive charts show attendance trends for individual students.

### Anomaly Detection

Identifies unusual attendance behavior patterns using unsupervised learning.

---

## Machine Learning Models Used

* Random Forest Classifier
* XGBoost Classifier
* DBSCAN for anomaly detection

The system uses an ensemble approach to improve prediction reliability.

---

## Feature Engineering

Key behavioral features used for prediction:

* Rolling Attendance Average
* Absence Streak
* Semester Attendance Percentage
* Attendance Trend (momentum)

These features allow the system to detect **early warning signals** rather than reacting after attendance drops.

---

## System Architecture

Dataset → Preprocessing → Feature Engineering → ML Model → Risk Classification → Dashboard Visualization

---

## Technology Stack

Backend

* Python
* Flask

Machine Learning

* Scikit-Learn
* XGBoost
* Pandas
* NumPy

Visualization

* Chart.js

Database

* SQLite

---

## Project Structure

```
Smart-Attendance-System
│
├── backend
│   ├── app.py
│   └── templates
│
├── models
│   ├── train_model.py
│   └── anomaly_detection.py
│
├── utils
│   └── preprocess.py
│
├── data
│   ├── raw
│   └── processed
│
├── notebooks
│
└── requirements.txt
```

---

## Example Output

The system categorizes students into risk groups:

| Student | Semester Attendance | Trend | Status    |
| ------- | ------------------- | ----- | --------- |
| S0414   | 73%                 | -0.50 | High Risk |
| S0695   | 89%                 | -0.20 | Watchlist |
| S0258   | 74%                 | +0.10 | Safe      |

Mentors receive actionable insights rather than simple attendance percentages.

---

## Future Improvements

* Real-time integration with university attendance systems
* Automated notification system for mentors and parents
* Advanced student behavioral analytics
* Deployment on cloud infrastructure

---

## Author

Atul Raj Singh
B.Tech Computer Science

---

## License

This project is intended for academic and research purposes.

Smart Attendance System

An ML-powered Smart Attendance System that predicts at-risk students using attendance patterns and behavioral features.

This project evolved from a basic ML model into a GPU-accelerated pipeline using XGBoost, hyperparameter tuning, and performance monitoring on NVIDIA CUDA hardware.

Features
Attendance trend analysis
Behavioral feature-based student risk prediction
GPU-accelerated XGBoost training (CUDA)
Hyperparameter tuning with:
GridSearchCV
RandomizedSearchCV
Weighted F1 evaluation for classification
GPU utilization monitoring via nvidia-smi
Experiment logging and benchmarking (CPU vs GPU)
Tech Stack

Machine Learning

Python
scikit-learn
XGBoost

GPU / Acceleration

NVIDIA CUDA 12.7
RTX 3050 Laptop GPU
XGBoost CUDA backend (device='cuda')

Data & Utilities

Pandas
NumPy
Dataset
~419,000 rows
21 features (attendance + behavioral data)

Target:

Student risk classification
Model Evolution
1. Random Forest Baseline
RandomForestClassifier
No tuning
2. CPU-Tuned XGBoost
RandomizedSearchCV
F1 Score: 0.8670
Time: 26.2s
3. GPU-Accelerated XGBoost (Final)

Configuration:

XGBClassifier(
device="cuda",
tree_method="hist"
)

Results:

Metric	Value
Weighted F1	0.8672
CV F1	0.8639
GPU Time	15.2s
CPU Time	26.2s
Speedup	1.7×

GPU Stats:

Peak Utilization: 99%
VRAM Usage: ~2454 MiB
Hyperparameter Tuning

param_distributions = {
"max_depth": [3, 5, 10],
"n_estimators": [50, 100, 200],
"min_child_weight": [1, 3, 5]
}

n_iter = 10
cv = 3
scoring = 'f1_weighted'
n_jobs = -1

Best Params:

{
'n_estimators': 200,
'min_child_weight': 1,
'max_depth': 5
}

GPU Integration Notes
Uses XGBoost ≥ 2.0
GPU enabled via:

device = 'cuda'
tree_method = 'hist'

Includes:
GPU verification
fallback prevention
runtime monitoring (nvidia-smi)
Project Structure

Smart-Attendance-System/
│
├── models/
│ └── train_model.py
├── data/
├── notebooks/
├── experiment_log.md
├── requirements.txt
└── README.md

Installation

git clone https://github.com/AtulBX1/Smart-Attendance-System.git
cd Smart-Attendance-System
pip install -r requirements.txt

GPU Requirements
NVIDIA GPU (CUDA supported)
CUDA 12+
XGBoost 2.x

Check GPU:

nvidia-smi

Future Improvements
SHAP explainability
Feature importance visualization
Real-time dashboard
Drift detection
Deep learning models
Author

Atul Raj Singh

License

MIT License
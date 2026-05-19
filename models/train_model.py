import pandas as pd
import subprocess
import threading
import time
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.metrics import classification_report, f1_score
from xgboost import XGBClassifier
import joblib
import numpy as np

# ─────────────────────────────────────────────
# 1. Confirm NVIDIA GPU via nvidia-smi (hard check — no fallback)
# ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — GPU HARDWARE CHECK")
print("=" * 60)
try:
    smi_out = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader",
        ],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()
    print(f"[GPU CONFIRMED]  {smi_out}")
except Exception as e:
    raise RuntimeError(
        "nvidia-smi failed — NVIDIA GPU not found. Exiting.\n"
        f"Details: {e}"
    )

# ─────────────────────────────────────────────
# 2. Load processed data
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — DATA LOADING")
print("=" * 60)
df = pd.read_csv("data/processed/processed_attendance.csv")

attendance_summary = df.groupby("StudentID")["Present"].mean()
risk_students = attendance_summary[attendance_summary < 0.75].index
df["Risk"] = df["StudentID"].apply(lambda x: 1 if x in risk_students else 0)

features = [
    "Rolling_Attendance",
    "Absence_Streak",
    "Semester_Attendance",
    "Attendance_Trend",
]
X = df[features]
y = df["Risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"[INFO] Train samples: {len(X_train):,}   Test samples: {len(X_test):,}")

# ─────────────────────────────────────────────
# 3. Validate XGBoost GPU integration (hard fail — no fallback)
#    XGBoost >= 2.0: use device='cuda' + tree_method='hist'
#    gpu_hist / gpu_predictor are legacy aliases removed in 2.0+
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3 — XGBoost GPU INTEGRATION CHECK")
print("=" * 60)
try:
    _probe = XGBClassifier(
        device="cuda",          # routes all computation to GPU (XGBoost >= 2.0)
        tree_method="hist",     # hist + device=cuda == former gpu_hist
        eval_metric="logloss",
        n_estimators=1,
        verbosity=0,
    )
    _probe.fit(X_train.iloc[:200], y_train.iloc[:200])
    print("[GPU CONFIRMED]  XGBoost is running on CUDA GPU")
    print("                 device=cuda | tree_method=hist (gpu_hist equivalent in XGBoost 2.0+)")
except Exception as e:
    raise RuntimeError(
        "XGBoost GPU validation failed — CUDA not accessible from XGBoost.\n"
        f"Error: {e}"
    )

# ─────────────────────────────────────────────
# 4. Background nvidia-smi monitor thread
#    Polls every 5s and logs GPU utilization during tuning
# ─────────────────────────────────────────────
_stop_monitor = threading.Event()
_gpu_log: list[str] = []

def _gpu_monitor() -> None:
    while not _stop_monitor.is_set():
        try:
            raw = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip().split(",")
            util  = raw[0].strip()
            used  = raw[1].strip()
            total = raw[2].strip()
            _gpu_log.append(
                f"  [{time.strftime('%H:%M:%S')}]  GPU util: {util}%  |  "
                f"VRAM: {used} / {total} MiB"
            )
        except Exception:
            pass
        _stop_monitor.wait(timeout=5)

monitor_thread = threading.Thread(target=_gpu_monitor, daemon=True)

# ─────────────────────────────────────────────
# 5. RandomizedSearchCV — GPU XGBoost
# ─────────────────────────────────────────────
param_distributions = {
    "max_depth":        [3, 5, 10],
    "n_estimators":     [50, 100, 200],
    "min_child_weight": [1, 3, 5],
}

base_xgb = XGBClassifier(
    device="cuda",
    tree_method="hist",
    eval_metric="logloss",
    random_state=42,
    verbosity=0,
)

xgb_search = RandomizedSearchCV(
    estimator=base_xgb,
    param_distributions=param_distributions,
    n_iter=10,
    cv=3,
    scoring="f1_weighted",
    random_state=42,
    n_jobs=-1,
    verbose=1,
)

print("\n" + "=" * 60)
print("STEP 4 — RandomizedSearchCV  (GPU | 10 iters x 3 folds = 30 fits)")
print("=" * 60)
monitor_thread.start()
tuning_start = time.time()
xgb_search.fit(X_train, y_train)
tuning_elapsed = time.time() - tuning_start
_stop_monitor.set()
monitor_thread.join(timeout=7)

# ─────────────────────────────────────────────
# 6. Best params & CV score
# ─────────────────────────────────────────────
print(f"\n[OK] Best Hyperparameters:")
print(f"   {xgb_search.best_params_}")
print(f"[OK] Best CV F1-Weighted (training folds): {xgb_search.best_score_:.4f}")
print(f"[TIME] Total tuning time: {tuning_elapsed:.1f}s")

# ─────────────────────────────────────────────
# 7. Refit on full training set with best params
# ─────────────────────────────────────────────
xgb_model = XGBClassifier(
    device="cuda",
    tree_method="hist",
    eval_metric="logloss",
    random_state=42,
    verbosity=0,
    **xgb_search.best_params_,
)
xgb_model.fit(X_train, y_train)

# ─────────────────────────────────────────────
# 8. Evaluate on held-out test set
# ─────────────────────────────────────────────
y_pred  = xgb_model.predict(X_test)
test_f1 = f1_score(y_test, y_pred, average="weighted")

print("\n" + "=" * 60)
print("STEP 5 — TEST-SET EVALUATION")
print("=" * 60)
print(classification_report(y_test, y_pred, digits=4))
print(f"[RESULT] Weighted F1 Score (resume number): {test_f1:.4f}")
print(f"[TIME]   Total tuning time               : {tuning_elapsed:.1f}s")
print("=" * 60)

# ─────────────────────────────────────────────
# 9. GPU utilization log (collected during tuning)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("GPU MONITOR LOG (nvidia-smi, sampled every 5s during tuning)")
print("=" * 60)
if _gpu_log:
    for row in _gpu_log:
        print(row)
else:
    print("  [INFO] Tuning completed in < 5s — no interval samples captured")

# ─────────────────────────────────────────────
# 10. Final post-training nvidia-smi snapshot
# ─────────────────────────────────────────────
try:
    snap = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
         "--format=csv,noheader"],
        text=True, stderr=subprocess.DEVNULL,
    ).strip()
    print(f"\n[nvidia-smi snapshot post-training]\n  {snap}")
except Exception:
    pass

# ─────────────────────────────────────────────
# 11. Save model
# ─────────────────────────────────────────────
joblib.dump(xgb_model, "models/xgb_model.pkl")
print("\nModel trained and saved successfully!")
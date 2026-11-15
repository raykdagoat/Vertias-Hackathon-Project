"""Checks the whole pipeline runs, using fake data (no internet needed)."""
import subprocess, sys, os

def test_pipeline_runs():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "run_all.py", "--synthetic"], cwd=root, check=True)
    assert os.path.exists(os.path.join(root, "results_synthetic", "RESULTS.md"))

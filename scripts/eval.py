"""
Minimal evaluation harness.
Put golden cases under ../data/gold/<case>/expected.json
"""
import json, os, glob

GOLD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "gold")

def load_pairs():
    pairs = []
    for case_dir in glob.glob(os.path.join(GOLD_DIR, "*")):
        exp = os.path.join(case_dir, "expected.json")
        if os.path.exists(exp):
            with open(exp) as f:
                pairs.append({"name": os.path.basename(case_dir), "expected": json.load(f)})
    return pairs

def main():
    pairs = load_pairs()
    if not pairs:
        print("No golden cases found. Add folders under data/gold with expected.json")
        return
    for p in pairs:
        print(f"CASE: {p['name']} -> compare got vs expected (implement metrics here)")

if __name__ == "__main__":
    main()

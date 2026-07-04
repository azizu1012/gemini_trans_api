
import os
import sys
import shutil

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from world.auto_learner import AutoWorldLearner
from trackers.character_tracker import CharacterTracker
from world.glossary import Glossary

def test_lazy_creation():
    print("Testing Lazy File Creation...")
    
    base_dir = "test_lazy_output"
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        
    # Define paths
    learner_path = os.path.join(base_dir, "learned_world.json")
    tracker_dir = os.path.join(base_dir, "character_states")
    glossary_path = os.path.join(base_dir, "glossary.json")
    
    # 1. Initialize modules
    print("Initializing modules...", end=" ")
    learner = AutoWorldLearner(learner_path)
    tracker = CharacterTracker(tracker_dir)
    glossary = Glossary(glossary_path)
    print("Done.")
    
    # 2. Check if folders exist (Should NOT exist yet)
    if os.path.exists(base_dir):
        print("❌ FAIL: Base directory created exclusively on init!")
        if os.path.exists(tracker_dir):
             print(f"   tracker_dir created: {tracker_dir}")
        return
    else:
        print("✅ PASS: No directories created on init.")

    # 3. Simulate Save
    print("Simulating Save...", end=" ")
    learner.save_data()
    tracker.save_state()
    glossary.save_glossary()
    print("Done.")
    
    # 4. Check if folders exist (Should exist now)
    if os.path.exists(base_dir) and os.path.exists(tracker_dir):
        print("✅ PASS: Directories created after save.")
    else:
        print("❌ FAIL: Directories NOT created after save.")
        
    # Cleanup
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)

if __name__ == "__main__":
    test_lazy_creation()

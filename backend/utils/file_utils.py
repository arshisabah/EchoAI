# backend/utils/file_utils.py

import json
from datetime import datetime

def save_analysis_results(transcript: str, summary: str, actions: list, filename_prefix: str = "meeting_results"):
    """
    Saves the transcript, summary, and action items into JSON and TXT files.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = f"{filename_prefix}_{timestamp}.json"
    txt_file = f"{filename_prefix}_{timestamp}.txt"

    data = {
        "timestamp": datetime.now().isoformat(),
        "transcript": transcript.strip(),
        "summary": summary.strip(),
        "action_items": actions
    }

    # Save JSON file
    try:
        with open(json_file, "w", encoding="utf-8") as jf:
            json.dump(data, jf, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"❌ Error saving JSON file: {e}")
        return

    # Save TXT file
    try:
        with open(txt_file, "w", encoding="utf-8") as tf:
            tf.write("=== Transcript ===\n")
            tf.write(data["transcript"] + "\n\n")
            tf.write("=== Summary ===\n")
            tf.write(data["summary"] + "\n\n")
            tf.write("=== Action Items ===\n")
            if data["action_items"]:
                for i, item in enumerate(data["action_items"], 1):
                    tf.write(f"{i}. {item}\n")
            else:
                tf.write("No action items detected.\n")
    except IOError as e:
        print(f"❌ Error saving TXT file: {e}")
        return

    print(f"\n💾 Results saved successfully to: {json_file} and {txt_file}")
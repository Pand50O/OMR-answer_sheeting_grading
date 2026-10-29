import json
import csv
import os
import copy  # Import the copy module

# Paths - Modified for this environment
ANSWER_STUDENT_PATH = "output.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Assumes grader CSVs are in the same directory
OUTPUT_DIR = "graded-results"

# Ensure output folder exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === 1. Load all student answers ===
try:
    with open(ANSWER_STUDENT_PATH, "r", encoding="utf-8") as f:
        all_data = json.load(f)
except FileNotFoundError:
    print(f"Error: {ANSWER_STUDENT_PATH} not found.")
    all_data = {}
except json.JSONDecodeError:
    print(f"Error: Could not decode {ANSWER_STUDENT_PATH}.")
    all_data = {}

# === 2. Load correct answers for one subject ===
def load_correct_answers(subject_name):
    csv_filename = os.path.join(BASE_DIR,"answer-grader", f"{subject_name}_grader.csv")
    # csv_filename = f"{subject_name}_grader.csv"
    csv_path = csv_filename  # No subdirectory in this environment

    if not os.path.exists(csv_path):
        print(f"⚠️ Skipped {subject_name}: {csv_filename} not found.")
        return None, None

    categories = {}
    correct_answers = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                correct_answers[row["ques"]] = [row["answer"], row["category"]]
                if row['category'] not in categories:
                    categories[row['category']] = 0
                categories[row['category']] += 1
        print(f"Loaded categories for {subject_name}: {list(categories.keys())}")
        return correct_answers, categories
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return None, None

# === 3. Grade each subject ===
for subject_key, students in all_data.items():
    print(f"\n📘 Grading subject: {subject_key}")

    correct_answers, categories = load_correct_answers(subject_key)
    if correct_answers is None:
        continue

    total_questions = len(correct_answers)
    
    # Create new lists to store the output data
    graded_csv_rows = []  # For CSV
    graded_json_students = [] # For JSON

    for student in students:
        student_id = student["id"]
        original_answers = student.get("answers", {})  # Get original answers
        status = student["status"]
        correct_count = 0
        correct_categories_count = {}

        # Dictionary to store 'c' (correct) or 'x' (incorrect)
        graded_answers_cx = {}

        # Count correct answers
        for q_num, [correct, cat] in correct_answers.items():
            if cat not in correct_categories_count:
                # Store max score for the category
                correct_categories_count[cat] = [0, categories[cat]]

            student_ans = original_answers.get(q_num, "x")  # Default "x" if not answered

            if student_ans == correct:
                correct_count += 1
                correct_categories_count[cat][0] += 1
                graded_answers_cx[q_num] = "c"  # Mark as correct
            else:
                graded_answers_cx[q_num] = "x"  # Mark as incorrect

        # --- This part builds the row for the CSV file ---
        percentile = round(correct_count / total_questions * 100, 2) if total_questions > 0 else 0

        csv_data_row = {
            "id": student_id,
            "score": correct_count,
            "filename": student["filename"],
            "percentile": percentile,
            "total": total_questions,
            "status": status
        }
        for cat, [score, score_mx] in correct_categories_count.items():
            csv_data_row[cat] = f"{score}/{score_mx}"

        graded_csv_rows.append(csv_data_row)
        
        # --- This part builds the new record for the JSON file ---
        # Create a deep copy to ensure the original 'student' object is not changed
        json_student_record = copy.deepcopy(student) 
        
        # Replace the 'answers' dict with the new 'c'/'x' version
        json_student_record["answers"] = graded_answers_cx 
        
        graded_json_students.append(json_student_record)
        # --- End building records ---

        print(f" - {student_id} ({student.get('filename', 'N/A')}): {correct_count}/{total_questions} → {percentile}%")

    # === 4. Sort by student ID (for CSV) ===
    graded_csv_rows.sort(key=lambda x: x["id"])

    # === 5. Write graded CSV per subject ===
    output_csv_path = os.path.join(OUTPUT_DIR, f"graded_{subject_key}_2.csv")

    # Define fieldnames, ensuring categories are included
    fieldNameList = ["id", "score", "percentile", "filename", "total", "status"]
    if categories:
        fieldNameList.extend(categories.keys())

    try:
        with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldNameList, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(graded_csv_rows)
        print(f"✅ Saved CSV: {output_csv_path}")
    except Exception as e:
        print(f"Error writing CSV {output_csv_path}: {e}")

    # === 6. Write graded JSON per subject ===
    output_json_path = os.path.join(OUTPUT_DIR, f"graded_{subject_key}.json")
    try:
        with open(output_json_path, "w", encoding="utf-8") as f:
            # Dump the NEW list of modified student objects
            json.dump(graded_json_students, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved JSON: {output_json_path}")
    except Exception as e:
        print(f"Error writing JSON {output_json_path}: {e}")

print("\n🎯 All subjects graded and saved!")
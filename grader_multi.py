## FOR MULTI CHOICE CORRECT

import csv
import json
import os
import re
import statistics
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANSWER_GRADER_DIR = os.path.join(BASE_DIR, "answer-grader")
OUTPUT_DIR = os.path.join(BASE_DIR, "graded-results")
OMR_RESULT_DIR = os.path.join(BASE_DIR, "omr-result")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def percentile_rank(values, x):
    n = len(values)
    if n == 0:
        return 0.0
    less_or_equal = sum(1 for v in values if v <= x)
    return round((less_or_equal / n) * 100, 2)


def safe_mean(values):
    return round(statistics.mean(values), 2) if values else 0.0


def safe_median(values):
    return round(statistics.median(values), 2) if values else 0.0


def safe_sd(values):
    return round(statistics.pstdev(values), 2) if values else 0.0


def normalize_part_name(part):
    p = str(part).strip().lower()
    if p == "tpat3":
        return "TPAT3"
    if p == "math":
        return "Math"
    if p == "physics":
        return "Physics"
    if p in ("chem", "chemistry"):
        return "Chemistry"
    return str(part).strip()


def get_answer_filename(subject_name):
    return f"FE_{subject_name}_multi.csv"


def get_subject_output_path(subject_name):
    return os.path.join(OMR_RESULT_DIR, subject_name, "output.json")


def load_students(subject_name):
    subject_output_path = get_subject_output_path(subject_name)
    if not os.path.exists(subject_output_path):
        print(f"⚠️ Skipped {subject_name}: file not found {subject_output_path}")
        return None
    with open(subject_output_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(subject_name, [])


def load_correct_answers(subject_name):
    csv_filename = get_answer_filename(subject_name)
    if not csv_filename:
        print(f"⚠️ Skipped {subject_name}: unsupported subject key")
        return None

    csv_path = os.path.join(ANSWER_GRADER_DIR, csv_filename)
    if not os.path.exists(csv_path):
        print(f"⚠️ Skipped {subject_name}: {csv_filename} not found")
        return None

    correct_answers = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q_num = str(row.get("ques", "")).strip()
            if not q_num:
                continue
            raw_ans = str(row.get("answer", "")).strip().lower()
            accepted_answers = [
                token.strip()
                for token in re.split(r"[|/,]", raw_ans)
                if token.strip()
            ]
            if not accepted_answers and raw_ans:
                accepted_answers = [raw_ans]
            part_raw = row.get("category_subject", row.get("category", "OTHER"))
            part = normalize_part_name(part_raw)
            correct_answers[q_num] = {"answers": accepted_answers, "part": part}

    return correct_answers


def get_question_weight(q_num_str):
    try:
        q_num = int(q_num_str)
    except ValueError:
        return 0.0
    if 1 <= q_num <= 50:
        return 1.5
    if 51 <= q_num <= 60:
        return 2.5
    return 0.0


def main():
    valid_subjects = ["pretest", "posttest"]
    selected_subjects = valid_subjects
    if len(sys.argv) >= 2:
        arg = sys.argv[1].strip().lower()
        if arg in valid_subjects:
            selected_subjects = [arg]
        else:
            print("Usage: python3 grader.py [pretest|posttest]")
            return

    for subject_key in selected_subjects:
        print(f"\n📘 Grading subject: {subject_key}")
        students = load_students(subject_key)
        if students is None:
            continue
        correct_answers = load_correct_answers(subject_key)
        if correct_answers is None:
            continue

        rows = []
        for student in students:
            student_id = student.get("id", "")
            status = str(student.get("status", "")).strip().lower()
            answers = student.get("answers", {})

            part_scores = {"TPAT3": 0.0, "Math": 0.0, "Physics": 0.0, "Chemistry": 0.0}
            total_score = 0.0

            # Explicitly keep score at 0 for absent students.
            if status != "absent":
                for q_num, meta in correct_answers.items():
                    student_ans = str(answers.get(q_num, "-")).strip().lower()
                    weight = get_question_weight(q_num)
                    if student_ans in meta["answers"]:
                        part = meta["part"]
                        if part in part_scores:
                            part_scores[part] += weight
                        total_score += weight

            rows.append(
                {
                    "exam_id": student_id,
                    "total_score": round(total_score, 2),
                    "tpat3_score": round(part_scores["TPAT3"], 2),
                    "math_score": round(part_scores["Math"], 2),
                    "physics_score": round(part_scores["Physics"], 2),
                    "chem_score": round(part_scores["Chemistry"], 2),
                }
            )

        best_rows_by_id = {}
        rows_without_id = []
        duplicate_count = 0
        for row in rows:
            exam_id = str(row.get("exam_id", "")).strip()
            if not exam_id:
                rows_without_id.append(row)
                continue

            existing = best_rows_by_id.get(exam_id)
            if existing is None:
                best_rows_by_id[exam_id] = row
                continue

            duplicate_count += 1
            if row["total_score"] > existing["total_score"]:
                best_rows_by_id[exam_id] = row

        if duplicate_count:
            print(f"⚠️ Found {duplicate_count} duplicate sheet(s); kept highest score per exam_id.")

        rows = list(best_rows_by_id.values()) + rows_without_id

        total_vals = [r["total_score"] for r in rows]
        tpat_vals = [r["tpat3_score"] for r in rows]
        math_vals = [r["math_score"] for r in rows]
        physics_vals = [r["physics_score"] for r in rows]
        chem_vals = [r["chem_score"] for r in rows]

        total_mean = safe_mean(total_vals)
        total_median = safe_median(total_vals)
        total_sd = safe_sd(total_vals)

        tpat_mean = safe_mean(tpat_vals)
        math_mean = safe_mean(math_vals)
        physics_mean = safe_mean(physics_vals)
        chem_mean = safe_mean(chem_vals)

        tpat_median = safe_median(tpat_vals)
        math_median = safe_median(math_vals)
        physics_median = safe_median(physics_vals)
        chem_median = safe_median(chem_vals)

        tpat_sd = safe_sd(tpat_vals)
        math_sd = safe_sd(math_vals)
        physics_sd = safe_sd(physics_vals)
        chem_sd = safe_sd(chem_vals)

        for r in rows:
            r["mean_all"] = total_mean
            r["mean_tpat3"] = tpat_mean
            r["mean_math"] = math_mean
            r["mean_physics"] = physics_mean
            r["mean_chem"] = chem_mean

            r["median_all"] = total_median
            r["median_tpat3"] = tpat_median
            r["median_math"] = math_median
            r["median_physics"] = physics_median
            r["median_chem"] = chem_median

            r["sd_all"] = total_sd
            r["sd_tpat3"] = tpat_sd
            r["sd_math"] = math_sd
            r["sd_physics"] = physics_sd
            r["sd_chem"] = chem_sd

            r["percentile_all"] = percentile_rank(total_vals, r["total_score"])

        rows.sort(key=lambda x: str(x.get("exam_id", "")))

        output_csv = os.path.join(OUTPUT_DIR, f"graded_{subject_key}.csv")
        fieldnames = [
            "exam_id",
            "total_score",
            "tpat3_score",
            "math_score",
            "physics_score",
            "chem_score",
            "mean_all",
            "mean_tpat3",
            "mean_math",
            "mean_physics",
            "mean_chem",
            "median_all",
            "median_tpat3",
            "median_math",
            "median_physics",
            "median_chem",
            "sd_all",
            "sd_tpat3",
            "sd_math",
            "sd_physics",
            "sd_chem",
            "percentile_all",
        ]

        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ Saved CSV: {output_csv}")


if __name__ == "__main__":
    main()

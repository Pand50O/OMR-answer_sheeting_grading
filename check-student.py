import csv
import json
import os
import sys
from collections import Counter
from typing import Any


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OMR_RESULT_DIR = os.path.join(BASE_DIR, "omr-result")
STUDENT_FILE_DIR = os.path.join(BASE_DIR, "student_file")

SUBJECT_STUDENT_FILES = {
    "pretest": ("VCK_STUDENT.csv", "exam_id"),
    "posttest": ("VCK_STUDENT.csv", "exam_id"),
}

SUBJECT_META = {
    "pretest": {"subject_id": "00", "subject_type": "pretest"},
    "posttest": {"subject_id": "01", "subject_type": "posttest"},
}


def normalize_id(value: Any) -> str:
    return str(value or "").strip()


def load_csv_students(subject: str) -> dict[str, dict[str, str]]:
    filename, id_column = SUBJECT_STUDENT_FILES[subject]
    csv_path = os.path.join(STUDENT_FILE_DIR, filename)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Student CSV not found: {csv_path}")

    students = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or id_column not in reader.fieldnames:
            raise Exception(f"Column '{id_column}' not found in {csv_path}")

        for row in reader:
            student_id = normalize_id(row.get(id_column))
            if student_id:
                students[student_id] = row

    return students


def load_omr_students(subject: str) -> list[dict[str, Any]]:
    json_path = os.path.join(OMR_RESULT_DIR, subject, "output.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"OMR output not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    students = data.get(subject, [])
    if not isinstance(students, list):
        raise Exception(f"Expected '{subject}' in {json_path} to be a list")

    return students


def save_omr_students(subject: str, students: list[dict[str, Any]]) -> None:
    json_path = os.path.join(OMR_RESULT_DIR, subject, "output.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({subject: students}, f, indent=2, ensure_ascii=False)


def format_student(row: dict[str, str]) -> str:
    name_parts = [
        normalize_id(row.get("title")),
        normalize_id(row.get("name")),
        normalize_id(row.get("surname")),
    ]
    name = " ".join(part for part in name_parts if part)
    room = normalize_id(row.get("room"))
    seat = normalize_id(row.get("seat_number"))

    details = []
    if name:
        details.append(name)
    if room:
        details.append(f"room={room}")
    if seat:
        details.append(f"seat={seat}")

    return " | ".join(details)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1].strip().lower() not in SUBJECT_STUDENT_FILES:
        subjects = "|".join(SUBJECT_STUDENT_FILES)
        print(f"Usage: python3 check-student.py [{subjects}]")
        return 1

    subject = sys.argv[1].strip().lower()
    csv_students = load_csv_students(subject)
    omr_students = load_omr_students(subject)

    csv_ids = set(csv_students)
    omr_ids = [normalize_id(student.get("id")) for student in omr_students]
    omr_ids = [student_id for student_id in omr_ids if student_id]
    omr_id_set = set(omr_ids)
    duplicates = sorted(student_id for student_id, count in Counter(omr_ids).items() if count > 1)

    missing_ids = sorted(csv_ids - omr_id_set)
    extra_ids = sorted(omr_id_set - csv_ids)

    print(f"Subject: {subject}")
    print(f"CSV students: {len(csv_ids)}")
    print(f"OMR students: {len(omr_id_set)} unique / {len(omr_ids)} rows")

    if missing_ids:
        print(f"\nMissing in omr-result/{subject}/output.json: {len(missing_ids)}")
        for student_id in missing_ids:
            detail = format_student(csv_students[student_id])
            suffix = f" - {detail}" if detail else ""
            print(f"- {student_id}{suffix}")

        subject_meta = SUBJECT_META[subject]
        for student_id in missing_ids:
            omr_students.append(
                {
                    "id": student_id,
                    "subject_id": subject_meta["subject_id"],
                    "subject_type": subject_meta["subject_type"],
                    "status": "absent",
                }
            )

        save_omr_students(subject, omr_students)
        print(f"\nAdded {len(missing_ids)} absent students to omr-result/{subject}/output.json")
    else:
        print(f"\nNo missing students from CSV in omr-result/{subject}/output.json")

    if extra_ids:
        print(f"\nFound in OMR JSON but not in CSV: {len(extra_ids)}")
        for student_id in extra_ids:
            print(f"- {student_id}")

    if duplicates:
        print(f"\nDuplicate IDs in OMR JSON: {len(duplicates)}")
        counts = Counter(omr_ids)
        for student_id in duplicates:
            print(f"- {student_id} ({counts[student_id]} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import os
import cv2
import numpy as np
import pickle
import json
import sys
from typing import List, Dict, Any, Tuple

# ... (Keep your existing AnswerSheet class definition as is,
#      including all methods: __init__, evaluate, convert_to_binary,
#      morph_erode, morph_dilate, crop, read_dots, parse_answer,
#      parse_multiple_choice, parse_fill_blank, parse_top, get_contours,
#      perspective_transform, sort_points, show_image)
#      For brevity, the class definition is not repeated here.
# ---------------------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BINARY_THRESHOLD = 200
WHITE_MARK_THRESHOLD = 0.35


class ContourCountError(Exception):
    def __init__(self, img_name: str, contour_count: int, debug_path: str | None = None):
        self.img_name = img_name
        self.contour_count = contour_count
        self.debug_path = debug_path
        super().__init__(f"Unable to crop bin_img properly for {img_name}. Found {contour_count} contours.")

# Re-pasting the AnswerSheet class for completeness in a single runnable block
# NOTE: I am only including the necessary methods to show the flow, 
# you should use your full AnswerSheet class.
class AnswerSheet:
    def __init__(self, img_path, venue):
        self.img_path = img_path
        self.img_name = os.path.splitext(os.path.basename(self.img_path))[0]
        self.venue = venue
        try:
          self.img = cv2.imread(img_path)
          if self.img is None:
              raise FileNotFoundError(f"Image not loaded: {img_path}")
        except Exception as e:
            # Handle cases where the image file might be corrupt or not found properly
            print(f"Error loading image {img_path}: {e}")
            self.img = None
            
        self.bin_img = None
        self.bin_find_rect_img = None
        self.sections = None
        self.subject = None
        self.cancel = None
        self.absent = None
        self.subject_type = None
        self.student_id = None
        self.student_answer = None
        self.processing_stage = "init"
        self.debug_marked_path = None
        self.debug_save_error = None
        self.top_boxes_drawn = 0
        self.answer_boxes_drawn = 0

    def auto_rotate_if_upside_down(self):
        """
        FE sheet expected orientation has dark borders on LEFT and BOTTOM.
        If detected as TOP and RIGHT instead, rotate 180 degrees.
        """
        if self.img is None:
            return

        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        strip = max(8, int(min(h, w) * 0.03))

        left_mean = float(np.mean(gray[:, :strip]))
        right_mean = float(np.mean(gray[:, w - strip:]))
        top_mean = float(np.mean(gray[:strip, :]))
        bottom_mean = float(np.mean(gray[h - strip:, :]))

        # Lower mean = darker edge
        normal_score = (left_mean < right_mean) + (bottom_mean < top_mean)
        flipped_score = (top_mean < bottom_mean) + (right_mean < left_mean)

        # Rotate only when "flipped" signal is clearly stronger.
        if flipped_score == 2 and normal_score == 0:
            self.img = cv2.rotate(self.img, cv2.ROTATE_180)
            print(f"↻ Auto-rotated 180°: {self.img_name}")

    def evaluate(self):
        if self.img is None:
             raise Exception(f"Skipping evaluation for {self.img_path} as image is not loaded.")
        
        # NOTE: Your original code had several cv2.imshow/waitKey calls inside `crop`
        # and `read_dots`. For folder-wide execution, these will pause the script
        # for every single file. You should comment them out or remove them for
        # production/batch processing.
        # e.g., in crop():
        # cv2.imshow("original", self.bin_img)
        # cv2.waitKey(0) 
        # and:
        # cv2.imshow(str(cnt), filtered_rect[cnt])
        # cv2.waitKey(0)
        
        self.processing_stage = "auto_rotate"
        self.auto_rotate_if_upside_down()
        self.processing_stage = "convert_to_binary"
        self.convert_to_binary(BINARY_THRESHOLD)
        self.processing_stage = "convert_to_binary_find_rect"
        self.convert_to_binary_find_rect()
        # self.morph_dilate((2, 2), 1)
        self.processing_stage = "crop"
        self.crop()
        self.processing_stage = "read_dots"
        self.read_dots()
        self.processing_stage = "done"
    
    def convert_to_binary_find_rect(self) -> np.ndarray:
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        # Use Gaussian blur to reduce noise before adaptive thresholding
        gray = cv2.GaussianBlur(gray, (5, 5), 0) 
        
        # Use Adaptive Thresholding (OTSU is global, which you use now)
        # THRESH_BINARY_INV is used to get white on black, as per your original code
        self.bin_find_rect_img = cv2.adaptiveThreshold(
            gray, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, # Use inverted binary
            65,
            7
            # 55, # Block size (must be odd, e.g., 11, 15, 21)
            # 15   # C (constant subtracted from the mean)
        )
        
    def convert_to_binary(self, thresh: int) -> np.ndarray:
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        _, self.bin_img = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV)
        # _, self.bin_img = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    def morph_dilate(self, kernel_size: tuple[int, int], iterations: int):
        kernel = np.ones(kernel_size, np.uint8)
        self.bin_img = cv2.dilate(self.bin_img, kernel, iterations=iterations)
        
    def crop(self):
        # ... (Your existing crop logic here)
        contours = AnswerSheet.get_contours(self.bin_find_rect_img)
        height, width = self.bin_find_rect_img.shape
        filtered_rect = []
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
            contour_area = cv2.contourArea(contour)
            if len(approx) != 4 or contour_area < 0.15 * height * width:
                continue
            filtered_rect.append((approx, contour_area))
            
        debug_path = None
        if len(filtered_rect) > 2:
            debug_path = self.save_contour_debug(filtered_rect)
            print(f"Saved contour debug for {self.img_name}: {debug_path}")
        
        if len(filtered_rect) != 2:
            raise ContourCountError(self.img_name, len(filtered_rect), debug_path)

        filtered_rect.sort(key=lambda x: x[1])
        filtered_rect = [rect for rect, _ in filtered_rect]
        filtered_rect = list(map(lambda x: x.reshape(4, 2), filtered_rect))
        filtered_rect = list(map(lambda x: AnswerSheet.sort_points(x), filtered_rect))
        filtered_rect = list(map(lambda x: AnswerSheet.perspective_transform(self.bin_img, x), filtered_rect))
        self.sections = {
            "top": filtered_rect[0],
            "answer": filtered_rect[1]
        }
        # Remember to comment out cv2.imshow/waitKey calls in this method for batch processing

    def save_contour_debug(self, filtered_rect: list[tuple[np.ndarray, float]]) -> str:
        debug_dir = os.path.join(BASE_DIR, "debug-images")
        os.makedirs(debug_dir, exist_ok=True)

        debug_img = self.img.copy()
        for index, (rect, contour_area) in enumerate(filtered_rect, start=1):
            points = rect.reshape(4, 2)
            center = tuple(np.mean(points, axis=0).astype(int))
            cv2.drawContours(debug_img, [rect], -1, (0, 0, 255), 5)
            cv2.putText(
                debug_img,
                f"{index}: {int(contour_area)}",
                center,
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        debug_path = os.path.join(debug_dir, f"{self.img_name}_contours.jpg")
        cv2.imwrite(debug_path, debug_img)
        return debug_path

    def read_dots(self):
        self.processing_stage = "prepare_debug_images"
        debug_img = {
            "top": cv2.cvtColor(self.sections["top"], cv2.COLOR_GRAY2BGR),
            "answer": cv2.cvtColor(self.sections["answer"], cv2.COLOR_GRAY2BGR),
        }

        try:
            # --- Read TOP section first to get subject info ---
            section = "top"
            marks_top = []
            pickle_name_top = "FE_top.pkl"
            pickle_path_top = os.path.join(BASE_DIR, "pickles", pickle_name_top)
            self.processing_stage = "read_top_pickle"
            with open(pickle_path_top, "rb") as f:
                marks_top = pickle.load(f)

            blacken_top = []
            height, width = self.sections[section].shape
            self.processing_stage = "read_top_bubbles"
            for (x, y), rect_size in marks_top:
                x1 = int(x * width)
                y1 = int(y * height)
                x2 = int(x * width + rect_size * height)
                y2 = int(y * height + rect_size * height)
                roi = self.sections[section][y1:y2, x1:x2]
                marked = self.is_white_over_threshold(roi, WHITE_MARK_THRESHOLD)
                blacken_top.append(marked)
                cv2.rectangle(
                    debug_img["top"],
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0) if marked else (0, 0, 255),
                    2,
                )
                self.top_boxes_drawn += 1

            self.processing_stage = "parse_top"
            self.cancel, self.absent, self.subject, self.subject_type, self.student_id = AnswerSheet.parse_top(blacken_top)

            # --- Read ANSWER section ---
            section = "answer"
            marks_answer = []
            self.processing_stage = "resolve_answer_pickle"
            if self.subject_type is None:
                raise Exception(f"Subject type is missing for {self.img_name}. Cannot load answer pickle.")

            if self.subject_type in ("pretest", "posttest", "postest"):
                pickle_name_answer = f"FE_{self.subject_type}_answer.pkl"
            else:
                pickle_name_answer = f"{self.venue}_{self.subject_type}_answer.pkl"
            pickle_path_answer = os.path.join(BASE_DIR, "pickles", pickle_name_answer)
            self.processing_stage = "read_answer_pickle"
            with open(pickle_path_answer, "rb") as f:
                marks_answer = pickle.load(f)

            blacken_answer = []
            height, width = self.sections[section].shape
            self.processing_stage = "read_answer_bubbles"
            for (x, y), rect_size in marks_answer:
                x1 = int(x * width)
                y1 = int(y * height)
                x2 = int(x * width + rect_size * height)
                y2 = int(y * height + rect_size * height)
                roi = self.sections[section][y1:y2, x1:x2]
                marked = self.is_white_over_threshold(roi, WHITE_MARK_THRESHOLD)
                blacken_answer.append(marked)
                cv2.rectangle(
                    debug_img["answer"],
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0) if marked else (0, 0, 255),
                    2,
                )
                self.answer_boxes_drawn += 1

            self.processing_stage = "parse_answer"
            self.student_answer = AnswerSheet.parse_answer(blacken_answer, self.subject)
        finally:
            try:
                debug_dir = os.path.join(BASE_DIR, "debug-images")
                os.makedirs(debug_dir, exist_ok=True)
                min_width = min(debug_img["top"].shape[1], debug_img["answer"].shape[1])
                top_resized = cv2.resize(
                    debug_img["top"],
                    (min_width, int(debug_img["top"].shape[0] * min_width / debug_img["top"].shape[1])),
                )
                answer_resized = cv2.resize(
                    debug_img["answer"],
                    (min_width, int(debug_img["answer"].shape[0] * min_width / debug_img["answer"].shape[1])),
                )
                concatenated_debug_img = np.vstack([top_resized, answer_resized])
                debug_path = os.path.join(debug_dir, f"{self.img_name}_marked.jpg")
                if not cv2.imwrite(debug_path, concatenated_debug_img):
                    raise Exception(f"cv2.imwrite returned False for {debug_path}")
                self.debug_marked_path = debug_path
            except Exception as debug_error:
                self.debug_save_error = str(debug_error)
                print(f"Failed to save marked debug image for {self.img_name}: {debug_error}")

    @staticmethod
    def is_white_over_threshold(roi: np.ndarray, threshold: float = 0.45) -> int:
        roi_area = roi.shape[0] * roi.shape[1]
        if roi_area == 0:
            return 0
        white = np.sum(roi == 255)
        white_percentage = white / roi_area
        return 1 if white_percentage > threshold else 0

    # ... (All static methods from your original class definition)

    @staticmethod
    def parse_top(blacken: list[int]) -> Tuple[bool, bool, str, str, str]:
        subject_id2name = {
            "00": "pretest", "01": "posttest", "61": "math", "64": "physics", "30": "tpat3", "69": "posttest"
        }
        subject_id2type = {
          "00": "pretest", "01": "posttest", "61": "alevel", "64" : "alevel", "30": "tpat3"
        }

        cancel = bool(blacken[0])
        absent = bool(blacken[1])

        # Subject ID (Indices 2 to 21)
        subject_id_blacken = blacken[2:2+20]
        if sum(subject_id_blacken[:10]) != 1 or sum(subject_id_blacken[10:20]) != 1:
            # NOTE: Your logic throws an exception here. In batch processing, you might
            # want to catch this later and mark the file as 'error' or 'unreadable'.
            raise Exception("Cannot parse subject id")
        subject_id = str(subject_id_blacken[:10].index(1)) + str(subject_id_blacken[10:20].index(1))
        
        if subject_id not in subject_id2name:
            raise Exception(f"Unknown subject ID: {subject_id}")
            
        subject_name = subject_id2name[subject_id]
        subject_type = subject_id2type.get(subject_id, "unknown") # Use .get for safety

        # Student ID (Indices -70 to the end)
        student_id_blacken = blacken[-70:]
        student_id_digits = []
        for i in range(0, 7):
            digit_dots = student_id_blacken[10 * i: 10 * (i + 1)]
            if sum(digit_dots) != 1:
                # Same note as above: consider robustness for batch processing
                raise Exception(f"Cannot parse student id digit {i+1}")
            student_id_digits.append(str(digit_dots.index(1)))
        
        student_id = "".join(student_id_digits)
        return (cancel, absent, subject_name, subject_type, student_id)
        
    @staticmethod
    def parse_answer(blacken: list[int], subject: str) -> Dict[str, str]:
        answer_dict = {}
        if subject in ("pretest", "posttest", "postest"):
            # Q1-50: multiple choice (50 * 5 = 250)
            for i in range(50):
                q_num = str(i + 1)
                start_index = 5 * i
                answer_dict[q_num] = AnswerSheet.parse_multiple_choice(blacken[start_index:start_index + 5])

            # Q51-60: written numeric (10 questions, 6 digits each, 10 bubbles per digit)
            # = 10 * 60 = 600, starting at index 250
            for i in range(10):
                q_num = str(i + 51)
                start_index = 250 + 60 * i
                answer_dict[q_num] = AnswerSheet.parse_fill_blank(blacken[start_index:start_index + 60])

        if subject == 'math' or subject == 'physics': 
            # Questions 1-25 are multiple choice, Questions 26-30 are fill-in-the-blank
            
            # Multiple Choice (25 questions * 5 choices = 125 dots)
            for i in range(25):
                q_num = str(i + 1)
                start_index = 5 * i
                answer_dict[q_num] = AnswerSheet.parse_multiple_choice(blacken[start_index:start_index + 5])
                
            # Fill-in-the-blank (5 questions * 6 digits * 10 options = 300 dots)
            # The blacken list index starts at 125.
            for i in range(5):
                q_num = str(i + 26)
                # Your list slicing is correct: [125 + 60*i : 125 + 60*i + 60]
                start_index = 125 + 60 * i
                answer_dict[q_num] = AnswerSheet.parse_fill_blank(blacken[start_index:start_index + 60])
                
        elif subject == 'tpat3': 
            # Questions 1-70 are multiple choice
            for i in range(70):
                q_num = str(i + 1)
                start_index = 5 * i
                answer_dict[q_num] = AnswerSheet.parse_multiple_choice(blacken[start_index:start_index + 5])
        
        # NOTE: Your original code returned a list of answers. 
        # The JSON structure requires a dictionary mapping question number to answer. 
        # I've updated this function to return the required dictionary.
        return answer_dict

    @staticmethod
    def parse_multiple_choice(blacken: list[int]) -> str:
        chosen = [str(i + 1) for i in range(len(blacken)) if blacken[i] == 1]
        if len(chosen) != 1:
            return "-"
        return chosen[0]

    @staticmethod
    def parse_fill_blank(blacken: list[int]) -> str:
        ret_str = ""
        for i in range(len(blacken) // 10):
            num_blacken = sum(blacken[10*i:10*i+10])
            if num_blacken == 1:
                ret_str += str(blacken[10*i:10*i+10].index(1))
            else:
                # Treat blank or invalid multiple marks as unfilled for this position.
                ret_str += "-"
        return ret_str
        
    @staticmethod
    def get_contours(bin_img: np.ndarray) -> list[np.ndarray]:
        if len(np.unique(bin_img)) != 2:
            raise Exception("The image is not binary")
        contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    @staticmethod
    def perspective_transform(img: np.ndarray, points: list[list[int]]) -> np.ndarray:
        # ... (Your existing perspective_transform logic here)
        max_width = max(
            int(np.hypot(points[0][0] - points[1][0], points[0][1] - points[1][1])),
            int(np.hypot(points[2][0] - points[3][0], points[2][1] - points[3][1]))
        )
        max_height = max(
            int(np.hypot(points[1][0] - points[2][0], points[1][1] - points[2][1])),
            int(np.hypot(points[3][0] - points[0][0], points[3][1] - points[0][1]))
        )
        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype="float32")
        M = cv2.getPerspectiveTransform(np.array(points, dtype="float32"), dst)
        warped = cv2.warpPerspective(img, M, (max_width, max_height))
        return warped

    @staticmethod
    def sort_points(points: list[list[int]]) -> list[list[int]]:
        # ... (Your existing sort_points logic here)
        points = sorted(points, key=lambda x: (x[1], x[0]))
        if points[0][0] > points[1][0]:
            points[0], points[1] = points[1], points[0]
        if points[2][0] < points[3][0]:
            points[2], points[3] = points[3], points[2]
        return points

# ---------------------------------------------------------------------------------------

if __name__ == "__main__":
    # Define the parent directory containing the subject folders
    SCAN_BASE_DIR = os.path.join(BASE_DIR, "answersheet-scan")

    if not os.path.isdir(SCAN_BASE_DIR):
        print(f"❌ Scan folder not found: {SCAN_BASE_DIR}")
        sys.exit(1)

    # Discover subject folders dynamically (e.g., pretest, posttest, math, physics)
    SUBJECT_FOLDERS = sorted(
        [
            name for name in os.listdir(SCAN_BASE_DIR)
            if os.path.isdir(os.path.join(SCAN_BASE_DIR, name))
        ]
    )

    if not SUBJECT_FOLDERS:
        print(f"❌ No subject folders found in: {SCAN_BASE_DIR}")
        sys.exit(1)

    selected_subjects = SUBJECT_FOLDERS
    if len(sys.argv) >= 2:
        arg = sys.argv[1].strip().lower()
        if arg == "all":
            selected_subjects = SUBJECT_FOLDERS
        elif arg in SUBJECT_FOLDERS:
            selected_subjects = [arg]
        else:
            print(f"Usage: python3 omr.py [all|{'|'.join(SUBJECT_FOLDERS)}]")
            sys.exit(1)
    
    # Hardcoded venue from your original script
    VENUE = "FEST"
    
    # Dictionary to hold all the results
    all_results: Dict[str, List[Dict[str, Any]]] = {subject: [] for subject in selected_subjects}
    
    # Dictionary to hold all the failed files and error messages
    failed_results: Dict[str, List[Dict[str, Any]]] = {subject: [] for subject in selected_subjects}
    contour_failures: List[Dict[str, Any]] = []
    
    # Output file path
    OMR_RESULT_DIR = os.path.join(BASE_DIR, "omr-result")
    os.makedirs(OMR_RESULT_DIR, exist_ok=True)
    
    print(f"Starting scan of folders in: {SCAN_BASE_DIR}")
    print(f"Subjects to process: {', '.join(selected_subjects)}")

    for subject in selected_subjects:
        subject_folder = os.path.join(SCAN_BASE_DIR, subject)
        
        if not os.path.isdir(subject_folder):
            print(f"⚠️ Warning: Folder '{subject_folder}' not found. Skipping.")
            continue
            
        print(f"\nProcessing **{subject.upper()}** files...")
        
        for filename in os.listdir(subject_folder):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                img_path = os.path.join(subject_folder, filename)
                print(f"-> Analyzing: {filename}")
                sheet = None
                
                try:
                    sheet = AnswerSheet(img_path, VENUE)
                    sheet.evaluate()
                    
                    # Determine status and subject_id from the results
                    status = "present" if not sheet.absent and not sheet.cancel else "absent" if sheet.absent else "cancelled"
                    
                    # Format the student answers into the required structure
                    # The parse_answer method should return the Dict[str, str]
                    
                    # Ensure student_id is set before trying to access
                    if sheet.student_id is None:
                        raise Exception("Student ID could not be read.")

                    # Use the subject ID derived from the subject name for consistency
                    # This relies on the internal mapping in parse_top
                    subject_name_to_id = {
                        "pretest": "00",
                        "posttest": "01",
                        "postest": "01",
                        "math": "61",
                        "physics": "64",
                        "tpat3": "30",
                    }
                    subject_id = subject_name_to_id.get(sheet.subject, "00")
                    
                    # Create the entry for the JSON file
                    file_entry = {
                        "filename": filename,
                        "status": status,
                        "subject_id": subject_id, 
                        "subject_type": sheet.subject_type,
                        "subject": sheet.subject,
                        "id": sheet.student_id,
                        # Assuming sheet.student_answer is a dict like {"1": "3", "2": "5", ...}
                        "answers": sheet.student_answer if isinstance(sheet.student_answer, dict) else {}
                    }
                    
                    all_results[subject].append(file_entry)
                    
                except ContourCountError as e:
                    error_message = str(e).strip()
                    print(f"-> Analyzing: {filename} | contour_count={e.contour_count} | skipped")
                    print(f"🚨 Error processing {filename}: {error_message}")
                    contour_failures.append({
                        "filename": filename,
                        "subject": subject,
                        "img_name": e.img_name,
                        "contour_count": e.contour_count,
                        "debug_image": e.debug_path,
                        "error": error_message
                    })
                    failed_results[subject].append({
                        "filename": filename,
                        "type": "contour_count",
                        "img_name": e.img_name,
                        "stage": getattr(sheet, "processing_stage", "crop"),
                        "contour_count": e.contour_count,
                        "debug_image": e.debug_path,
                        "top_boxes_drawn": getattr(sheet, "top_boxes_drawn", 0),
                        "answer_boxes_drawn": getattr(sheet, "answer_boxes_drawn", 0),
                        "error": error_message
                    })
                except Exception as e:
                    # Catch exceptions and log the error, but continue to the next file
                    error_message = str(e).strip()
                    print(f"🚨 Error processing {filename}: {error_message}")
                    # You might want to log a partial or error entry here if the student ID was readable
                    # Log the failed file and error message
                    failed_results[subject].append({
                        "filename": filename,
                        "type": type(e).__name__,
                        "img_name": getattr(sheet, "img_name", os.path.splitext(filename)[0]),
                        "stage": getattr(sheet, "processing_stage", "unknown"),
                        "debug_image": getattr(sheet, "debug_marked_path", None),
                        "debug_save_error": getattr(sheet, "debug_save_error", None),
                        "top_boxes_drawn": getattr(sheet, "top_boxes_drawn", 0),
                        "answer_boxes_drawn": getattr(sheet, "answer_boxes_drawn", 0),
                        "subject": getattr(sheet, "subject", None),
                        "subject_type": getattr(sheet, "subject_type", None),
                        "student_id": getattr(sheet, "student_id", None),
                        "error": error_message
                    })
                    
    print("\n--- Processing Complete ---")
    
    # --- Sorting Step ---
    print("Sorting results by filename...")
    
    # Define the numerical sort key helper function here
    import re
    def numerical_sort_key(filename):
      """
      Extracts the room number and page number from the filename for compound numerical sorting.
      Example: 'math_room_304_page_4.png' -> (304, 4)
              'math_room_304_page_10.png' -> (304, 10)
      """
      # Regex to find numbers following 'room_' and 'page_'
      room_match = re.search(r'room_(\d+)', filename)
      page_match = re.search(r'page_(\d+)', filename)
      
      room_num = int(room_match.group(1)) if room_match else 0
      page_num = int(page_match.group(1)) if page_match else 0
      
      # Return a tuple: Python sorts tuples element by element (Room, then Page)
      return (room_num, page_num)
    
    for subject in all_results:
        # Sort the list of entries (dictionaries) using the 'filename' key,
        # but apply the numerical_sort_key to that filename for comparison.
        all_results[subject].sort(key=lambda x: numerical_sort_key(x['filename']))

    fail_py_path = os.path.join(BASE_DIR, "fail.py")
    try:
        with open(fail_py_path, "w", encoding="utf-8") as f:
            f.write("# Auto-generated by omr.py\n")
            f.write("CONTOUR_FAILURES = ")
            f.write(repr(contour_failures))
            f.write("\n")
        print(f"📝 Saved contour failures to **{fail_py_path}**")
    except Exception as e:
        print(f"❌ Failed to write fail.py: {e}")
    
    # Save successful/failed outputs per selected subject in omr-result/<subject>/
    for subject in selected_subjects:
        subject_dir = os.path.join(OMR_RESULT_DIR, subject)
        os.makedirs(subject_dir, exist_ok=True)
        subject_output_json = os.path.join(subject_dir, "output.json")
        subject_fail_json = os.path.join(subject_dir, "fail_log.json")

        try:
            with open(subject_output_json, "w", encoding="utf-8") as f:
                json.dump({subject: all_results.get(subject, [])}, f, indent=2, ensure_ascii=False)
            print(f"✅ Successfully saved {subject} results to **{subject_output_json}**")
        except Exception as e:
            print(f"❌ Failed to write {subject} output JSON: {e}")

        subject_failures = failed_results.get(subject, [])
        if subject_failures:
            try:
                with open(subject_fail_json, "w", encoding="utf-8") as f:
                    json.dump({subject: subject_failures}, f, indent=2, ensure_ascii=False)
                print(f"⚠️ Saved {len(subject_failures)} failures to **{subject_fail_json}**")
            except Exception as e:
                print(f"❌ Failed to write {subject} failure log JSON: {e}")
        else:
            print(f"🎉 No failed files for {subject}.")

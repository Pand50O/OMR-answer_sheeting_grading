import os
import cv2
import numpy as np
import pickle
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCAN_BASE_DIR = os.path.join(BASE_DIR, "answersheet-scan")
SUBJECT_FOLDERS = ["pretest", "posttest"]
DEBUG_DIR = os.path.join(BASE_DIR, "debug-images")


def auto_rotate_if_upside_down(img, img_name=""):
    """
    FE sheet expected orientation has dark borders on LEFT and BOTTOM.
    If detected as TOP and RIGHT instead, rotate 180 degrees.
    """
    if img is None:
        return img

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
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
        print(f"↻ Auto-rotated 180°: {img_name}")
        return cv2.rotate(img, cv2.ROTATE_180)
    return img


def sort_points(points):
    points = sorted(points, key=lambda x: (x[1], x[0]))
    if points[0][0] > points[1][0]:
        points[0], points[1] = points[1], points[0]
    if points[2][0] < points[3][0]:
        points[2], points[3] = points[3], points[2]
    return points


def perspective_transform(img, points):
    max_width = max(
        int(np.hypot(points[0][0] - points[1][0], points[0][1] - points[1][1])),
        int(np.hypot(points[2][0] - points[3][0], points[2][1] - points[3][1])),
    )
    max_height = max(
        int(np.hypot(points[1][0] - points[2][0], points[1][1] - points[2][1])),
        int(np.hypot(points[3][0] - points[0][0], points[3][1] - points[0][1])),
    )
    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(np.array(points, dtype="float32"), dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


def crop_sections(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)

    bin_find_rect_img = cv2.adaptiveThreshold(
        gray_blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        65,
        7,
    )
    _, bin_img = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(bin_find_rect_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = bin_find_rect_img.shape
    filtered = []
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4 or cv2.contourArea(contour) < 0.12 * h * w:
            continue
        filtered.append(approx)

    if len(filtered) != 2:
        raise Exception(f"Found {len(filtered)} candidate rectangles (expected 2)")

    rects = [perspective_transform(bin_img, sort_points(x.reshape(4, 2))) for x in filtered]
    rects.sort(key=lambda x: x.shape[0] * x.shape[1])
    return rects[0], rects[1], bin_find_rect_img, bin_img


def save_all_contours_debug(img, img_name):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
    bin_find_rect_img = cv2.adaptiveThreshold(
        gray_blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        65,
        7,
    )
    contours, _ = cv2.findContours(bin_find_rect_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    debug = img.copy()
    h, w = bin_find_rect_img.shape
    for contour in contours:
        area = cv2.contourArea(contour)
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        color = (0, 255, 255) if (len(approx) == 4 and area >= 0.12 * h * w) else (0, 0, 255)
        cv2.drawContours(debug, [contour], -1, color, 2)

    save_path = os.path.join(DEBUG_DIR, f"{img_name}_contours.jpg")
    cv2.imwrite(save_path, debug)
    print(f"{img_name}: saved contour debug -> {save_path}")


def draw_marks(section_img, marks, threshold=0.45):
    debug = cv2.cvtColor(section_img, cv2.COLOR_GRAY2BGR)
    h, w = section_img.shape
    for (x, y), rect_size in marks:
        x1 = int(x * w)
        y1 = int(y * h)
        x2 = int(x * w + rect_size * h)
        y2 = int(y * h + rect_size * h)
        roi = section_img[y1:y2, x1:x2]
        roi_area = roi.shape[0] * roi.shape[1]
        white = np.sum(roi == 255)
        white_percentage = (white / roi_area) if roi_area > 0 else 0.0
        marked = white_percentage > threshold
        cv2.rectangle(debug, (x1, y1), (x2, y2), (0, 255, 0) if marked else (0, 0, 255), 2)
    return debug


def main():
    selected_subjects = SUBJECT_FOLDERS
    if len(sys.argv) >= 2:
        arg = sys.argv[1].strip().lower()
        if arg in SUBJECT_FOLDERS:
            selected_subjects = [arg]
        else:
            print("Usage: python3 main-read-folder-preview.py [pretest|posttest]")
            return

    print("Controls: [n]=next image, [q]=quit")

    for subject in selected_subjects:
        folder = os.path.join(SCAN_BASE_DIR, subject)
        if not os.path.isdir(folder):
            print(f"Skip missing folder: {folder}")
            continue

        files = sorted([f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
        for name in files:
            path = os.path.join(folder, name)
            img = cv2.imread(path)
            if img is None:
                print(f"Cannot open: {path}")
                continue
            img = auto_rotate_if_upside_down(img, name)

            try:
                top, answer, find_rect_bin, read_bin = crop_sections(img)
            except Exception as e:
                print(f"{name}: crop failed -> {e}")
                save_all_contours_debug(img, os.path.splitext(name)[0])
                continue

            top_marked = cv2.cvtColor(top, cv2.COLOR_GRAY2BGR)
            answer_marked = cv2.cvtColor(answer, cv2.COLOR_GRAY2BGR)

            try:
                with open(os.path.join(BASE_DIR, "pickles", "FE_top.pkl"), "rb") as f:
                    top_marks = pickle.load(f)
                top_marked = draw_marks(top, top_marks)
                print(f"{name}: top marks loaded = {len(top_marks)}")
            except Exception as e:
                print(f"{name}: top mark overlay failed -> {e}")

            try:
                answer_pickle = os.path.join(BASE_DIR, "pickles", f"FE_{subject}_answer.pkl")
                with open(answer_pickle, "rb") as f:
                    answer_marks = pickle.load(f)
                answer_marked = draw_marks(answer, answer_marks)
                print(f"{name}: answer marks loaded ({subject}) = {len(answer_marks)}")
            except Exception as e:
                print(f"{name}: answer mark overlay failed -> {e}")

            cv2.imshow("original", img)
            cv2.imshow("find_rect_bin", find_rect_bin)
            cv2.imshow("read_bin", read_bin)
            cv2.imshow("top", top)
            cv2.imshow("answer", answer)
            cv2.imshow("top_marked", top_marked)
            cv2.imshow("answer_marked", answer_marked)
            print(f"Showing {subject}/{name}")

            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == ord("q"):
                    cv2.destroyAllWindows()
                    return
                if key == ord("n"):
                    break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

import os
import cv2
import numpy as np
import pickle
import sys
import cvzone

TOP_RECT_SIZE = 0.07
ANS_RECT_SIZE = 0.018
TOP_SEC_SCALE = 0.3
ANS_SEC_SCALE = 0.9


def render(marks, preview, section, img, view_state, app_state):
    height_orig, width_orig = img.shape[:2]
    scale = TOP_SEC_SCALE if section == "top" else ANS_SEC_SCALE
    base_w = int(width_orig * scale)
    base_h = int(height_orig * scale)
    canvas = cv2.resize(img, (base_w, base_h))

    zoom = view_state["zoom"]
    pan_x_rel = view_state["pan_x"]
    pan_y_rel = view_state["pan_y"]

    view_w_rel = 1.0 / zoom
    view_h_rel = 1.0 / zoom

    crop_x1 = int(pan_x_rel * base_w)
    crop_y1 = int(pan_y_rel * base_h)
    crop_x2 = int((pan_x_rel + view_w_rel) * base_w)
    crop_y2 = int((pan_y_rel + view_h_rel) * base_h)

    crop_x1 = max(0, min(crop_x1, base_w - 1))
    crop_y1 = max(0, min(crop_y1, base_h - 1))
    crop_x2 = max(crop_x1 + 1, min(crop_x2, base_w))
    crop_y2 = max(crop_y1 + 1, min(crop_y2, base_h))

    cropped_canvas = canvas[crop_y1:crop_y2, crop_x1:crop_x2]
    img = cv2.resize(cropped_canvas, (base_w, base_h))
    height, width = img.shape[:2]

    def map_rel_to_window(rel_val, pan_rel, view_rel, base_dim):
        return int(((rel_val - pan_rel) / view_rel) * base_dim)

    for mark in marks:
        (x, y), rect_size = mark
        rect_w_rel = rect_size * (height_orig / width_orig)
        rect_h_rel = rect_size
        cv2.rectangle(
            img,
            (
                map_rel_to_window(x, pan_x_rel, view_w_rel, width),
                map_rel_to_window(y, pan_y_rel, view_h_rel, height),
            ),
            (
                map_rel_to_window(x + rect_w_rel, pan_x_rel, view_w_rel, width),
                map_rel_to_window(y + rect_h_rel, pan_y_rel, view_h_rel, height),
            ),
            (0, 255, 0),
            1,
        )

    preview_rect_size = TOP_RECT_SIZE if section == "top" else ANS_RECT_SIZE
    preview_w_rel = preview_rect_size * (height_orig / width_orig)
    preview_h_rel = preview_rect_size

    def draw_preview_box(x_rel, y_rel, color):
        cv2.rectangle(
            img,
            (
                map_rel_to_window(x_rel, pan_x_rel, view_w_rel, width),
                map_rel_to_window(y_rel, pan_y_rel, view_h_rel, height),
            ),
            (
                map_rel_to_window(x_rel + preview_w_rel, pan_x_rel, view_w_rel, width),
                map_rel_to_window(y_rel + preview_h_rel, pan_y_rel, view_h_rel, height),
            ),
            color,
            2,
        )

    if app_state["is_pasting"] and app_state["recorded_pattern"]:
        draw_preview_box(preview[0], preview[1], (0, 165, 255))
        for dx, dy in app_state["recorded_pattern"]:
            draw_preview_box(preview[0] + dx, preview[1] + dy, (0, 165, 255))
    else:
        draw_preview_box(preview[0], preview[1], (0, 0, 255))

    cvzone.putTextRect(img, f"Number of marks: {len(marks)}", (10, 30), 1, 1, (0, 255, 0), 2)
    cvzone.putTextRect(img, f"Zoom: {zoom:.1f}x", (10, 70), 1, 1, (255, 0, 0), 2)
    status_text = "Normal"
    status_color = (0, 255, 0)
    if app_state["is_recording"]:
        status_text = f"Recording... ({len(app_state['recorded_pattern']) + 1} pts)"
        status_color = (0, 0, 255)
    elif app_state["is_pasting"]:
        status_text = f"Paste Mode ({len(app_state['recorded_pattern']) + 1} pts)"
        status_color = (0, 165, 255)
    cvzone.putTextRect(img, f"Mode: {status_text}", (10, 110), 1, 1, status_color, 2)
    return img


def mouse_event(event, x, y, flags, param):
    marks, img_shape, section, preview, view_state, app_state = param
    width, height = img_shape

    zoom = view_state["zoom"]
    pan_x = view_state["pan_x"]
    pan_y = view_state["pan_y"]
    view_w_rel = 1.0 / zoom
    view_h_rel = 1.0 / zoom

    rel_x = pan_x + (x / width) * view_w_rel
    rel_y = pan_y + (y / height) * view_h_rel

    if event == cv2.EVENT_LBUTTONDOWN:
        rect_size = TOP_RECT_SIZE if section == "top" else ANS_RECT_SIZE
        if app_state["is_pasting"] and app_state["recorded_pattern"]:
            marks.append(((rel_x, rel_y), rect_size))
            for dx, dy in app_state["recorded_pattern"]:
                marks.append(((rel_x + dx, rel_y + dy), rect_size))
            app_state["history"].append(1 + len(app_state["recorded_pattern"]))
        else:
            marks.append(((rel_x, rel_y), rect_size))
            app_state["history"].append(1)
            if app_state["is_recording"]:
                if app_state["recording_base"] is None:
                    app_state["recording_base"] = (rel_x, rel_y)
                else:
                    dx = rel_x - app_state["recording_base"][0]
                    dy = rel_y - app_state["recording_base"][1]
                    app_state["recorded_pattern"].append((dx, dy))
    elif event == cv2.EVENT_MOUSEMOVE:
        preview[0], preview[1] = rel_x, rel_y


def get_pickle_path(venue, subject, section):
    if section == "top":
        return os.path.join("pickles", f"{venue}_{section}.pkl")
    else:
        return os.path.join("pickles", f"{venue}_{subject}_{section}.pkl")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python label.py <venue> <subject>")
        sys.exit(1)
    venue = sys.argv[1]
    subject = sys.argv[2]

    if venue not in ["FEST", "FE"]:
        print("Venue must be either FEST or FE")
        sys.exit(1)
    if venue == "FEST" and subject not in ["alevel", "tpat3"]:
        print("Subject must be either alevel or tpat3")
        sys.exit(1)
    if venue == "FE" and subject not in ["pretest", "posttest"]:
        print("Subject must be either pretest or posttest")
        sys.exit(1)

    top_path = os.path.join("label_templates", f"{venue}_top.jpg")
    answer_path = os.path.join("label_templates", f"{venue}_{subject}_answer.jpg")
    sections = {
        "top": cv2.imread(top_path),
        "answer": cv2.imread(answer_path),
    }

    for section in sections:
        if sections[section] is None:
            print(f"Could not read {section} section")
            sys.exit(1)
        marks = []
        pickle_path = get_pickle_path(venue, subject, section)
        if os.path.exists(pickle_path):
            with open(pickle_path, "rb") as f:
                marks = pickle.load(f)

        cancel = False
        preview = [0, 0]
        view_state = {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0}
        pan_step = 0.05
        app_state = {
            "is_recording": False,
            "is_pasting": False,
            "recorded_pattern": [],
            "recording_base": None,
            "history": [1] * len(marks),
        }

        section_h, section_w = sections[section].shape[:2]
        section_scale = TOP_SEC_SCALE if section == "top" else ANS_SEC_SCALE
        img_shape = (int(section_w * section_scale), int(section_h * section_scale))

        cv2.namedWindow("Label")
        cv2.setMouseCallback("Label", mouse_event, (marks, img_shape, section, preview, view_state, app_state))

        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                cancel = True
                break
            if key == ord("u") and len(marks) > 0 and len(app_state["history"]) > 0:
                count_to_remove = app_state["history"].pop()
                for _ in range(count_to_remove):
                    if marks:
                        marks.pop()
                if app_state["is_recording"] and len(app_state["recorded_pattern"]) > 0:
                    app_state["recorded_pattern"].pop()
                elif app_state["is_recording"] and len(app_state["recorded_pattern"]) == 0:
                    app_state["recording_base"] = None

            if key == ord("z"):
                view_state["zoom"] += 0.2
            if key == ord("x"):
                view_state["zoom"] = max(1.0, view_state["zoom"] - 0.2)

            view_w_rel = 1.0 / view_state["zoom"]
            view_h_rel = 1.0 / view_state["zoom"]

            if key == ord("a"):
                view_state["pan_x"] = max(0.0, view_state["pan_x"] - pan_step)
            if key == ord("d"):
                view_state["pan_x"] = min(1.0 - view_w_rel, view_state["pan_x"] + pan_step)
            if key == ord("w"):
                view_state["pan_y"] = max(0.0, view_state["pan_y"] - pan_step)
            if key == ord("s"):
                view_state["pan_y"] = min(1.0 - view_h_rel, view_state["pan_y"] + pan_step)

            view_state["pan_x"] = max(0.0, min(1.0 - view_w_rel, view_state["pan_x"]))
            view_state["pan_y"] = max(0.0, min(1.0 - view_h_rel, view_state["pan_y"]))

            if key == ord("r"):
                if not app_state["is_recording"]:
                    app_state["is_recording"] = True
                    app_state["is_pasting"] = False
                    app_state["recorded_pattern"] = []
                    app_state["recording_base"] = None
                else:
                    app_state["is_recording"] = False

            if key == ord("p"):
                if len(app_state["recorded_pattern"]) > 0:
                    app_state["is_pasting"] = not app_state["is_pasting"]
                    app_state["is_recording"] = False

            img = render(marks, preview, section, sections[section].copy(), view_state, app_state)
            cv2.imshow("Label", img)

        if not cancel:
            os.makedirs(os.path.dirname(pickle_path), exist_ok=True)
            with open(pickle_path, "wb") as f:
                pickle.dump(marks, f)


'''
TOP:
1 = cancel
2 = absent
'''

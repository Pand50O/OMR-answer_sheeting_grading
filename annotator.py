from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from io import BytesIO
import pandas as pd

#                start       end
NAME_FIELD = ((270, 800), (430, 800))
SUBJECT_FIELD = ((280, 743), (430, 743))
LOCATION_FIELD = ((280, 726), (430, 726))
ROOM_FIELD = ((280, 708), (430, 708))
DATE_FIELD = ((280, 691), (430, 691))

#           start
ID_FIELD = (475, 792)
SEAT_NO_FIELD = (397.5, 766)
SUBID_FIELD = (442, 792)

ID_CHAR_SPACE = 8
SUBID_CHAR_SPACE = 8
CIRC_RADIUS = 10
CIRC_Y_OFFSET = 10.5
CIRC_X_OFFSET = 12

#                 top-left
SUBID_CIRC_POS = (439.5, 777.5)
ID_CIRC_POS = (472.5, 777.5)

def annotate(answer_sheet_path: str, 
             student_name: tuple[str, str], 
             student_id: str, 
             subject_id: str,
             subject: str,
             seat_no: str,
             exam_loc: str,
             exam_room: str,
             exam_date: str,
             output_path: str):
    reader = PdfReader(answer_sheet_path)
    writer = PdfWriter()

    # Register font
    pdfmetrics.registerFont(TTFont("THSarabun Bold", "THSarabun Bold.ttf"))

    # Create overlay PDF (in-memory)
    buffer = BytesIO()
    cvs = canvas.Canvas(buffer)

    # Annotate on the overlay PDF
    full_name = f"{student_name[0]} {student_name[1]}"
    full_name_font_size = 11
    full_name_width = pdfmetrics.stringWidth(full_name, "THSarabun Bold", full_name_font_size)

    # Adjust font size dynamically for full name
    while full_name_width > NAME_FIELD[1][0] - NAME_FIELD[0][0]:
        full_name_font_size -= 1
        full_name_width = pdfmetrics.stringWidth(full_name, "THSarabun Bold", full_name_font_size)

    # Set final font size
    cvs.setFont("THSarabun Bold", full_name_font_size)

    full_name_textobj = cvs.beginText()
    full_name_textobj.setTextOrigin((NAME_FIELD[0][0] + NAME_FIELD[1][0] - full_name_width) / 2, NAME_FIELD[0][1])
    full_name_textobj.setFillColorRGB(0, 0, 0)
    full_name_textobj.textLine(full_name)
    cvs.drawText(full_name_textobj)

    # Other fields (fixed font size)
    cvs.setFont("THSarabun Bold", 11)

    subject_textobj = cvs.beginText()
    subject_textobj.setTextOrigin((SUBJECT_FIELD[0][0] + SUBJECT_FIELD[1][0] - pdfmetrics.stringWidth(subject, "THSarabun Bold", 11)) / 2, SUBJECT_FIELD[0][1])
    subject_textobj.setFillColorRGB(0, 0, 0)
    subject_textobj.textLine(subject)
    cvs.drawText(subject_textobj)

    location_textobj = cvs.beginText()
    location_textobj.setTextOrigin((LOCATION_FIELD[0][0] + LOCATION_FIELD[1][0] - pdfmetrics.stringWidth(exam_loc, "THSarabun Bold", 11)) / 2, LOCATION_FIELD[0][1])
    location_textobj.setFillColorRGB(0, 0, 0)
    location_textobj.textLine(exam_loc)
    cvs.drawText(location_textobj)

    room_textobj = cvs.beginText()
    room_textobj.setTextOrigin((ROOM_FIELD[0][0] + ROOM_FIELD[1][0] - pdfmetrics.stringWidth(exam_room, "THSarabun Bold", 11)) / 2, ROOM_FIELD[0][1])
    room_textobj.setFillColorRGB(0, 0, 0)
    room_textobj.textLine(exam_room)
    cvs.drawText(room_textobj)

    date_textobj = cvs.beginText()
    date_textobj.setTextOrigin((DATE_FIELD[0][0] + DATE_FIELD[1][0] - pdfmetrics.stringWidth(exam_date, "THSarabun Bold", 11)) / 2, DATE_FIELD[0][1])
    date_textobj.setFillColorRGB(0, 0, 0)
    date_textobj.textLine(exam_date)
    cvs.drawText(date_textobj)

    while len(seat_no) != 2:
        seat_no = "0" + seat_no
    seat_no_textobj = cvs.beginText()
    seat_no_textobj.setTextOrigin(*SEAT_NO_FIELD)
    seat_no_textobj.setCharSpace(ID_CHAR_SPACE)
    seat_no_textobj.setFillColorRGB(0, 0, 0)
    seat_no_textobj.textLine(seat_no)
    cvs.drawText(seat_no_textobj)

    right_id_textobj = cvs.beginText()
    right_id_textobj.setTextOrigin(*ID_FIELD)
    right_id_textobj.setCharSpace(ID_CHAR_SPACE)
    right_id_textobj.setFillColorRGB(0, 0, 0)
    right_id_textobj.textLine(student_id)
    cvs.drawText(right_id_textobj)

    sub_id_textobj = cvs.beginText()
    sub_id_textobj.setTextOrigin(*SUBID_FIELD)
    sub_id_textobj.setCharSpace(SUBID_CHAR_SPACE)
    sub_id_textobj.setFillColorRGB(0, 0, 0)
    sub_id_textobj.textLine(subject_id)
    cvs.drawText(sub_id_textobj)

    for idx, num in enumerate(subject_id):
        cvs.ellipse(
            SUBID_CIRC_POS[0] + idx * CIRC_X_OFFSET,
            SUBID_CIRC_POS[1] - int(num) * CIRC_Y_OFFSET,
            SUBID_CIRC_POS[0] + CIRC_RADIUS + idx * CIRC_X_OFFSET,
            SUBID_CIRC_POS[1] - int(num) * CIRC_Y_OFFSET + CIRC_RADIUS,
            stroke=0, fill=1
        )

    for idx, num in enumerate(student_id):
        cvs.ellipse(
            ID_CIRC_POS[0] + idx * CIRC_X_OFFSET,
            ID_CIRC_POS[1] - int(num) * CIRC_Y_OFFSET,
            ID_CIRC_POS[0] + CIRC_RADIUS + idx * CIRC_X_OFFSET,
            ID_CIRC_POS[1] - int(num) * CIRC_Y_OFFSET + CIRC_RADIUS,
            stroke=0, fill=1
        )

    # Save the overlay PDF
    cvs.save()
    buffer.seek(0)

    # Read overlay and merge with original PDF
    overlay_reader = PdfReader(buffer)
    page = reader.pages[0]
    page.merge_page(overlay_reader.pages[0])
    writer.add_page(page)

    # Save the annotated PDF
    with open(output_path, "wb") as f:
        writer.write(f)

if __name__ == "__main__":
    df = pd.read_csv("camper_FE18.csv").set_index("camperId")
    for idx, row in df.iterrows():
        annotate("./2024fe-answer-sheet.pdf",
                 (row["name"], row["surname"]),
                 str(idx),
                 "11",
                 "Pretest",
                 str(row["seat_no"]),
                 "อาคาร 3 คณะวิศวกรรมศาสตร์",
                 str(row["room"]),
                 "19 พฤษภาคม 2568",
                 f"./camper-answer-sheet/room-{row["room"]}/{idx}_{row["name"]}_{row["surname"]}.pdf"
        )
        print(f"annotated {idx} {row["name"]} {row["surname"]}")

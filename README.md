# FE Answer Sheet Grader

This project was developed with AI assistance and is designed to help grade filled-in answer sheets used at the **FEST** and **FE** camps.

The system processes scanned or photographed answer sheets, reads the marked answers, and compares them with the answer key to calculate scores.

## Main Folders

- `answersheet-scan/` — Scanned answer sheets, organized by exam set
- **[View mark detection examples in `debug-images/` →](debug-images/)**
- `answer-grader/` — Answer key files used for grading
- `omr-result/` — Answers read from the scanned sheets
- `graded-results/` — Processed grading results
- `label_templates/` and `pickles/` — Templates and data used to locate answer areas on the sheets

## Basic Usage

Place answer sheet images in a subfolder inside `answersheet-scan/`, then run the answer-reading program:

```bash
python3 omr.py all
```

To process a specific exam set found in `answersheet-scan/`, run:

```bash
python3 omr.py pretest
```

After the answers have been read, calculate the scores:

```bash
python3 grader.py
```

The program saves the extracted answers in `omr-result/` and the processed scores in `graded-results/`.

> Review the scanned images and extracted answers before using the scores. Image quality and how answers are marked can affect the results.

import pandas as pd
import io 
import matplotlib.pyplot as plt
import numpy as np
import os
import matplotlib.font_manager as fm

# =========================================
# CONFIG: Add all subject CSV files here
# =========================================
DATA_FILES = {
    "math": "graded_math.csv",
    "physics": "graded_physics.csv",
    "tpat3": "graded_tpat3.csv",
}

SUBJECT_COLUMNS_MAP = {
    "math": ['Algebra 1', 'Algebra 2', 'Algebra 3', 'Stat and Prob', 'Calculus'],
    "physics": ['กลศาสตร์', 'คลื่น แสง เสียง', 'ไฟฟ้า', 'สมบัติสสาร', 'ฟิสิกส์ใหม่'],
    "tpat3": ['การทดสอบความถนัดด้านตัวเลข', 'การทดสอบความถนัดด้านมิติสัมพันธ์', 'การทดสอบความถนัดด้านเชิงกล', 'ความคิดเชิงวิทยาศาสตร์', 'ความสนใจข่าวสารความรู้ทางด้านวิทยาศาสตร์'],
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BASE = os.path.join(BASE_DIR, "chart")
os.makedirs(OUTPUT_BASE, exist_ok=True)

# NEW: Create the accuracy folder
ACCURACY_DIR = os.path.join(BASE_DIR, "accuracy")
os.makedirs(ACCURACY_DIR, exist_ok=True)

# Function: parse x/y score text like "2/6"
def parse_score(score_str):
    if pd.isna(score_str):
        # Return three NaN values for score, total, and empty string
        return pd.Series([np.nan, np.nan, ""])
    try:
        score, total = map(int, score_str.split('/'))
        return pd.Series([score, total, score_str])
    except:
        return pd.Series([np.nan, np.nan, ""])
        
# 🛠️ Group Mean Chart with Mean/SD and Frequency Tables (TOTAL SCORE added to both tables)
def create_mean_chart(subject_name, categories, mean_values, std_values, df):
    # --- 1. Calculate Overall Group Mean, SD, Min, and Max (Percentages and Actual Scores) ---
    sum_score_cols = [f'{col}_score' for col in categories]
    sum_total_cols = [f'{col}_total' for col in categories]
    
    df_temp = df.copy()
    df_temp['Overall_Score'] = df_temp[sum_score_cols].sum(axis=1)
    df_temp['Overall_Total'] = df_temp[sum_total_cols].sum(axis=1)
    df_temp['Overall_Percent'] = (df_temp['Overall_Score'] / df_temp['Overall_Total'] * 100).fillna(0)

    # Percentage Stats
    overall_mean_percent = df_temp['Overall_Percent'].mean()
    overall_sd_percent = df_temp['Overall_Percent'].std()
    overall_min_percent = df_temp['Overall_Percent'].min()
    overall_max_percent = df_temp['Overall_Percent'].max()
    
    # Actual Score Stats
    overall_mean_actual = df_temp['Overall_Score'].mean()
    overall_min_actual = df_temp['Overall_Score'].min()
    overall_max_actual = df_temp['Overall_Score'].max()
    overall_sd_actual = df_temp['Overall_Score'].std() # Overall SD (Score)
    
    # --- 2. Chart Setup ---
    mean_values_closed = mean_values + mean_values[:1]
    angles = [i / float(len(categories)) * 2 * np.pi for i in range(len(categories))]
    angles_closed = angles + angles[:1]
    
    # Font Setup
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FONT_PATH = os.path.join("/Users/panda500/Library/Fonts","THSarabunNew.ttf")
    fm.fontManager.addfont(FONT_PATH)
    plt.rcParams['font.family'] = "Sarabun"
    
    # FONT SIZE SETTINGS
    plt.rcParams['font.size'] = 12     
    plt.rcParams['axes.titlesize'] = 18
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    
    # Increased Figure width to 10
    fig, ax = plt.subplots(figsize=(10, 11), subplot_kw=dict(polar=True)) 

    # Plot Mean Score Line
    ax.plot(angles_closed, mean_values_closed, color='blue', linewidth=2, marker='o', markersize=8, label="Group Mean Score")
    ax.fill(angles_closed, mean_values_closed, 'blue', alpha=0.2)
    ax.set_xticks(angles)
    ax.set_xticklabels(categories)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_yticklabels([f'{i}%' for i in np.arange(0, 101, 20)])
    ax.set_ylim(0, 100)

    # Title and Legend
    ax.set_title(f"Group Mean Performance: {subject_name.upper()}", size=18, va='bottom', pad=30, fontweight='bold')
    plt.legend(loc='upper right', bbox_to_anchor=(1.2, 1.15))

    # =========================================
    # 3. ADD MEAN/SD/MIN/MAX DATA TABLE (With Total Row)
    # =========================================
    
    mean_sd_cell_text = []
    
    # Calculate Min/Max for Percentages AND Actual Scores
    category_percent_min_max = {}
    category_actual_stats = {}
    
    for col in categories: 
        # Percentage stats
        percent_scores = (df[f"{col}_score"] / df[f"{col}_total"] * 100).fillna(0)
        category_percent_min_max[col] = (percent_scores.min(), percent_scores.max())
        
        # Actual score stats
        actual_scores = df[f"{col}_score"].fillna(0)
        category_actual_stats[col] = (actual_scores.mean(), actual_scores.min(), actual_scores.max(), actual_scores.std())

    for category, mean_percent, sd_percent in zip(categories, mean_values, std_values):
        c_min_percent, c_max_percent = category_percent_min_max[category]
        c_mean_actual, c_min_actual, c_max_actual, c_std_actual = category_actual_stats[category]
        
        mean_sd_cell_text.append([
            category, 
            f'{c_mean_actual:.2f}',
            f'{c_min_actual:.2f}',
            f'{c_max_actual:.2f}',
            f'{c_std_actual:.2f}',  # SD (Score)
            f'{mean_percent:.2f}',    
            f'{c_min_percent:.2f}',   
            f'{c_max_percent:.2f}',   
            f'{sd_percent:.2f}'             
        ])
    
    # Add Overall Total Row
    mean_sd_cell_text.append([
        "TOTAL SCORE",
        f'{overall_mean_actual:.2f}',
        f'{overall_min_actual:.2f}',
        f'{overall_max_actual:.2f}',
        f'{overall_sd_actual:.2f}',  # Overall SD (Score)
        f'{overall_mean_percent:.2f}',
        f'{overall_min_percent:.2f}',
        f'{overall_max_percent:.2f}',
        f'{overall_sd_percent:.2f}'
    ])

    # Update Column Labels
    mean_sd_columns = ['Category', 'Mean (Score)', 'Min (Score)', 'Max (Score)', 'SD (Score)', 'Mean (%)', 'Min (%)', 'Max (%)', 'SD (%)']
    
    table_mean_sd = plt.table(
        cellText=mean_sd_cell_text,
        colLabels=mean_sd_columns,
        loc='bottom',  
        bbox=[0.0, -0.27, 1.0, 0.17] 
    )

    # Style Mean/SD Table
    table_mean_sd.auto_set_font_size(False)
    table_mean_sd.set_fontsize(10)
    table_mean_sd.auto_set_column_width(col=list(range(len(mean_sd_columns))))
    for (row, col), cell in table_mean_sd.get_celld().items():
        cell.set_edgecolor('lightgray')
        if row == 0:
            cell.set_facecolor('#cccccc')
            cell.set_text_props(fontweight='bold')
        elif row == len(categories) + 1:
            cell.set_facecolor('#ffffb3') # Highlight Total Row
            cell.set_text_props(fontweight='bold')
        else:
             cell.set_facecolor('white')


    # =========================================
    # 4. ADD SCORE FREQUENCY TABLE (With Total Row)
    # =========================================
    
    # Define score bins and labels
    bins = [0, 20, 40, 60, 80, 100]
    labels = ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']
    
    frequency_data = {}
    for col in categories: 
        percent_scores = (df[f"{col}_score"] / df[f"{col}_total"] * 100).fillna(0)
        binned_scores = pd.cut(percent_scores, bins=bins, labels=labels, right=False, include_lowest=True)
        frequency = binned_scores.value_counts().reindex(labels, fill_value=0)
        frequency_data[col] = frequency.tolist()

    df_freq = pd.DataFrame(frequency_data, index=labels).T
    
    # --- Calculate Total Score Frequency Distribution ---
    overall_binned_scores = pd.cut(df_temp['Overall_Percent'], bins=bins, labels=labels, right=False, include_lowest=True)
    overall_frequency = overall_binned_scores.value_counts().reindex(labels, fill_value=0)
    overall_freq_list = overall_frequency.astype(int).astype(str).tolist() # Convert to list of strings
    
    # Prepare cell text for the Matplotlib table
    freq_cell_text = []
    for category in categories:
        freq_cell_text.append([category] + df_freq.loc[category].astype(int).astype(str).tolist())
    
    # Append the TOTAL SCORE row
    freq_cell_text.append(["TOTAL SCORE"] + overall_freq_list)
    
    freq_columns = ['Category'] + labels
    
    table_freq = plt.table(
        cellText=freq_cell_text,
        colLabels=freq_columns,
        loc='bottom',  
        bbox=[0.0, -0.55, 1.0, 0.25] 
    )

    # Style Frequency Table
    table_freq.auto_set_font_size(False)
    table_freq.set_fontsize(10)
    table_freq.auto_set_column_width(col=list(range(len(freq_columns))))
    for (row, col), cell in table_freq.get_celld().items():
        cell.set_edgecolor('lightgray')
        if row == 0:
            cell.set_facecolor('#e6e6e6')
            cell.set_text_props(fontweight='bold')
        # Highlight the Total Score row
        elif row == len(categories) + 1:
            cell.set_facecolor('#ffffb3') # Highlight Total Row
            cell.set_text_props(fontweight='bold')
        else:
             cell.set_facecolor('white')

    # Save Chart
    save_path = os.path.join(OUTPUT_BASE, "Group_Summary", f"{subject_name}_MeanChart.jpg")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, bbox_inches='tight')
    plt.close()
    
# 🛠️ Individual Chart with Table (Total Score Row Added - Unchanged from previous step)
def create_student_chart(student_id, subject_name, categories, student_values, student_scores, student_totals, mean_values, std_values):
    # --- 1. Chart Setup ---
    student_values_closed = student_values + student_values[:1]
    mean_values_closed = mean_values + mean_values[:1]
    
    angles = [i / float(len(categories)) * 2 * np.pi for i in range(len(categories))]
    angles_closed = angles + angles[:1]
    
    # Font Setup
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FONT_PATH = os.path.join("/Users/panda500/Library/Fonts","THSarabunNew.ttf")
    fm.fontManager.addfont(FONT_PATH)
    plt.rcParams['font.family'] = "Sarabun"
    
    # FONT SIZE SETTINGS
    plt.rcParams['font.size'] = 12     
    plt.rcParams['axes.titlesize'] = 18
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    
    fig, ax = plt.subplots(figsize=(7, 9), subplot_kw=dict(polar=True)) 

    # Plotting
    ax.plot(angles_closed, student_values_closed, color='red', linewidth=1.2, label="Student Score")
    ax.fill(angles_closed, student_values_closed, 'red', alpha=0.2)
    ax.plot(angles_closed, mean_values_closed, color='blue', linewidth=1.2, linestyle='dashed', label="Mean Score")
    ax.set_xticks(angles)
    ax.set_xticklabels(categories)
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_yticklabels([f'{i}%' for i in np.arange(0, 101, 20)])
    ax.set_ylim(0, 100)
    ax.set_title(f"{subject_name.upper()} - Student {str(student_id)}", size=16, va='bottom', pad=30, fontweight='bold')
    plt.legend(loc='upper right', bbox_to_anchor=(1.2, 1.15))

    # =========================================
    # 2. ADD DATA TABLE BELOW THE CHART 
    # =========================================
    cell_text = []
    
    # Calculate Totals
    total_student_score = np.nansum(student_scores)
    total_possible_score = np.nansum(student_totals)
    total_percentage = (total_student_score / total_possible_score * 100) if total_possible_score > 0 else 0
    
    # Add individual category rows
    for category, score, total, percent in zip(categories, student_scores, student_totals, student_values):
        score_display = int(score) if pd.notna(score) else 'N/A'
        total_display = int(total) if pd.notna(total) else 'N/A'
        
        cell_text.append([
            category, 
            f'{score_display}/{total_display}',
            f'{percent:.1f}%'
        ])
        
    # Add Total Score Row
    cell_text.append([
        "TOTAL SCORE",
        f'{int(total_student_score)}/{int(total_possible_score)}',
        f'{total_percentage:.1f}%'
    ])

    columns = ['Category', 'Score', 'Percentage']
    
    table = plt.table(
        cellText=cell_text,
        colLabels=columns,
        loc='bottom',
        bbox=[0.05, -0.27, 0.9, 0.22] 
    )

    # Style Table
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(columns))))
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('lightgray')
        if row == 0:
            cell.set_facecolor('#cccccc') 
            cell.set_text_props(fontweight='bold')
        elif row == len(categories) + 1:
            cell.set_facecolor('#ffffb3') # Highlight Total Row
            cell.set_text_props(fontweight='bold')
        else:
             cell.set_facecolor('white')

    # Save Chart
    save_path = os.path.join(OUTPUT_BASE, str(student_id), f"{subject_name}.jpg")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, bbox_inches='tight')
    plt.close()

# =========================================
# Main Loop per Subject File
# =========================================
for subject_name, filename in DATA_FILES.items():
    file_path = os.path.join(BASE_DIR, "graded-results", filename)
    subject_cols = SUBJECT_COLUMNS_MAP[subject_name]
    
    print(file_path)
    print(f"\n📘 Processing {subject_name} file: {filename}")
    df = pd.read_csv(file_path)

    # Filter for 'present' students HERE
    df = df[df["status"] == "present"].copy()
    
    for col in subject_cols:
        df[[f"{col}_score", f"{col}_total", f"{col}_str"]] = df[col].apply(parse_score)

    mean_scores = []
    std_scores = []
    accuracy_data = [] # <-- NEW: List to hold accuracy data for the CSV
    sum_score_cols = [f'{col}_score' for col in subject_cols]
    sum_total_cols = [f'{col}_total' for col in subject_cols]

    for col in subject_cols:
        # Calculate mean scores
        total_score = df[f"{col}_score"].sum()
        total_possible = df[f"{col}_total"].sum()
        mean_percent = (total_score / total_possible * 100) if total_possible > 0 else 0
        mean_scores.append(mean_percent)

        # Calculate percentage scores for SD calculation
        percent_scores = (df[f"{col}_score"] / df[f"{col}_total"] * 100).fillna(0)
        std_scores.append(percent_scores.std() if len(percent_scores) > 1 else 0)

        # <-- NEW: Add data for accuracy CSV
        accuracy_data.append({
            "Category": col,
            "Total_Score_Achieved": total_score,
            "Total_Score_Possible": total_possible,
            "Accuracy (%)": f"{mean_percent:.2f}"
        })

    # 🟢 Generate Group Summaries (Image only)
    print(f"   -> Generating Group Mean Summary (Image) for {subject_name}...")
    # Pass the filtered dataframe to the chart function
    create_mean_chart(subject_name, subject_cols, mean_scores, std_scores, df) 
    
    # Individual student charts
    # This loop also iterates over the filtered dataframe
    for _, row in df.iterrows():
        sid = str(row["id"])
        sid = sid.zfill(7)
        
        student_percent = []
        student_scores = [] 
        student_totals = [] 
        
        for c in subject_cols:
            score = row[f"{c}_score"]
            total = row[f"{c}_total"]
            
            student_percent.append((score / total * 100) if total > 0 else 0)
            student_scores.append(score)
            student_totals.append(total)

        # Pass all data to student chart function
        create_student_chart(sid, subject_name, subject_cols, student_percent, student_scores, student_totals, mean_scores, std_scores)

    # --- NEW: Save Accuracy CSV File ---
    
    # Calculate Overall Total Accuracy
    df['Overall_Score'] = df[sum_score_cols].sum(axis=1)
    df['Overall_Total'] = df[sum_total_cols].sum(axis=1)
    total_overall_score = df['Overall_Score'].sum()
    total_overall_possible = df['Overall_Total'].sum()
    accuracy_overall_percent = (total_overall_score / total_overall_possible * 100) if total_overall_possible > 0 else 0
    
    accuracy_data.append({
        "Category": "TOTAL SCORE",
        "Total_Score_Achieved": total_overall_score,
        "Total_Score_Possible": total_overall_possible,
        "Accuracy (%)": f"{accuracy_overall_percent:.2f}"
    })
    
    # Create DataFrame and Save
    df_accuracy = pd.DataFrame(accuracy_data)
    save_path = os.path.join(ACCURACY_DIR, f"{subject_name}_accuracy.csv")
    df_accuracy.to_csv(save_path, index=False, encoding='utf-8-sig')
    print(f"   -> Saving accuracy summary to: {save_path}")
    # --- End of New Section ---

print("\n✅ All charts and accuracy files generated.")
print("   - Individual student charts are in: /chart/<student_id>/")
print("   - Group mean summary charts (image only) are in: /chart/Group_Summary/")
print(f"   - Accuracy CSV files are in: /{os.path.basename(ACCURACY_DIR)}/")
import os
import glob
from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description="Process BIDS derivatives.")
parser.add_argument(
    "bids_derivatives_dir",
    type=str,
    help="Path to the root BIDS derivatives directory."
)

args = parser.parse_args()

bids_derivatives_dir = args.bids_derivatives_dir

# Define the root BIDS derivatives directory
#bids_derivatives_dir = "/data0/udit/derivative_ABIDEII-KKI_1"

# Define pattern for BOLD files (flexible for runs and space)
bold_pattern = "sub-*/ses-*/func/*res-2_desc-preproc_bold.nii.gz"

# Step 1: Identify all subjects in the directory
all_subjects = {d.name for d in Path(bids_derivatives_dir).glob("sub-*") if d.is_dir()}

# Step 2: Collect all subject-session-run-task combinations from BOLD files
subject_session_run_pairs = {}
bold_files = glob.glob(os.path.join(bids_derivatives_dir, bold_pattern), recursive=True)

for bold_file in bold_files:
    filename = os.path.basename(bold_file)
    parts = filename.split('_')
    
    subject = next(part for part in parts if part.startswith("sub-"))
    session = next((part for part in parts if part.startswith("ses-")), "")
    task = next((part for part in parts if part.startswith("task-")), "")
    run = next((part for part in parts if part.startswith("run-")), "")
    
    if not session and "ses-" in bold_file:
        session = [part for part in bold_file.split('/') if part.startswith("ses-")][0]
    
    key = (subject, session, task, run)
    if key not in subject_session_run_pairs:
        subject_session_run_pairs[key] = {}
    
    subject_session_run_pairs[key]["bold"] = bold_file

# Step 3: Add subjects with no BOLD files
for subject in all_subjects:
    # Check for sessions (default to ses-01 if present, else empty)
    session_dirs = glob.glob(os.path.join(bids_derivatives_dir, subject, "ses-*"))
    sessions = [os.path.basename(d) for d in session_dirs] if session_dirs else [""]
    
    for session in sessions:
        # Assume task-rest as default (adjust if needed)
        key = (subject, session, "task-rest", "")
        if key not in subject_session_run_pairs:
            subject_session_run_pairs[key] = {}  # No BOLD file yet

# Step 4: Check for BOLD and confounds files
missing_files = {}
for (subject, session, task, run), files_dict in subject_session_run_pairs.items():
    # Check BOLD file
    bold_file = files_dict.get("bold")
    if not bold_file:
        # Construct expected BOLD path (simplified, adjust space/res as needed)
        bold_parts = [subject]
        if session:
            bold_parts.append(session)
        if task:
            bold_parts.append(task)
        if run:
            bold_parts.append(run)
        bold_parts.append("space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz")
        bold_filename = "_".join(bold_parts)
        bold_file = os.path.join(bids_derivatives_dir, subject, session or "", "func", bold_filename)
        if not os.path.exists(bold_file):
            if (subject, session, task, run) not in missing_files:
                missing_files[(subject, session, task, run)] = []
            missing_files[(subject, session, task, run)].append("bold")
        else:
            files_dict["bold"] = bold_file

    # Check confounds file if BOLD exists
    if "bold" in files_dict:
        bold_file = files_dict["bold"]
        filename = os.path.basename(bold_file)
        parts = filename.split('_')
        confound_parts = [part for part in parts if part.startswith(("sub-", "ses-", "task-", "run-"))]
        confound_parts.append("desc-confounds_timeseries.tsv")
        confound_filename = "_".join(confound_parts)
        confound_file = os.path.join(os.path.dirname(bold_file), confound_filename)
        
        if os.path.exists(confound_file):
            files_dict["confounds"] = confound_file
        else:
            if (subject, session, task, run) not in missing_files:
                missing_files[(subject, session, task, run)] = []
            missing_files[(subject, session, task, run)].append("confounds")

# Step 5: Report results
print("Preprocessing Check Results:")
print("---------------------------")
for (subject, session, task, run) in sorted(subject_session_run_pairs.keys()):
    session_str = f" {session}" if session else ""
    task_str = f" {task}" if task else ""
    run_str = f" {run}" if run else ""
    if (subject, session, task, run) in missing_files:
        missing = ", ".join(missing_files[(subject, session, task, run)])
        print(f"{subject}{session_str}{task_str}{run_str}: INCOMPLETE (Missing: {missing})")
    else:
        print(f"{subject}{session_str}{task_str}{run_str}: COMPLETE")

# Summary
total_pairs = len(subject_session_run_pairs)
complete_pairs = total_pairs - len(missing_files)
print("\nSummary:")
print(f"Total subject-session-task-run pairs: {total_pairs}")
print(f"Complete: {complete_pairs}")
print(f"Incomplete: {len(missing_files)}")
if missing_files:
    print("Pairs with missing files:")
    for (subject, session, task, run), missing in sorted(missing_files.items()):
        session_str = f" {session}" if session else ""
        task_str = f" {task}" if task else ""
        run_str = f" {run}" if run else ""
        print(f"  {subject}{session_str}{task_str}{run_str}: {', '.join(missing)}")

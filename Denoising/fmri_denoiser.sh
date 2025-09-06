#!/bin/bash

# --- Default Settings ---
N_JOBS=4
DERIVS_DIR=""
OUTPUT_DIR=""
TR=""        # Default to empty, so python script will auto-detect
CONFOUND_COLS=""  # NEW: comma-separated list passed through to Python
LOW_PASS=""       # NEW: optional override of default 0.1
HIGH_PASS=""      # NEW: optional override of default 0.01
GSR_FLAG=""       # NEW: explicit flag to pass --gsr or --no_gsr
FORCE=0           # NEW: overwrite existing outputs if set

# --- Help/Usage Function ---
usage() {
    echo "Usage: $0 -i <fmriprep_dir> -o <output_dir> [OPTIONS]"
    echo ""
    echo "This script runs fMRI denoising in parallel on fMRIPrep derivatives."
    echo ""
    echo "Required Arguments:"
    echo "  -i --input -d, --derivs    Path to the fMRIPrep derivatives directory."
    echo "  -o, --output               Path to the directory where cleaned files will be saved."
    echo ""
    echo "Optional Arguments:"
    echo "  -j, --jobs                 Number of parallel jobs to run (default: ${N_JOBS})."
    echo "  -tr, --tr                  Repetition Time (TR) in seconds. Overrides auto-detection."
    echo "  -col, --confound_columns   Comma-separated confound column names to use (overrides defaults)."
    echo "  -L, --low_pass             Low-pass cutoff in Hz (default: 0.1)."
    echo "  -H, --high_pass            High-pass cutoff in Hz (default: 0.01)."
    echo "  -G, --gsr                  Enable Global Signal Regression (GSR)."
    echo "      --no_gsr               Disable Global Signal Regression."
    echo "      --force                Overwrite existing denoised files."
    echo "  -h, --help                 Display this help message and exit."
    exit 1
}

# --- Parse Command-Line Arguments ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -i|-d|--input|--derivs) DERIVS_DIR="$2"; shift ;;
        -o|--output)            OUTPUT_DIR="$2"; shift ;;
        -j|--jobs)              N_JOBS="$2"; shift ;;
        -tr|--tr)               TR="$2"; shift ;;
        -col|--confound_columns) CONFOUND_COLS="$2"; shift ;;
        -L|--low_pass)          LOW_PASS="$2"; shift ;;
        -H|--high_pass)         HIGH_PASS="$2"; shift ;;
        -G|--gsr)               GSR_FLAG="--gsr" ;;
        --no_gsr)               GSR_FLAG="--no_gsr" ;;
        --force)                FORCE=1 ;;
        -h|--help) usage ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# --- Validate Required Arguments ---
if [[ -z "$DERIVS_DIR" ]] || [[ -z "$OUTPUT_DIR" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# --- Print Settings for Confirmation ---
echo "---------------------------------------------------------"
echo "        fMRI Denoising Batch Process Configuration       "
echo "---------------------------------------------------------"
echo "Input derivatives dir : $DERIVS_DIR"
echo "Output dir            : $OUTPUT_DIR"
echo "Parallel jobs         : $N_JOBS"
echo "TR (sec)              : ${TR:-auto-detect}"
echo "Confound columns      : ${CONFOUND_COLS:-defaults}" 
echo "Low-pass cutoff (Hz)  : ${LOW_PASS:-0.1}"
echo "High-pass cutoff (Hz) : ${HIGH_PASS:-0.01}"
echo "GSR setting           : ${GSR_FLAG:-default (disabled)}"
echo "Overwrite existing?   : $( [[ $FORCE -eq 1 ]] && echo YES || echo NO )"
echo "---------------------------------------------------------"

read -p "Do you want to proceed with these settings? (yes/no): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Aborted by user."
    exit 1
fi

# --- Main Logic ---
mkdir -p "$OUTPUT_DIR"

process_subject() {
    local nifti_file="$1"
    local base_name
    base_name=$(basename "$nifti_file" | sed 's/_space-MNI152NLin2009cAsym_desc-preproc_bold\.nii\.gz//')

    local confounds_file="${nifti_file%/*}/${base_name}_desc-confounds_timeseries.tsv"
    local output_file="${OUTPUT_DIR}/${base_name}_desc-denoised_bold.nii.gz"

    if [[ -f "$output_file" && $FORCE -eq 0 ]]; then
        echo "[SKIP] Denoised file already exists: $output_file"
        return
    fi

    echo "---------------------------------------------------------"
    echo "Processing Subject: ${base_name}"
    echo "---------------------------------------------------------"

    local python_cmd=(
        python denoise_fmri.py
        "$nifti_file"
        "$confounds_file"
        "$output_file"
    )

    [[ -n "$TR" ]] && python_cmd+=("--t_r" "$TR")
    [[ -n "$CONFOUND_COLS" ]] && python_cmd+=("--confound_columns" "$CONFOUND_COLS")
    [[ -n "$LOW_PASS" ]] && python_cmd+=("--low_pass" "$LOW_PASS")
    [[ -n "$HIGH_PASS" ]] && python_cmd+=("--high_pass" "$HIGH_PASS")
    [[ -n "$GSR_FLAG" ]] && python_cmd+=("$GSR_FLAG")

    "${python_cmd[@]}"
}

export -f process_subject
export OUTPUT_DIR TR CONFOUND_COLS LOW_PASS HIGH_PASS GSR_FLAG FORCE

find "$DERIVS_DIR" -type f -name "*_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz" | \
    parallel -j "$N_JOBS" process_subject {}

echo "All denoising jobs are complete."

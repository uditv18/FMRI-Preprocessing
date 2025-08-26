#!/bin/bash

# Define the paths
DATA_DIR=/data0/udit/ABIDEII-KKI_1-BIDS
OUTPUT_DIR=/data0/udit/derivative_ABIDEII-KKI_1/
LICENSE_FILE=/data0/udit/license.txt
WORK_SPACE=/home/brojen/udit-workspace/

# Create a dedicated workspace
mkdir -p $WORK_SPACE/logs

# Ensure required environment variables are set
if [ -z "$DATA_DIR" ]; then
  echo "Error: DATA_DIR is not set. Please set it to the directory containing your fMRI data."
  exit 1
fi

if [ -z "$OUTPUT_DIR" ]; then
  echo "Error: OUTPUT_DIR is not set. Please set it to the directory where you want the results to be saved."
  exit 1
fi

if [ -z "$LICENSE_FILE" ]; then
  echo "Error: LICENSE_FILE is not set. Please set it to the path of your FreeSurfer license file."
  exit 1
fi

# Get the list of subjects from the data directory
SUBJECTS=($(ls -d $DATA_DIR/sub-* | xargs -n 1 basename))


process_subject() {
  SUBJECT=$1
  DATA_DIR=$2
  OUTPUT_DIR=$3
  LICENSE_FILE=$4
  WORK_SPACE=$5
  
  # Create a unique temp directory for each subject
  TEMP_DIR="$WORK_SPACE/$SUBJECT/temp"
  mkdir -p $TEMP_DIR
  echo "$TEMP_DIR"
  
  # Check if the final preprocessed file already exists (based on the naming pattern)
#  FINAL_FILE="$OUTPUT_DIR/$SUBJECT/ses-01/func/${SUBJECT}_task-rest_space-MNI152NLin2009cAsym_desc-preproc_bold.nii.gz"
#  if ls $FINAL_FILE 1> /dev/null 2>&1; then
#    echo "Subject $SUBJECT has already been processed. Final file exists. Skipping..."
#    return
#  fi


  # File checking with nullglob
  shopt -s nullglob
  FINAL_FILES=("$OUTPUT_DIR/$SUBJECT"/ses-01/func/"${SUBJECT}"*_task-rest_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz)
  shopt -u nullglob

  if [ ${#FINAL_FILES[@]} -gt 0 ]; then
    echo "✅ Subject $SUBJECT has already been processed. Skipping..."
    return
  else
    echo "⏩ Preprocessing $SUBJECT ..."
  fi


  echo "Processing subject: $SUBJECT"
  START_TIME=$(date +%s)

  # Run fMRIPrep
  docker run --rm \
    -v "$DATA_DIR:/data:ro" \
    -v "$OUTPUT_DIR:/out" \
    -v "$LICENSE_FILE:/opt/freesurfer/license.txt" \
    -v "$TEMP_DIR:/work" \
    nipreps/fmriprep:latest /data /out participant --fs-license-file /opt/freesurfer/license.txt \
    --participant_label "$SUBJECT" \
    --work-dir /work \
    --output-spaces MNI152NLin2009cAsym:res-2 \
    --omp-nthreads 18 \
    --verbose \
    &> "$WORK_SPACE/logs/fmriprep_$SUBJECT.log"
    
  # Capture the exit status of the docker command
  EXIT_STATUS=$?
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))
  echo "Time taken for subject $SUBJECT: $DURATION seconds"
  if [ $EXIT_STATUS -eq 0 ]; then
    echo "✅ Data preprocessing for subject $SUBJECT is done."
  else
    echo "🆘 Error: fMRIPrep failed for subject $SUBJECT. Please check the logs in $WORK_SPACE/logs for details."
  fi
}
export -f process_subject

parallel --jobs 2 --line-buffer process_subject {1} {2} {3} {4} {5} ::: "${SUBJECTS[@]}" ::: "$DATA_DIR" ::: "$OUTPUT_DIR" ::: "$LICENSE_FILE" ::: "$WORK_SPACE"

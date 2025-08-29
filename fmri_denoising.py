# Denoise fMRI NIfTI file using voxelwise regression with confounds from fMRIPrep
# This script performs: motion regression, physiological noise removal, spike regression, and optional filtering

import numpy as np
import nibabel as nib
import pandas as pd
from nilearn.image import clean_img
from nilearn.maskers import NiftiMasker

def denoise_voxelwise_nifti(nifti_path, confounds_path, output_path,
                             confound_columns=None,
                             low_pass=0.1, high_pass=0.01, t_r=2.0,
                             use_gsr=True):
    """
    Denoise a 4D fMRI NIfTI using confounds from fMRIPrep.

    Parameters:
        nifti_path: str - Path to preprocessed BOLD NIfTI file
        confounds_path: str - Path to fMRIPrep confounds .tsv file
        output_path: str - Path to save the cleaned NIfTI file
        confound_columns: list of str - Optional list of specific confound columns to use
        low_pass: float - Low-pass filter cutoff in Hz
        high_pass: float - High-pass filter cutoff in Hz
        t_r: float - Repetition time in seconds
        use_gsr: bool - Whether to include global signal regression (GSR)
    """
    print("Loading fMRI image...")
    img = nib.load(nifti_path)

    print("Loading confounds file...")
    confounds_df = pd.read_csv(confounds_path, sep='\t').fillna(0)

    # Default confounds: motion, physio, spikes, global
    if confound_columns is None:
        confound_columns = [
            'trans_x', 'trans_y', 'trans_z',
            'rot_x', 'rot_y', 'rot_z',          # motion
            'white_matter', 'csf'               # physiological
        ]

        # Include spike regressors for frames [45, 46, 51, 86, 87, 108, 109, 153]
        # If fMRIPrep already created motion_outlier regressors, we add them
        spike_cols = [col for col in confounds_df.columns if 'motion_outlier' in col]
        if spike_cols:
            confound_columns += spike_cols
        else:
            print("Adding custom spike regressors for timepoints with FD/DVARS spikes...")
            spike_indices = [45, 46, 51, 86, 87, 108, 109, 153]
            for i in spike_indices:
                reg = np.zeros(len(confounds_df))
                if i < len(reg):
                    reg[i] = 1
                confounds_df[f'custom_spike_{i}'] = reg
                confound_columns.append(f'custom_spike_{i}')

        # Optionally include global signal regression
        if use_gsr and 'global_signal' in confounds_df.columns:
            confound_columns.append('global_signal')

    # Final confound matrix
    confounds = confounds_df[confound_columns].values

    print("Confound regressors included:")
    for name in confound_columns:
        print(f"  - {name}")

    print("Performing nuisance regression and filtering...")
    cleaned_img = clean_img(
        img,
        confounds=confounds,
        detrend=True,
        standardize=True,
        low_pass=low_pass,
        high_pass=high_pass,
        t_r=t_r
    )

    print(f"Saving cleaned NIfTI to: {output_path}")
    cleaned_img.to_filename(output_path)
    print("Done. The BOLD image has been denoised and saved.")

# Example usage:
denoise_voxelwise_nifti(
    nifti_path='/home/udit/Desktop/sub-29355/ses-01/func/sub-29355_ses-01_task-rest_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold.nii.gz',
    confounds_path='/home/udit/Desktop/sub-29355/ses-01/func/sub-29355_ses-01_task-rest_desc-confounds_timeseries.tsv',
    output_path='/home/udit/Desktop/sub-29355_ses-01_task-rest_space-MNI152NLin2009cAsym_res-2_desc-preproc_bold_denoised.nii.gz',
    t_r=2.5,
    use_gsr=True
)


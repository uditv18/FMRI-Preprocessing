import argparse
import sys
import json
import os
import pandas as pd
import numpy as np
import nibabel as nib
from nilearn.image import clean_img

class FMRIDenoiser:
    """
    A class to denoise a 4D fMRI NIfTI file using confounds from fMRIPrep.
    """
    def __init__(self, nifti_path, confounds_path, output_path,
                 confound_columns=None, low_pass=0.1, high_pass=0.01,
                 t_r=None, use_gsr=False):
        """Initializes the FMRIDenoiser instance."""
        # Normalize confound_columns to a list if provided as a comma-separated string
        if isinstance(confound_columns, str):
            confound_columns = [c.strip() for c in confound_columns.split(',') if c.strip()]

        self.nifti_path = nifti_path
        self.confounds_path = confounds_path
        self.output_path = output_path
        self.confound_columns = confound_columns
        self.low_pass = low_pass
        self.high_pass = high_pass
        self.t_r = t_r # TR can now be None initially
        self.use_gsr = use_gsr

    def _get_tr_from_nifti(self, img_obj):
        """
        Extracts the Repetition Time (TR) from the NIfTI file header.
        """
        try:
            # The TR is the 4th element of the pixdim array in the header
            tr = img_obj.header['pixdim'][4]
            if tr > 0:
                print(f"TR not provided. Extracted TR = {tr:.4f}s from NIfTI header.")
                return float(tr)
            else:
                raise ValueError
        except (ValueError, IndexError):
            print("\nError: Could not extract a valid TR from the NIfTI header.")
            print("The TR value in the header is missing, zero, or invalid.")
            print("Please specify the TR manually using the --t_r <value> flag.")
            sys.exit(1) # Exit the script with an error status

    def _prepare_confounds(self):
        """Loads and prepares the confound matrix for regression."""
        print("Loading and preparing confounds...")
        confounds_df = pd.read_csv(self.confounds_path, sep='\t').fillna(0)

        if self.confound_columns is None:
            default_cols = [
                'trans_x', 'trans_y', 'trans_z',
                'rot_x', 'rot_y', 'rot_z',
                'white_matter', 'csf'
            ]
            self.confound_columns = [col for col in default_cols if col in confounds_df.columns]
            spike_cols = [col for col in confounds_df.columns if 'motion_outlier' in col]
            if spike_cols:
                print(f"Found {len(spike_cols)} motion outlier regressors from fMRIPrep.")
                self.confound_columns.extend(spike_cols)
            else:
                print("No 'motion_outlier' columns found.")
            if self.use_gsr and 'global_signal' in confounds_df.columns:
                print("Including Global Signal Regression (GSR).")
                self.confound_columns.append('global_signal')

        final_columns = [col for col in self.confound_columns if col in confounds_df.columns]
        print("\nFinal list of confound regressors to be used:")
        for name in final_columns:
            print(f"  - {name}")
            
        return confounds_df[final_columns].values

    def _write_json_sidecar(self):
        """Writes a JSON sidecar file describing denoising steps."""
        json_path = os.path.splitext(self.output_path)[0] + ".json"
        metadata = {
            "Denoised": {
                "ConfoundsFile": os.path.basename(self.confounds_path),
                "RepetitionTime(TR)": self.t_r,
                "ConfoundColumns": self.confound_columns,
                "LowPassHz": self.low_pass,
                "HighPassHz": self.high_pass,
                "GlobalSignalRegression": self.use_gsr
            }
        }
        with open(json_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        print(f"Saved JSON: {json_path}")


    def run(self):
        """Executes the full denoising pipeline."""
        print("--- Starting Denoising Process ---")
        print(f"Input NIfTI: {self.nifti_path}")
        
        print("\nLoading fMRI image...")
        img = nib.load(self.nifti_path)
        
        # New Step: Automatically determine TR if not provided
        if self.t_r is None:
            self.t_r = self._get_tr_from_nifti(img)
        else:
            print(f"Using user-provided TR = {self.t_r}s.")

        confounds_matrix = self._prepare_confounds()
        
        print("\nPerforming nuisance regression and filtering...")
        cleaned_img = clean_img(
            img,
            confounds=confounds_matrix,
            detrend=True,
            standardize=True,
            low_pass=self.low_pass,
            high_pass=self.high_pass,
            t_r=self.t_r
        )
        
        print(f"\nSaving cleaned NIfTI to: {self.output_path}")
        cleaned_img.to_filename(self.output_path)
        print("--- Denoising Complete ---")

def main():
    """Main function to parse command-line arguments and run the denoising."""
    parser = argparse.ArgumentParser(description="Denoise a 4D fMRI NIfTI file.")
    
    parser.add_argument("nifti_path", type=str, help="Path to the preprocessed BOLD NIfTI file.")
    parser.add_argument("confounds_path", type=str, help="Path to the fMRIPrep confounds .tsv file.")
    parser.add_argument("output_path", type=str, help="Path to save the cleaned NIfTI file.")
    
    parser.add_argument("--t_r", type=float, default=None, help="Repetition time (TR) in seconds. If not provided, it will be extracted from the NIfTI header.")
    parser.add_argument("--low_pass", type=float, default=0.1, help="Low-pass filter cutoff in Hz (default: 0.1).")
    parser.add_argument("--high_pass", type=float, default=0.01, help="High-pass filter cutoff in Hz (default: 0.01).")

    # NEW: explicit confound columns (comma-separated)
    parser.add_argument("--confound_columns", type=str, default=None,
                        help="Comma-separated list of confound column names to use; overrides defaults.")

    # Keep original behavior (GSR of by default) and allow explicit enable/disable
    parser.add_argument("--gsr", action="store_true", dest="use_gsr",
                        help="Enable Global Signal Regression (GSR). off by default.")
    parser.add_argument("--no_gsr", action="store_false", dest="use_gsr",
                        help="Disable Global Signal Regression (GSR).")

    args = parser.parse_args()

    denoiser = FMRIDenoiser(
        nifti_path=args.nifti_path,
        confounds_path=args.confounds_path,
        output_path=args.output_path,
        confound_columns=args.confound_columns,
        t_r=args.t_r,
        low_pass=args.low_pass,
        high_pass=args.high_pass,
        use_gsr=args.use_gsr
    )
    denoiser.run()

if __name__ == "__main__":
    main()
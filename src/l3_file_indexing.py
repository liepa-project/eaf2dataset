import pandas as pd
import os
import shutil
from typing import List, Dict, Optional
import argparse

import re
import sys

def get_wav_path(filename_original:str, root_search_dir:str, fallback_root_search_dir:str) -> str|None:
    """
    Finds the full path of a .wav file based on its basename and search directories.
    It checks if the filename starts with two alphanumeric characters and an underscore (e.g., "aa_").
    If it matches, the prefix is removed, and the search starts in `input_root_dir`.
    Otherwise, it searches in `fallback_input_root_dir`.

    Args:
        filename_original (str): The original basename of the .wav file (e.g., "AB_test.wav" or "regular_file.wav").
        input_root_dir (str): The primary directory to search for WAV files.
        fallback_input_root_dir (str): The fallback directory to search if not found in primary or if prefix not matched.

    Returns:
        str: The full path of the found .wav file, or None if not found.
    """
    filename_to_search = filename_original
    search_dir = ""
    full_path = None

    # Check if the filename starts with two alphanumeric characters and an underscore
    if re.match(r'^[a-zA-Z0-9]{2}_', filename_original):
        # Remove the prefix (e.g., "aa_")
        filename_to_search = re.sub(r'^[a-zA-Z0-9]{2}_', '', filename_original)
        filename_to_search = re.sub(r'\s\(\d+\).wav$', '.wav', filename_to_search)
        search_dir = root_search_dir
    else:
        search_dir = fallback_root_search_dir

    # Perform a recursive search for the file within the determined search_dir
    for root, _, files in os.walk(search_dir, followlinks=True):
        if filename_to_search in files:
            full_path = os.path.join(root, filename_to_search)
            break # Found the file, stop searching

    return full_path


def line_fixer(x):
    print(x)
    return None



def find_real_paths_from_csv(
    tsv_file_path: str,
    root_search_dir: str,
    fallback_root_search_dir:str,
    output_csv_path: str
) -> None:
    """
    Reads a CSV file, extracts unique file paths from the first column,
    then finds the real full path for each file's basename within a
    specified root directory, handling soft links.
    The results are saved to an output CSV file.

    Args:
        csv_file_path (str): The path to the input CSV file. The first
                             column is expected to contain file paths.
        root_search_dir (str): The root directory where the files will be
                               searched for.
        output_csv_path (str): The path where the results will be saved as a
                               CSV file. The first column will be the original
                               unique path, and the second will be the real path.
    """
    if not os.path.exists(tsv_file_path):
        print(f"Error: TSV file not found at '{tsv_file_path}'")
        return

    if not os.path.isdir(root_search_dir):
        print(f"Error: Root search directory not found at '{root_search_dir}'")
        return

    # 1. Read the TSV file and extract the first column
    try:
        # Assuming no header in the input TSV
        df = pd.read_csv(tsv_file_path, header=0, delimiter="\t", 
                         encoding='utf-8',
                         engine='python',
                         on_bad_lines=line_fixer
                         )#  names=["input_wav_path", "output_mp3_path", "start_segment", "end_segment", "duration_segment", "text_len", "annotation"],
        print(df)

        # Ensure the first column exists
        if df.empty or df.shape[1] == 0:
            print("Error: CSV file is empty or has no columns.")
            return
        file_paths_from_csv = df.iloc[:, 0].astype(str).tolist()
    except Exception as e:
        print(f"Error reading input CSV file '{tsv_file_path}': {e}")
        return

    # 2. Get unique values from the first column
    unique_paths = list(set(file_paths_from_csv))
    print(f"Found {len(unique_paths)} unique paths in the input CSV.")

    # Dictionary to store results: original_csv_path -> found_real_path
    found_paths_map: Dict[str, Optional[str]] = {path: None for path in unique_paths}

    # 3. For each unique path from CSV, extract basename and search in root dir
    for original_path in unique_paths:
        # Extract file basename (e.g., "syslog" from "/var/log/syslog")
        basename = os.path.basename(original_path)
        real_path=get_wav_path(basename,root_search_dir, fallback_root_search_dir)
        if real_path!=None: 
            real_path=os.path.realpath(real_path)
        
        

        # Search for the basename in our pre-collected map
        if real_path != None:
            found_paths_map[original_path] = real_path
            # print(f"{original_path}->{real_path}")
        else:
            found_paths_map[original_path] = "-"
            print(f"Warning:  '{original_path}' not found'")

    # 4. Store the results to an output CSV file
    try:
        # Convert the dictionary to a pandas DataFrame
        output_df = pd.DataFrame(found_paths_map.items(), columns=['OriginalPath', 'RealPath'])
        output_df.to_csv(output_csv_path, index=False, header=True)
        print(f"Results successfully saved to '{output_csv_path}'")
    except Exception as e:
        print(f"Error saving results to output CSV '{output_csv_path}': {e}")


def main():
    """
    Main function to parse arguments, read the TSV, process each audio segment,
    and convert it to MP3.
    """

    parser = argparse.ArgumentParser(
        description="This script processes a TSV file for speech training, "
                    "extracting specified audio segments from WAV files and converting them to MP3 format.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Define command-line arguments, mirroring the shell script's expected arguments

    parser.add_argument("tsv_file", help="Path to the TSV file.\n"
                                          "Each line in the TSV should have the following tab-separated columns:\n"
                                          "  1. input_wav_path    (Path to the source WAV file)\n"
                                          "  2. output_mp3_path   (Path where the extracted MP3 segment will be saved)\n"
                                          "  3. start_segment     (Start time of the segment in seconds or HH:MM:SS.ms)\n"
                                          "  4. end_segment       (End time of the segment in seconds or HH:MM:SS.ms)\n"
                                          "  5. duration_segment  (Duration of the segment - currently not used by script but good for record)\n"
                                          "  6. text_len          (Text length)\n"
                                          "  7. annotation        (Any annotation - currently not used by script but good for record)\n\n"
                                          "Example TSV line: /path/to/input.wav /path/to/output.mp3 10.5 15.2 4.7 Some annotation")
    parser.add_argument("root_search_dir", help="Root directory for input WAV files.")
    parser.add_argument("fallback_root_search_dir", help="Fallback root directory for input WAV files if not found in primary.")
    parser.add_argument("output_file", help="Output file")

    args = parser.parse_args()

    # Assign arguments to variables
    # args.wav_type is captured but not used, matching the original shell script's behavior
    tsv_file = args.tsv_file
    root_search_dir = args.root_search_dir
    fallback_root_search_dir = args.fallback_root_search_dir
    output_file = args.output_file

    # Check if the TSV file exists
    if not os.path.isfile(tsv_file):
        print(f"Error: TSV file '{tsv_file}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing TSV file: {tsv_file}")
    print("----------------------------------------------------")
    find_real_paths_from_csv(tsv_file, root_search_dir, fallback_root_search_dir, output_file)


if __name__ == "__main__":
    main()

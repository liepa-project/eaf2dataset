#!/usr/bin/env python3

import argparse
import os
import shutil
import csv
import re
import subprocess
import datetime
import sys

# --- Helper Functions ---

def check_ffmpeg():
    """
    Checks if ffmpeg is installed and accessible in the system's PATH.
    If not, it prints an error message and exits the script.
    """
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg is not installed.", file=sys.stderr)
        print("Please install ffmpeg to use this script. On Debian/Ubuntu, you can use: sudo apt-get install ffmpeg", file=sys.stderr)
        print("On macOS with Homebrew: brew install ffmpeg", file=sys.stderr)
        sys.exit(1)

def log_to_file_and_stderr(message, filename="error.log"):
    """
    Logs a message with an ISO-formatted timestamp to a specified file
    and also prints it to stderr.

    Args:
        message (str): The log message.
        filename (str): The name of the log file to append to.
    """
    timestamp = datetime.datetime.now().isoformat(timespec='seconds') # YYYY-MM-DDTHH:MM:SS format
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp}  {message}\n")
    print(f"{timestamp}  {message}", file=sys.stderr)

def get_wav_path(filename_original, input_root_dir, fallback_input_root_dir):
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
        search_dir = input_root_dir
    else:
        search_dir = fallback_input_root_dir

    # Perform a recursive search for the file within the determined search_dir
    for root, _, files in os.walk(search_dir, followlinks=True):
        if filename_to_search in files:
            full_path = os.path.join(root, filename_to_search)
            break # Found the file, stop searching

    if full_path is None:
        log_to_file_and_stderr(
            f"Error: File '{filename_to_search}' (original '{filename_original}') not found in '{search_dir}'.",
            "file_error.log"
        )
        raise Exception("File not found")
    return full_path

# --- Main Script ---
def main():
    """
    Main function to parse arguments, read the TSV, process each audio segment,
    and convert it to MP3.
    """
    check_ffmpeg() # Ensure ffmpeg is installed

    parser = argparse.ArgumentParser(
        description="This script processes a TSV file for speech training, "
                    "extracting specified audio segments from WAV files and converting them to MP3 format.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Define command-line arguments, mirroring the shell script's expected arguments
    parser.add_argument("wav_type", help="Type of WAV file (e.g., 'test', 'train'). Currently not used by the script.")
    parser.add_argument("tsv_file", help="Path to the TSV file.\n"
                                          "Each line in the TSV should have the following tab-separated columns:\n"
                                          "  1. input_wav_path    (Path to the source WAV file)\n"
                                          "  2. output_mp3_path   (Path where the extracted MP3 segment will be saved)\n"
                                          "  3. start_segment     (Start time of the segment in seconds or HH:MM:SS.ms)\n"
                                          "  4. end_segment       (End time of the segment in seconds or HH:MM:SS.ms)\n"
                                          "  5. duration_segment  (Duration of the segment - currently not used by script but good for record)\n"
                                          "  6. annotation        (Any annotation - currently not used by script but good for record)\n\n"
                                          "Example TSV line: /path/to/input.wav /path/to/output.mp3 10.5 15.2 4.7 Some annotation")
    parser.add_argument("input_root_dir", help="Root directory for input WAV files.")
    parser.add_argument("output_root_dir", help="Root directory for output MP3 files.")
    parser.add_argument("fallback_input_root_dir", help="Fallback root directory for input WAV files if not found in primary.")

    args = parser.parse_args()

    # Assign arguments to variables
    # args.wav_type is captured but not used, matching the original shell script's behavior
    tsv_file = args.tsv_file
    input_root_dir = args.input_root_dir
    output_root_dir = args.output_root_dir
    fallback_input_root_dir = args.fallback_input_root_dir

    # Check if the TSV file exists
    if not os.path.isfile(tsv_file):
        print(f"Error: TSV file '{tsv_file}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing TSV file: {tsv_file}")
    print("----------------------------------------------------")

    processed_count = 0
    failed_count = 0

    # Log start attempts to respective log files
    log_to_file_and_stderr("--- start new attempt", "format_error.log")
    log_to_file_and_stderr("--- start new attempt", "file_error.log")

    # Open and read the TSV file line by line
    with open(tsv_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        for i, row in enumerate(reader):
            # Skip lines that don't have enough critical columns (at least 4: input, output, start, end)
            if len(row) < 4:
                log_to_file_and_stderr(f"Skipping malformed line {i+1}: '{' '.join(row)}'",
                                       "format_error.log")
                continue

            input_wav_orig, output_mp3_orig, start_segment_str, end_segment_str = row[:4]
            # Optional fields (duration and annotation) are not actively used in the processing logic
            # duration = row[4] if len(row) > 4 else ""
            # annotation = row[5] if len(row) > 5 else ""

            # Check if critical fields are empty
            if not all([input_wav_orig, output_mp3_orig, start_segment_str, end_segment_str]):
                log_to_file_and_stderr(f"Skipping malformed line {i+1} (missing critical data): '{' '.join(row)}'",
                                       "format_error.log")
                continue

            # Process input and output paths
            basename_wav_name = os.path.basename(input_wav_orig)
            input_file = get_wav_path(basename_wav_name, input_root_dir, fallback_input_root_dir)

            output_mp3_cleaned = output_mp3_orig.replace(' ', '_') # Replace spaces in output filename
            output_file = os.path.join(output_root_dir, output_mp3_cleaned)

            # Convert start and end times, replicating the shell script's awk logic
            # If the segment string contains ':', treat it as HH:MM:SS.ms.
            # Otherwise, assume it's a numeric value in milliseconds and convert to seconds.
            try:
                start_sec = start_segment_str if ':' in start_segment_str else str(float(start_segment_str) / 1000)
                end_sec = end_segment_str if ':' in end_segment_str else str(float(end_segment_str) / 1000)
            except ValueError:
                log_to_file_and_stderr(f"Skipping line {i+1}: Invalid start or end segment time format. "
                                       f"Start: '{start_segment_str}', End: '{end_segment_str}'",
                                       "format_error.log")
                failed_count += 1
                continue

            print("Processing:")
            print(f"  input_wav :   {input_wav_orig}")
            print(f"  Basename WAV: {basename_wav_name}")
            print(f"  Input PATH:   {input_file}")
            print(f"  Output MP3:   {output_file}")
            print(f"  Start:        {start_sec}")
            print(f"  End:          {end_sec}")

            # Create the output directory if it doesn't exist
            output_dir = os.path.dirname(output_file)
            if not os.path.exists(output_dir):
                print(f"  Creating output directory: {output_dir}")
                try:
                    os.makedirs(output_dir)
                except OSError as e:
                    print(f"Error: Failed to create directory '{output_dir}'. Skipping this segment. Error: {e}", file=sys.stderr)
                    failed_count += 1
                    continue

            # Check if the input WAV file was found and exists
            if input_file is None or not os.path.isfile(input_file):
                print(f"Error: Input WAV file '{input_file}' not found or path resolution failed. Skipping this segment.", file=sys.stderr)
                failed_count += 1
                continue

            # Construct the ffmpeg command
            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-ss", start_sec,
                "-to", end_sec,
                "-c:a", "libmp3lame",
                "-q:a", "2",
                "-y", output_file
            ]

            # Execute the ffmpeg command
            try:
                # `subprocess.run` with `check=True` raises `CalledProcessError` for non-zero exit codes.
                # `capture_output=True` redirects stdout/stderr, mimicking `&> /dev/null`.
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"  Successfully extracted and converted to: {output_file}")
                processed_count += 1
            except subprocess.CalledProcessError as e:
                print(f"  Error: Failed to process segment from '{input_file}' to '{output_file}'. "
                      f"FFmpeg stderr: {e.stderr.strip()}", file=sys.stderr)
                failed_count += 1
            except FileNotFoundError:
                # This specific error means the 'ffmpeg' executable itself wasn't found
                print(f"Error: ffmpeg command not found. Please ensure ffmpeg is installed and in your PATH.", file=sys.stderr)
                sys.exit(1) # Exit immediately as ffmpeg is a critical dependency
            print("----------------------------------------------------")

    print("\nScript finished.")
    print(f"Total segments processed successfully: {processed_count}")
    print(f"Total segments failed: {failed_count}")

if __name__ == "__main__":
    main()

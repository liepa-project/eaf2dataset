#!/bin/bash

set -e

# This script reads a TSV file, extracts specified audio segments from WAV files,
# and converts them to MP3 format.

# --- Configuration ---
# Path to the TSV file provided as the first argument.

# --- Functions ---

# Function to display script usage
usage() {
    echo "Usage: $0 <tsv_file>"
    echo "This script processes a TSV file for speech training."
    echo "Each line in the TSV should have the following tab-separated columns:"
    echo "  1. input_wav_path    (Path to the source WAV file)"
    echo "  2. output_mp3_path   (Path where the extracted MP3 segment will be saved)"
    echo "  3. start_segment     (Start time of the segment in seconds or HH:MM:SS.ms)"
    echo "  4. end_segment       (End time of the segment in seconds or HH:MM:SS.ms)"
    echo "  5. duration_segment  (Duration of the segment - currently not used by script but good for record)"
    echo "  6. annotation        (Any annotation - currently not used by script but good for record)"
    echo ""
    echo "Example TSV line: /path/to/input.wav /path/to/output.mp3 10.5 15.2 4.7 Some annotation"
    exit 1
}

# Function to check if ffmpeg is installed
check_ffmpeg() {
    if ! command -v ffmpeg &> /dev/null; then
        echo "Error: ffmpeg is not installed."
        echo "Please install ffmpeg to use this script. On Debian/Ubuntu, you can use: sudo apt-get install ffmpeg"
        echo "On macOS with Homebrew: brew install ffmpeg"
        exit 1
    fi
}

# --- Main Script ---

# Check if ffmpeg is available
check_ffmpeg

# Check if a TSV file is provided as an argument
if [ -z "$1" ]; then
    usage
fi

wav_type="$1"
tsv_file="$2"

#wav_type=test
# wav_type=train

input_root_dir="$3"
output_root_dir="$4"
fallback_input_root_dir="$5"

# Check if the TSV file exists
if [ ! -f "$tsv_file" ]; then
    echo "Error: TSV file '$tsv_file' not found."
    exit 1
fi

echo "Processing TSV file: $tsv_file"
echo "----------------------------------------------------"

# Initialize a counter for processed segments
processed_count=0
# Initialize a counter for failed segments
failed_count=0


# Function to find the full path of a .wav file
# It searches in /data/corpus/records if the filename starts with two word characters and an underscore (e.g., "aa_").
# Otherwise, it searches in /var/www/html/records/.
#
# Usage:
# get_wav_path "filename.wav"
#
# Arguments:
#   $1: The base name of the .wav file (e.g., "AB_test.wav" or "regular_file.wav")
#
# Returns:
#   The full path of the found .wav file, or an empty string if not found.
function get_wav_path() {
  local filename="$1"
  local wav_dir="$2"
  local fallback_wav_dir="$3"

  local search_dir=""
  local full_path=""

  # Check if the filename starts with two word characters and an underscore using regex
  # [[ "$filename" =~ ^[[:alnum:]]{2}_ ]] is a more robust way to check for word characters
  if [[ "$filename" =~ ^[a-zA-Z0-9]{2}_ ]]; then
    filename=$(echo $filename|sed -e "s/^\w\w_//")
    search_dir=$wav_dir
  else
    search_dir=$fallback_wav_dir
  fi

  # Use find to locate the file.
  # -name "$filename" ensures we're looking for the exact filename provided.
  # -print -quit makes find exit after the first match, improving efficiency.
  # 2>/dev/null suppresses any error messages from find (e.g., if directories don't exist).
  full_path=$(find -L "$search_dir" -type f -name "$filename" -print -quit 2>/dev/null)

  # If the file was not found, print an error message to stderr
  if [[ -z "$full_path" ]]; then
    echo "$(date --iso-8601=s)  Error: File '$filename' not found in '$search_dir'." |tee -a file_error.log
  fi

  # Return the found path
  echo "$full_path"
}

echo "$(date --iso-8601=s) --- start new attempt "|tee  format_error.log
echo "$(date --iso-8601=s)  --- start new attempt" |tee  file_error.log

# Read the TSV file line by line
# IFS=$'\t' sets the Internal Field Separator to a tab character.
# -r prevents backslash escapes from being interpreted.
while IFS=$'\t' read -r input_wav output_mp3 start_segment end_segment duration annotation ; do
    # Skip empty lines or lines that don't have enough columns
    if [ -z "$input_wav" ] || [ -z "$output_mp3" ] || [ -z "$start_segment" ] || [ -z "$end_segment" ]; then
        echo "$(date --iso-8601=s) Skipping malformed line: '$input_wav	$output_mp3	$start_segment	$end_segment	$duration	$annotation'"|tee -a format_error.log
        continue
    fi

    # remove file prefix like XX_
    basename_wav_name=$(basename "$input_wav") 
    #input_file=$input_root_dir/$input_wav
    input_file=$(get_wav_path "$basename_wav_name" "$input_root_dir" "$fallback_input_root_dir")
    output_mp3=${output_mp3// /_}
    output_file="$output_root_dir/$output_mp3"
    start_sec=$(awk "BEGIN {x=$start_segment;y=1000;print x/y}")
    end_sec=$(awk "BEGIN {x=$end_segment;y=1000;print x/y}")

    echo "Processing:"
    echo "  Input WAV:    $input_file"
    echo "  Output MP3:   $output_file"
    echo "  Start:        $start_sec"
    echo "  End:          $end_sec"

    # Create the output directory if it doesn't exist
    output_dir=$(dirname "$output_file")
    if [ ! -d "$output_dir" ]; then
        echo "  Creating output directory: $output_dir"
        mkdir -p "$output_dir"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create directory '$output_dir'. Skipping this segment."
            failed_count=$((failed_count + 1))
            continue
        fi
    fi

    # Check if input WAV file exists
    if [ ! -f "$input_file" ]; then
        echo "Error: Input WAV file '$input_file' not found. Skipping this segment."
        failed_count=$((failed_count + 1))
        exit
        continue
    fi

    # Use ffmpeg to cut the segment and convert it to MP3
    # -i: input file
    # -ss: start time
    # -to: end time (exclusive, meaning it stops *at* this timestamp)
    # -c:a libmp3lame: use libmp3lame codec for MP3 encoding
    # -q:a 2: variable bitrate quality (0=best, 9=worst for libmp3lame)
    # -y: overwrite output files without asking
    ffmpeg -i "$input_file" -ss "$start_sec" -to "$end_sec" -c:a libmp3lame -q:a 2 -y "$output_file"  &> /dev/null

    if [ $? -eq 0 ]; then
        echo "  Successfully extracted and converted to: $output_file"
        processed_count=$((processed_count + 1))
    else
        echo "  Error: Failed to process segment from '$input_file' to '$output_file'."
        failed_count=$((failed_count + 1))
    fi
    echo "----------------------------------------------------"
    

done < "$tsv_file"

echo ""
echo "Script finished."
echo "Total segments processed successfully: $processed_count"
echo "Total segments failed: $failed_count"

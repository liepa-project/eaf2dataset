from typing import Optional
import pandas as pd
from pydub import AudioSegment
import os
import argparse
import sys

import logging
logger = logging.getLogger("INFO")
logging.basicConfig(
    level=os.environ.get('PARSE_EAF_LOGLEVEL', 'INFO').upper()
)


def find_real_path(a_file_path: str, file_index_df) -> Optional[str]:
    """
    Reads a CSV file with 'file_path' and 'real_path' columns,
    and returns the 'real_path' corresponding to a given 'file_path'.

    Args:
        a_file_path (str): The file path to search for.
        csv_path_file_index (str): The path to the CSV file.

    Returns:
        Optional[str]: The corresponding 'real_path' if found, otherwise None.
    """
    try:
        df=file_index_df
        result = df[df['OriginalPath'] == a_file_path]['RealPath']
        if not result.empty:
            return result.iloc[0]
        else:
            return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # return None
        raise e
    
def log_metadata(output_mp3, annotation:str, duration:str, txt_len:str, filename="metadata.csv"):
    """
    Logs a message with an ISO-formatted timestamp to a specified file
    and also prints it to stderr.

    Args:
        message (str): The log message.
        filename (str): The name of the log file to append to.
    """
    
    clean_annotation=annotation.replace(',', '').replace('"', '').replace('|', '')

    with open(filename, 'a', encoding='utf-8') as f:
        f.write(f"./mp3/{output_mp3},{clean_annotation},{duration},{txt_len}\n")

def split_audio_from_tsv(tsv_file_path: str, file_index_path, output_root_dir: str):
    """
    Splits audio files into multiple MP3s based on a TSV file,
    grouping processing by input file path to minimize I/O.
    """
    if not os.path.exists(tsv_file_path):
        print(f"Error: The TSV file '{tsv_file_path}' was not found.")
        sys.exit(1)

    try:
        file_index_df= pd.read_csv(file_index_path, header=0)
        # Read the TSV file into a pandas DataFrame
        df = pd.read_csv(tsv_file_path, sep='\t')
        
        
        # Validate required columns
        # required_cols = ['input_wav_path', 'output_mp3_path', 'start_segment_ms', 'end_segment_ms']
        required_cols = ["input_wav_path", "output_mp3_path", "start_segment", "end_segment", "duration_segment", "text_len", "annotation"]
        if not all(col in df.columns for col in required_cols):
            print(f"Error: The TSV file must contain the following columns: {required_cols}")
            sys.exit(1)

    except Exception as e:
        print(f"An error occurred while reading the TSV file: {e}")
        sys.exit(1)

    # Group the DataFrame by the input audio file path
    grouped_df = df.groupby('input_wav_path')
    
    print(f"Processing {len(grouped_df)} unique audio files...")
    
    for input_wav_orig, group in grouped_df:
        
        # Check if all output files for this group already exist
        all_output_exist = True
        for index, row in group.iterrows():
            output_relative_path = row['output_mp3_path'].replace('./', '')
            output_full_path = os.path.join(output_root_dir, output_relative_path)
            if not os.path.exists(output_full_path):
                all_output_exist = False
                break
        
        if all_output_exist:
            print(f"✅ All output files for '{input_wav_orig}' already exist. Skipping this group.")
            continue
        try:
            input_file = find_real_path(str(input_wav_orig), file_index_df)
            print(f"\n>Input_file : {input_wav_orig}")
            audio = AudioSegment.from_file(input_file)
            audio = audio.set_frame_rate(16000)
            print(f"  found_path :   {input_file}")

            
            # Process each segment for this specific audio file
            for index, row in group.iterrows():
                # Construct the full output path
                # output_mp3_path in TSV is relative to its input_wav_path
                # We need to prepend the output_root_dir
                # output_relative_path = row['output_mp3_path'].replace('./', '')
                # output_full_path = os.path.join(output_root_dir, output_relative_path)
                output_mp3_orig= row['output_mp3_path']

                output_mp3_cleaned = output_mp3_orig.replace(' ', '_') # Replace spaces in output filename
                output_file = os.path.join(output_root_dir, output_mp3_cleaned)

                if os.path.isfile(output_file):
                    logging.debug(f"Warning: Output file '{output_file}' exists already. Skipping this segment.", "file_exists.log")
                    continue

                annotation=row['annotation']
                duration_segment=row['duration_segment']
                text_len=row['text_len']
                start_ms = row['start_segment']
                end_ms = row['end_segment']
                # print(f"  Output MP3:   {output_file} ")

                # Slice the audio segment
                chunk = audio[start_ms:end_ms]
                
                # Create the output directory if it doesn't exist
                output_dir = os.path.dirname(output_file)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                # Export the chunk as an MP3 file
                chunk.export(output_file, format="mp3")
                            #  prameters=["-acodec", "pcm_s16le", "-ar", "16000", "-c:a", "libmp3lame", "-q:a", "2"])
                log_metadata(output_mp3_cleaned, annotation, duration_segment, text_len, filename=os.path.join(output_root_dir, "..", "metadata.csv"))
                print(f"\tExported:\t{output_file} [{start_ms},{end_ms}]")

        except FileNotFoundError as fe:
            print(f"Error: Input file '{input_file}' not found. Skipping this group.")
            # continue
            raise fe
        except Exception as e:
            print(f"An error occurred while processing '{input_file}': {e}. Skipping this group.")
            # continue
            raise e

    print("\nAll audio processing tasks complete.")

def main():
    """
    Main function to parse command-line arguments and run the audio splitting.
    """
    parser = argparse.ArgumentParser(description="Split audio files based on a TSV file.")
    parser.add_argument("wav_type", help="Type of WAV file (e.g., 'test', 'train'). Currently not used by the script.")
    parser.add_argument("tsv_file_path", type=str, 
                        help="Path to the TSV file containing audio segment information.")
    parser.add_argument("file_index_path", help="Root directory for input WAV files.")
    parser.add_argument("output_root_dir", type=str, 
                        help="The root directory where the output MP3 files will be saved.")
    
    args = parser.parse_args()
    
    split_audio_from_tsv(args.tsv_file_path, args.file_index_path, args.output_root_dir)

if __name__ == "__main__":
    main()
import os
import argparse
import parse_eaf

import logging
logger = logging.getLogger("INFO")
logging.basicConfig(
    level=os.environ.get('PARSE_EAF_LOGLEVEL', 'INFO').upper()
)


def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

def find_eaf_files(path):
    """
    Finds all files with a .eaf extension in the given directory and its subdirectories.

    Args:
        path (str): The starting directory to search from.

    Returns:
        list: A list of full paths to all found .eaf files.
    """
    eaf_files = []
    # os.walk generates the file names in a directory tree
    for root, dirs, files in os.walk(path):
        for file in files:
            # Check if the file name ends with .eaf
            if file.endswith('.eaf'):
                # Construct the full path and add it to the list
                eaf_files.append(os.path.join(root, file))
    return eaf_files



def filter_eaf_files_by_subdir(eaf_files, exclude_file_path):
    """
    Filters a list of .eaf file paths, excluding any files located in subdirectories
    whose names are listed in the exclusion file.

    Args:
        eaf_files (list): A list of full file paths to .eaf files.
        exclude_file_path (str): The path to a text file containing subdirectory
                                 names to exclude, one name per line.

    Returns:
        list: A new list of .eaf file paths that are not in the excluded subdirectories.
    """
    logger.info("exclude_file_path: %s", exclude_file_path)
    excluded_subdirs = set()
    try:
        with open(exclude_file_path, 'r') as f:
            # Read each line, strip whitespace, and add to the set
            for line in f:
                subdir_name = line.strip()
                if subdir_name:  # Ensure we don't add empty strings
                    excluded_subdirs.add(subdir_name)
    except FileNotFoundError:
        print(f"Error: Exclusion file not found at '{exclude_file_path}'")
        return eaf_files  # Return the original list if the exclusion file doesn't exist
    filtered_files = []
    for file_path in eaf_files:
        # Get the name of the subdirectory where the file is located
        subdir_name = os.path.basename(os.path.dirname(file_path))

        # Check if the subdirectory name is NOT in our set of excluded names
        if subdir_name not in excluded_subdirs:
            filtered_files.append(file_path)

    return filtered_files


def main():
    parser = argparse.ArgumentParser(description="Transcribe MP3 files in a directory and calculate WER.")
    parser.add_argument("-r", "--root_path", type=dir_path,
                        help="Path root dir that contains the eaf files.")
    parser.add_argument("-e", "--exclusion_file", type=argparse.FileType('r'),
                        help="Path file that contains list of excoluded dirs.")


    args = parser.parse_args()
    root_path = args.root_path
    exclusion_file = args.exclusion_file
    if not os.path.isdir(root_path):
        logger.error(f"Error: File not found at '{root_path}'. Please provide a valid file path.")
        return
    logger.debug("\n--- Starting wer calc in '%s' ---", root_path)

    all_eaf_files = find_eaf_files(root_path)
    filtered_eaf_files = filter_eaf_files_by_subdir(all_eaf_files, exclusion_file.name)
    for eaf_file in filtered_eaf_files:
        parse_eaf.process_eaf_file(eaf_file)
    # print(filtered_eaf_files)


if __name__ == "__main__":
    main()
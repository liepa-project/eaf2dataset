
import argparse
import datasets
import pathlib


datasets.logging.set_verbosity_info()

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%dT%H:%M:%S')

argparser = argparse.ArgumentParser(description='Generates dataset for Liepa project')
argparser.add_argument('-c', '--corpus_name', type=str, nargs='?',
                    required=True,
                    help='A corpus name is used for generate data set')
argparser.add_argument('-p', '--corpus_path', type=pathlib.Path, nargs='?',
                    required=True,
                    help='A corpus npath to upload')



def main(corpus_name:str, corpus_path:pathlib.Path):
    logger.info(f"[main]+++ {corpus_name}")
    dataset = datasets.load_dataset("audiofolder", data_dir=str(corpus_path))    
    dataset.push_to_hub(repo_id=corpus_name)
    



if __name__ == "__main__":
    args = argparser.parse_args()
    corpus_name=args.corpus_name
    corpus_path=args.corpus_path
    logger.info(f"[main]corpus name: {corpus_name}")
    logger.info(f"[main]corpus path {corpus_path}")
    main(corpus_name, corpus_path)


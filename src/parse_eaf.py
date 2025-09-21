import argparse
import os
from typing import List, Set, Optional
import typing
from pympi import Eaf
# from dataclasses import dataclass
import dataclasses
import json
import re

import logging
logger = logging.getLogger("DEBUG")
logging.basicConfig(
    level=os.environ.get('PARSE_EAF_LOGLEVEL', 'INFO').upper()
)

import liepa3_normalizer

normalizer = liepa3_normalizer.Liepa3TextNormalizer()

#"noise" - Liepa2
IgnoreTiers = ('overlap', 'noise', 'default', 'zodziai') 
ValidTierName  = re.compile(r"^S\d{4}|\d{1,2}frazes|Guest[-_]\d{1,2}$")


@dataclasses.dataclass
class TimeSlot:
    id: str
    time_value: int
    

@dataclasses.dataclass
class Annotation:
    id:str
    tier_id:str
    time_slot_start_id: str
    time_slot_start: int
    time_slot_end_id: str
    time_slot_end: int
    annotation_value: str

@dataclasses.dataclass
class Tier:
    id: str
    tier_id: str
    annotator: str
    participant: str
    # time_value: int
    annotations: List[Annotation]

    # def __post_init__(self):
    #     self.annotations = Annotation(**self.annotations)

@dataclasses.dataclass
class AnnotationDoc:
    media_url:str
    eaf_path:str
    tiers: List[Tier]
    time_slots: List[TimeSlot]


@dataclasses.dataclass
class LatEntry:
    time_slot_start: int
    time_slot_end: int



def map_annotations(key:str, detail, time_slots:List[TimeSlot], tier_id:str) -> Annotation:
    time_slot_start_id=detail[0]
    time_slot_start = [ts.time_value for ts in time_slots if ts.id == time_slot_start_id][0]
    time_slot_end_id=detail[1]
    time_slot_end = [ts.time_value for ts in time_slots if ts.id == time_slot_end_id][0]
    # logger.debug('[map_annotations] detail %s', detail)
    return Annotation(id=key,
                            tier_id=tier_id,
                            time_slot_start_id=time_slot_start_id,
                            time_slot_start=time_slot_start,
                            time_slot_end_id=time_slot_end_id,
                            time_slot_end=time_slot_end,
                            annotation_value=detail[2])#



def map_tier_detail(key:str, tier_details, time_slots:List[TimeSlot]) -> Optional[Tier]:
    annotations_dict=tier_details[0]
    tier_id=tier_details[2].get("TIER_ID","NONE")
    annotations=[map_annotations(k,v, time_slots, tier_id) for k,v in annotations_dict.items()]
    # print(annotations)
    # logger.debug('[map_tier_detail] annotation empty %s', tier_details[1])
    logger.debug('[map_tier_detail] ANNOTATOR %s', tier_details[2])
    # logger.debug('[map_tier_detail] annotation seq %s', tier_details[3])
    
    ### Liepa3
    if "ANNOTATOR" in tier_details[2]:
        # logging.error("tier_id: %s", tier_id)
        if tier_id in IgnoreTiers:
            logging.error("tier_id is ignored: %s", tier_id)
            return None
        if(not ValidTierName.match(tier_id)):
            logging.error("tier_id is not valid: %s", tier_id)
            return None
        return Tier(id=key,
                    annotator=tier_details[2]["ANNOTATOR"],
                    tier_id=tier_id,
                    participant=tier_details[2].get("PARTICIPANT","NONE"),
                    annotations=annotations)
    ### Liepa2(tier_id != "noise") 
    elif not tier_id in IgnoreTiers:
        return Tier(id=key,
                        annotator="-",
                        tier_id=tier_id,
                        participant=tier_details[2].get("PARTICIPANT","NONE"),
                        annotations=annotations)
    else:
        return None


def parse_eaf(eaf_path):
    eaf = Eaf(eaf_path)
    
    time_slots = [TimeSlot(id=k, time_value=v) for k, v in eaf.timeslots.items()]
    tiers_all = [map_tier_detail(k,v, time_slots) for k, v in eaf.tiers.items()]
    tiers = list(filter(lambda x: x is not None, tiers_all)) 
    # logger.debug("[parse_eaf] tiers: %s", tiers_all)
    tiers = typing.cast(List[Tier],tiers)
    
    # logger.debug("[parse_eaf] %s", eaf.properties[0])
    return AnnotationDoc(media_url=eaf.media_descriptors[0]["MEDIA_URL"],
                         eaf_path=eaf_path,
                                time_slots=time_slots,
                                tiers=tiers)




def group_transcription_segments(annotation_doc: AnnotationDoc, max_chunk_duration: int = 26000, max_gap_between_segments: int = 500, max_text_len=500) -> List[Annotation]:
    """
    Groups audio transcription annotation segments into larger chunks based on time constraints.

    Segments are combined into a chunk if:
    1. The time gap between the current segment's start and the previous segment's
       end in the chunk is not greater than 'max_gap_between_segments'.
    2. Adding the current segment does not make the chunk's total duration
       (from the chunk's start to the current segment's end) exceed 'max_chunk_duration'.

    If either condition is not met, the current chunk is finalized, and a new chunk
    is started with the current segment.

    Args:
        data: A dictionary containing the transcription tiers and annotations.
              Expected format:
              {
                "tiers": [
                  {
                    "annotations": [
                      {"id": "a1", "time_slot_start": 0, "time_slot_end": 5, "annotation_value": "segment1"},
                      {"id": "a2", "time_slot_start": 5, "time_slot_end": 10, "annotation_value": "segment2"},
                      ...
                    ]
                  }
                ]
              }
        max_chunk_duration: The maximum allowed duration for a single chunk in seconds.
                            Defaults to 30 seconds.
        max_gap_between_segments: The maximum allowed gap between two consecutive segments within
                                  a chunk before a new chunk is started, in seconds.
                                  Defaults to 3 seconds.

    Returns:
        A list of dictionaries, where each dictionary represents a grouped chunk.
        Each chunk dictionary contains the following keys:
        - 'start_time': The start time of the chunk (from the first segment in the chunk).
        - 'end_time': The end time of the chunk (from the last segment in the chunk).
        - 'text': The combined annotation values (transcribed text) of all segments in the chunk,
                  separated by spaces.
        Returns an empty list if no annotations are found in the input data.
    """
    grouped_chunks = []
    current_chunk:Optional[Annotation] = None
    current_chunk_tierids:set[str]|None=None

    # Safely retrieve annotations from the input data structure.
    # We assume annotations are in the first tier.
    all_annotations:List[Annotation] = []
    if annotation_doc and len(annotation_doc.tiers) > 0 :
        # all_annotations = annotation_doc.tiers[0].annotations
        for tiers in annotation_doc.tiers:
            all_annotations.extend(tiers.annotations)
    
        all_annotations.sort(key=lambda x: x.time_slot_start)
    else:
        # If no annotations are found, return an empty list
        print("Warning: No annotations found in the provided data structure.")
        return []

    for segment in all_annotations:
        # segment_id = segment.id
        # segment_start = segment.time_slot_start
        # segment_end = segment.time_slot_end
        # segment_text = segment.annotation_value

        if(segment.time_slot_end-segment.time_slot_start > 30000):
            # segment too long to use
            logging.error(f"[group_transcription_segments]Error : segment>30s\t{segment}")
            continue
        if(len(segment.annotation_value)==0):
            # logging.error(f"[group_transcription_segments]Error : zero len annotation\t{segment}")
            continue
        if(len(segment.annotation_value)>700):
        #    aStr = f"###{aStr}"
            logging.error(f"[group_transcription_segments]Error : text_len>700\t{segment}")
            continue
        if current_chunk is None:
            # If no chunk is currently being built, start a new one with the current segment.
            current_chunk_tierids={segment.tier_id}
            current_chunk = Annotation(id=segment.id,
                            tier_id=segment.tier_id,
                            time_slot_start_id=segment.time_slot_start_id,
                            time_slot_start=segment.time_slot_start,
                            time_slot_end_id=segment.time_slot_end_id,
                            time_slot_end=segment.time_slot_end,
                            annotation_value=segment.annotation_value)
        else:
            # Calculate the time gap between the current segment and the end of the current chunk.
            gap = segment.time_slot_start - current_chunk.time_slot_end
            # Calculate the potential total duration of the chunk if the current segment is added.
            potential_total_duration = segment.time_slot_end - current_chunk.time_slot_start

            potential_text_len = len(segment.annotation_value) + len(current_chunk.annotation_value)


            # Determine if a new chunk should be started.
            # This happens if:
            # 1. The gap between segments is too large, OR
            # 2. Adding the current segment would make the chunk's total duration
            #    exceed the maximum allowed duration.
            # 3. text length is too long
            if gap > max_gap_between_segments or potential_total_duration > max_chunk_duration or potential_text_len > max_text_len:
                # Finalize the current chunk and add it to the list of grouped chunks.
                logger.debug("_grouped_chunks_ gap %s, potential_total_duration %s", gap, potential_total_duration)
                if current_chunk_tierids!= None: current_chunk.tier_id="|".join(list(current_chunk_tierids))
                grouped_chunks.append(current_chunk)
                logger.debug("\n_grouped_chunks_ after %s", len(grouped_chunks))
                # Start a new chunk with the current segment.
                current_chunk_tierids=set([segment.tier_id])
                current_chunk = Annotation(id=segment.id,
                            tier_id=segment.tier_id,
                            time_slot_start_id=segment.time_slot_start_id,
                            time_slot_start=segment.time_slot_start,
                            time_slot_end_id=segment.time_slot_end_id,
                            time_slot_end=segment.time_slot_end,
                            annotation_value=segment.annotation_value
                            
                            )
            else:
                # If conditions allow, append the current segment's text to the current chunk's text
                # and update the chunk's end time.
                if current_chunk_tierids != None: current_chunk_tierids.add(segment.tier_id)
                current_chunk.annotation_value += " | " + segment.annotation_value
                current_chunk.time_slot_end = segment.time_slot_end

    # After iterating through all segments, ensure the last built chunk is added to the list.
    if current_chunk is not None:
        if current_chunk_tierids!= None: current_chunk.tier_id="|".join(list(current_chunk_tierids))
        grouped_chunks.append(current_chunk)

    return grouped_chunks


def format_annotations(eaf_doc:AnnotationDoc, group_annotations:List[Annotation]):
    media_file_name = os.path.basename(eaf_doc.eaf_path)
    media_file_name_wo_ext = os.path.splitext(media_file_name)[0]
    output_mp3_cleaned = media_file_name_wo_ext.replace(' ', '_')
    output_mp3_cleaned = output_mp3_cleaned.replace('(', '_')
    output_mp3_cleaned = output_mp3_cleaned.replace(')', '_')

    media_dir_name = os.path.basename(os.path.dirname(eaf_doc.eaf_path))
    os.path.dirname
    result:List[str] = []
    counter = 1
    for annotation in group_annotations:
        segment_length=annotation.time_slot_end - annotation.time_slot_start
        annotation_value = annotation.annotation_value.replace("\n", " ")
        annotation_value=normalizer(annotation_value)
        annotation_value_len = len(annotation_value) 
        tiers=annotation.tier_id
        #bash script loosing first symbols. I ll us currend dir hack
        aStr = f"./{media_dir_name}/{media_file_name_wo_ext}.wav\t{media_dir_name}/{output_mp3_cleaned}_chunk_{counter:03}.mp3\t{annotation.time_slot_start}\t{annotation.time_slot_end}\t{segment_length}\t{annotation_value_len}\t{tiers}\t{annotation_value}"
        ### workarounds
        if(segment_length > 30000):
            # segment too long to use
            logging.error(f"[format_annotations]Error : segment>30s\t{aStr}")
            continue
        if(annotation_value_len==0):
            # raise( Exception(f"Error : zero len annotation {aStr}"))
            logging.error(f"Error : zero len annotation\t{aStr}")
            continue
        if(annotation_value_len>700):
        #    aStr = f"###{aStr}"
            logging.error(f"[format_annotations]Error : text_len>700\t{aStr}")
            continue


        result.append(aStr)
        counter += 1
    return "\n".join(result)

    
def process_eaf_file(eaf_path):
    eaf_doc=parse_eaf(eaf_path)
    # print("eaf_doc", eaf_doc)
    # print("json", json.dumps(dataclasses.asdict(eaf_doc)))
    group_annotation = group_transcription_segments(eaf_doc)
    
    print(format_annotations(eaf_doc, group_annotation))




def main():
    parser = argparse.ArgumentParser(description="Transcribe MP3 files in a directory and calculate WER.")
    parser.add_argument("-e", "--eaf_path", type=str,
                        help="Path to the file containing transcribtion.")
    
    
    args = parser.parse_args()
    eaf_path = args.eaf_path


    if not os.path.isfile(eaf_path):
        logger.error(f"Error: File not found at '{eaf_path}'. Please provide a valid file path.")
        return
    logger.debug("\n--- Starting wer calc in '%s' ---", eaf_path)
    
    process_eaf_file(eaf_path)

    return

if __name__ == "__main__":
    main()

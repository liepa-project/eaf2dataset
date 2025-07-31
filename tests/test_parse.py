from typing import List
import unittest
import datetime

import sys
# sys.path.append('../src')
import src.parse_eaf as parse_eaf




class Test_file_util(unittest.TestCase):

    def test_parse_annotated(self):
        # given
        annotation_doc = self.create_annotations()
        # when
        # result=parse_eaf.group_annotations(annotation_doc)
        result=parse_eaf.group_transcription_segments(annotation_doc)
        
        # then
        self.assertEqual(len(result), 2, "Result length should be 2")
        # self.assertEqual("001-020", result.listnumm)
        # self.assertIsNotNone(result.record_path)



    def create_annotations(self) -> parse_eaf.AnnotationDoc:
        anotations =  [self.create_annotation(0,5,"vienas"),
            self.create_annotation(5,10,"du"),
            self.create_annotation(10,15,"trys"),
            self.create_annotation(20,30,"keturi")]
        
        tier = self.create_tier(anotations=anotations) 
        tiers:List[parse_eaf.Tier] = [tier]
        result = parse_eaf.AnnotationDoc(media_url="", eaf_path="", tiers=tiers,time_slots=[])
        return result
    
    def create_tier(self, anotations:List[parse_eaf.Annotation]) -> parse_eaf.Tier:
        return parse_eaf.Tier(id="key",
                        annotator="AA",
                        participant="PP",
                        annotations=anotations)

    def create_annotation(self, time_slot_start:int, time_slot_end:int, annotation_value:str) -> parse_eaf.Annotation:
        return parse_eaf.Annotation(id="key"+ str(time_slot_start),
                            time_slot_start_id="t",
                            time_slot_start=time_slot_start,
                            time_slot_end_id="t",
                            time_slot_end=time_slot_end,
                            annotation_value=annotation_value)


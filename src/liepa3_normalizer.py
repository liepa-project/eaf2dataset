import re
import unicodedata

# Based on transformers.models.whisper.english_normalizer import BasicTextNormalizer

class Liepa3TextNormalizer:
    def __init__(self):
        self.clean = self.remove_symbols
        self.regex_dual_definition = r"\(([\w\s]*)\/[\w\s]*\)" # (von triero/von trier)
        self.regex_spelled = r"<([\w\s]*)>" # <mantrierodžek>

    def remove_symbols(self, s: str):
        """
        Replace any other markers, symbols, punctuations with a space, keeping diacritics
        """
        return "".join(" " if unicodedata.category(c)[0] in "MSP" else c for c in unicodedata.normalize("NFKC", s))

    def __call__(self, s: str):

        s = s.replace("—", "-")
        s = s.replace("“", "\"")
        s = s.replace("„", "\"")
        s = s.replace("\t", " ")
        s = re.sub(self.regex_dual_definition, r"\1", s) # (Monik/Monique)
        s = re.sub(self.regex_spelled, r"\1", s) # <eta>
        # s = re.sub(r"[<\[][^>\]]*[>\]]", "", s)  # remove words between brackets: 
        # s = re.sub(r"\(([^)]+?)\)", "", s)  # remove words between parenthesis: 
        # s = self.clean(s).lower()
        s = re.sub(r"\s+", " ", s)  # replace any successive whitespace characters with a space


        s = s.strip()
        return s
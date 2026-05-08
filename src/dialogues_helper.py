import re
from datetime import datetime
from typing import List

# Regular expression pattern for parsing subtitle files (.srt).
SRT_PATTERN = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)\n'

class DialogueLine:
    def __init__(self, line_number, start, end, text):
        self.line_number = int(line_number)
        self.start = self._timecode_to_sec(start)
        self.end = self._timecode_to_sec(end)
        self.text = text

    def to_dict_only_number_and_text(self):
        # Convert the scene data to a dictionary for JSON serialization, ensuring path is a string.
        return { 
            "line_number": self.line_number,
            "text": self.text,
        }
    
    @staticmethod
    def _timecode_to_sec(timecode):
        dt = datetime.strptime(timecode, "%H:%M:%S,%f")
        return dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1000000

    def __str__(self):
        # String representation for easy debugging and logging.
        return f"Subtitle number: {self.line_number}\nStart Frame: {self.start}\nEnd Frame: {self.end}\nDialogue line: {self.text}"
    
    
def extract_dialogue_lines(subtitles_path: str) -> List[DialogueLine]:
            
    with open(subtitles_path) as f:
        text = f.read()

    matches = re.findall(SRT_PATTERN, text)
    
    return [DialogueLine(num, start, end, dialogue_text) for num, start, end, dialogue_text in matches]
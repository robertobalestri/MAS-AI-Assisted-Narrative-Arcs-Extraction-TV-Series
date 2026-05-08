import json
import re
import os
from typing import List
from nltk.tokenize import sent_tokenize
from functools import lru_cache
from difflib import SequenceMatcher
from typing import Dict



def load_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1252') as f:
            return f.read()
    
def load_json(file_path: str) -> List[Dict]:
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1252') as f:
            return json.load(f)
    
def jaccard_index(set1: set, set2: set) -> float:
    """
    Calculate the Jaccard index between two sets.

    Args:
        set1 (set): The first set.
        set2 (set): The second set.

    Returns:
        float: The Jaccard index.
    """
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0.0

def clean_text(text: str) -> str:
    """
    Preprocess the input text by removing extra whitespace and normalizing line breaks.

    Args:
        text (str): The text to preprocess.

    Returns:
        str: The preprocessed text.
    """
    text = re.sub(r'\s+', ' ', text).strip()
    return text
    
@lru_cache(maxsize=100)
def split_into_sentences(text: str) -> List[str]:
    """
    Split the input text into sentences.

    Args:
        text (str): The text to be split.

    Returns:
        List[str]: A list of sentences.
    """
    return sent_tokenize(text)

def remove_duplicates(sentences):
    """
    Remove duplicate sentences from a list.

    Args:
        sentences (list): List of sentences to process.

    Returns:
        list: List of unique sentences.
    """
    seen = set()
    unique_sentences = []
    for sentence in sentences:
        if sentence not in seen:
            seen.add(sentence)
            unique_sentences.append(sentence)
    return unique_sentences

def save_json(data: dict, file_path: str) -> None:
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def calculate_similarity_list_of_strings_jaccard(list1: List[str], list2: List[str]) -> float:
    """
    Calculate the maximum similarity score between two lists of strings using the Jaccard index.

    Args:
        list1 (List[str]): The first list of strings.
        list2 (List[str]): The second list of strings.

    Returns:
        float: The maximum similarity score between any two strings from the lists.
    """
    max_similarity = 0
    for str1 in list1:
        for str2 in list2:
            similarity = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
            max_similarity = max(max_similarity, similarity)
    return max_similarity
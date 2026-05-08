import re
from typing import List
from nltk.tokenize import sent_tokenize
from functools import lru_cache
from langchain_litellm import ChatLiteLLM  # Updated import
from src.utils.logger_utils import setup_logging
from src.utils.text_utils import split_into_sentences, remove_duplicates
import json
from textwrap import dedent
from src.utils.llm_utils import clean_llm_text_response
from langchain_core.messages import HumanMessage

# Set up colored logging
logger = setup_logging(__name__)

def replace_pronouns_with_names(text: str, intelligent_llm: ChatLiteLLM, cheap_llm: ChatLiteLLM, chunk_size: int = 60, context_size: int = 6) -> str:
    """
    Replace pronouns and generic references in the text with specific character names.

    Args:
        text (str): The text to modify.
        intelligent_llm (ChatLiteLLM): The intelligent language model instance.
        cheap_llm (ChatLiteLLM): The cheap language model instance.

    Returns:
        str: The modified text with pronouns replaced by names.
    """
    sentences = split_into_sentences(text)
    named_sentences = []

    for i in range(0, len(sentences), chunk_size):
        end_index = min(i + chunk_size, len(sentences))
        chunk = sentences[i:end_index]
        
        logger.info(f"Processing {len(chunk)} sentences (index {i} to {end_index-1}).")

        prompt = (
            "Rewrite the following text, replacing pronouns and generic references with specific character names while simplifying the sentence structure. "
            "Follow these guidelines:\n"
            "1. Break complex periods into shorter, simple sentences. Ensure every single phrase explicitly contains the character's name instead of generic pronouns.\n"
            "2. Replace all pronouns (he, she, they, etc.) with the appropriate character name. Pay attention to the context to understand who the pronoun refers to, don't just replace the pronoun with the nearest names you find.\n"
            "3. Replace generic references like 'a woman', 'the boy', 'the old man' with specific character names found in the provided text, if possible.\n"
            "4. Clarify possessive pronouns (his, her, their) when the reference is unclear.\n"
            "5. Rephrase the sentences in a simpler way, avoiding ambiguities and maintaining all the details about place, time, characters, and actions. Use indirect quotation instead of direct quotes.\n"
            "6. Split the text in a way that each period is focused on a single character or event.\n"
            "7. Separate each resulting simple sentence with a newline character.\n"
            "8. Do not add or remove any information beyond the replacements and simplifications.\n"
            "9. You will be given the previous context (if any) of the text you are modifying. You should only output the rewritten [TEXT TO MODIFY] text. You should never output the text included in the [PREVIOUS CONTEXT] tags.\n"
            "10. Do not make up character names.\n"
            "11. If a character is introduced with a generic description (e.g., 'A woman') and is later identified by name within the text, use their specific name from the very first mention."
            
        )
        
        if i > 0:
            # Use the last 'context_size' sentences from the previous chunk as context
            context = '\n'.join(named_sentences[-context_size:])
            prompt += f"[PREVIOUS CONTEXT]\n{context}\n[/PREVIOUS CONTEXT]\n\n"
        
        prompt += f"[TEXT TO MODIFY]\n{' '.join(chunk)}\n[/TEXT TO MODIFY]\n\nRewritten text:"
        
        logger.info(f"Sending prompt to LLM for pronoun and reference replacement:\n{prompt}\n")
        response = intelligent_llm.invoke([HumanMessage(content=prompt)])  # Updated method
        logger.info(f"Received response from LLM:\n{response.content}\n")  # Corrected to use content
        
        response_sentences = [s.strip() for s in response.content.split('\n') if s.strip()]  # Corrected to use content
        
        # If this is not the first chunk, remove any sentences that are duplicates from the context
        if i > 0:
            response_sentences = [s for s in response_sentences if s not in named_sentences[-context_size:]]
        
        named_sentences.extend(response_sentences)
    
    named_sentences = remove_duplicates(named_sentences)
    return '\n'.join(named_sentences)


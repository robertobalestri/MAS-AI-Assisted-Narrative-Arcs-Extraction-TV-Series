from src.utils.logger_utils import setup_logging
from typing import List
from langchain_litellm import ChatLiteLLM
import re
from langchain_core.messages import HumanMessage
from src.utils.text_utils import split_into_sentences, clean_text
from src.utils.llm_utils import clean_llm_text_response
from textwrap import dedent

# Set up colored logging
logger = setup_logging(__name__)

def split_text(window_text: str, llm: ChatLiteLLM) -> List[str]:
    prompt = dedent(f"""
    Analyze the following text and insert <BOS> (Begin of Scene) tags only where a new semantic scene begins.
    If the text starts with an incomplete scene from a previous section, continue that scene and only add <BOS> tags for new scenes after it.

    Guidelines:
    - Scene shifts: A new scene usually starts when there is a major change in time or location, or a change of narrative or thematic focus during the same situation.
    - Dialogue continuity: Do not add a <BOS> tag if the scene remains the same during an ongoing conversation, unless there is a change in the focus of the discourse.
    - Minor transitions: Small movements within the same setting should not trigger a new scene tag unless the overall narrative shifts significantly.
    - Sentence integrity: Only place <BOS> tags at the beginning of sentences that introduce a new scene. Do not break sentences unnecessarily.
    - Event and Action focus: Only one major event or action usually happens per scene.
    - Thematic shifts: Continuous narration can consist of multiple scenes if the thematic focus substantially changes.
    - Time and Place words: Introductory words indicating time or place changes are potential indicators of a new scene. For example: "The next day", "Later", "In the forest", "On the way to...", "One day", "One evening", etc. might indicate a new scene.
    - Difference between anticipation and resolution: The anticipation of an event can be in one scene, and the resolution in another.

    Text to analyze:
    {window_text}

    Please return the text with <BOS> tags inserted only where significant narrative shifts occur. If the text starts with a continuation of a previous scene, do not add a <BOS> tag at the beginning.
    """)

    response = llm.invoke([HumanMessage(content=prompt)])
    marked_text = clean_llm_text_response(str(response.content).strip())

    segments = re.split(r'<BOS>', marked_text)
    segments = [clean_text(seg.strip()) for seg in segments if seg.strip()]
    
    return segments

def correct_segments(segments: List[str], llm: ChatLiteLLM, batch_size: int = 3) -> List[str]:
    logger.info("Starting segment correction")
    corrected_segments = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i+batch_size]
        
        prompt = dedent(f"""
        Analyze the following segments and determine if they meet the criteria for valid semantic scenes. If any segment is invalid, please correct it by merging or splitting as necessary.

        Guidelines:
        - Scene shifts: A new scene usually starts when there is a major change in time or location, or a substantial change of narrative or thematic focus.
        - Dialogue continuity: The scene remains the same during an ongoing conversation, unless there is a substantial change in the focus of the discourse.
        - Minor transitions: Small movements within the same setting should not trigger a new scene unless the overall narrative shifts significantly.
        - Sentence integrity: Only split scenes at the beginning of sentences that introduce a new scene. Do not break sentences unnecessarily.
        - Event and Action focus: Only one major event or action usually happens per scene.
        - Thematic shifts: Continuous narration can consist of multiple scenes if the thematic focus substantially changes.
        - Time and Place words: Introductory words indicating time or place changes are potential indicators of a new scene. For example: "The next day", "Later", "In the forest", "On the way to...", "One day", "One evening", etc. might indicate a new scene.
        - Difference between anticipation and resolution: The anticipation of an event can be in one scene, and the resolution in another.

        Segments to analyze:
        {' '.join(f'<BOS> {seg}' for seg in batch)}

        Please return the corrected segments, each starting with <BOS>. If no corrections are needed, simply return the original segments.
        """)

        response = llm.invoke([HumanMessage(content=prompt)])
        corrected_text = clean_llm_text_response(str(response.content).strip())

        batch_corrected_segments = re.split(r'<BOS>', corrected_text)
        batch_corrected_segments = [clean_text(seg.strip()) for seg in batch_corrected_segments if seg.strip()]

        corrected_segments.extend(batch_corrected_segments)
        
        logger.info(f"Corrected batch {i//batch_size + 1}. Segments: {len(batch_corrected_segments)}")

    logger.info(f"Segment correction complete. Total segments: {len(corrected_segments)}")
    return corrected_segments

def semantic_split(text: str, llm: ChatLiteLLM, window_size: int = 20, correction_batch_size: int = 3) -> List[str]:
    logger.info("Starting semantic split")

    sentences = split_into_sentences(text)
    total_sentences = len(sentences)
    
    sentences[0] = '<BOS> ' + sentences[0]
    
    initial_segments = []
    last_incomplete_segment = ""

    for i in range(0, total_sentences, window_size):
        window_end = min(i + window_size, total_sentences)
        window_text = last_incomplete_segment + ' ' + ' '.join(sentences[i:window_end])
        window_text = window_text.strip()

        logger.debug(f"Processing window: {i} to {window_end}")

        result = split_text(window_text, llm)
        
        # Process the segments
        if result:
            if len(result) > 1:
                # Add all complete segments except the last one to initial_segments
                initial_segments.extend(result[:-1])
                
                # Keep the last segment as potentially incomplete
                last_incomplete_segment = result[-1]
            else:
                # If there's only one segment, treat it as incomplete
                last_incomplete_segment = result[0]
        else:
            # If no segments were created, add the whole window text as incomplete
            last_incomplete_segment += ' ' + window_text
        
        logger.info(f"Window processing complete. Segments: {len(result)}")

    # Add the last incomplete segment if it exists
    if last_incomplete_segment:
        initial_segments.append(last_incomplete_segment.strip())

    logger.info(f"Initial semantic split complete. Number of segments: {len(initial_segments)}")
    
    logger.debug(f"Initial segments: {[str(segment) + '...' for segment in initial_segments]}")

    # Correct the segments
    final_segments = correct_segments(initial_segments, llm, correction_batch_size)

    logger.info(f"Semantic split and correction complete. Final number of segments: {len(final_segments)}")
    logger.debug(f"Final segments: {[seg[:50] + '...' for seg in final_segments]}")

    return final_segments
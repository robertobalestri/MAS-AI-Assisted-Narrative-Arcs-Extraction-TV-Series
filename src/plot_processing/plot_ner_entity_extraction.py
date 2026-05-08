# plot_ner_extraction.py

import spacy
from typing import List, Tuple
from collections import defaultdict
import json
import os
import re
from textwrap import dedent
import logging

from langchain_core.messages import HumanMessage
from langchain_litellm import ChatLiteLLM

from src.utils.logger_utils import setup_logging
from src.utils.llm_utils import clean_llm_json_response

# Import your models and services
from src.narrative_storage_management.repositories import DatabaseSessionManager, CharacterRepository
from src.narrative_storage_management.character_service import CharacterService
from src.plot_processing.plot_processing_models import EntityLink  # Adjust import path if needed
from src.narrative_storage_management.narrative_models import CharacterAppellation, Character  # Import models if needed

logger = setup_logging(__name__)
nlp = spacy.load("en_core_web_trf")

titles_list = [
    "Dr", "Dr.", "Mr", "Mr.", "Ms", "Ms.", "Miss", "Miss.", "Mrs", "Mrs.",
    "Mme", "Mme.", "Prof", "Prof.", "Doc", "Doctor", "Sir", "Lady", "Dame",
    "Duke", "Duchess", "Count", "Countess", "Baron", "Baroness", "King",
    "Queen", "Prince", "Princess", "Earl", "Don", "Sister", "Brother",
    "Colonel", "Major", "Captain", "Lieutenant", "Sergeant", "Private",
    "Doctorate", "PhD", "MD", "MA", "BA", "BS", "BSc", "Bachelor", "Master",
    "Masters", "M.A.", "M.B.A.", "M.D.", "M.S.", "M.Sc."
]

def extract_entities_with_spacy(text: str) -> List[str]:
    """
    Extract entities from the text using spaCy's NER, including titles.

    Args:
        text (str): The input text to process.

    Returns:
        List[str]: A list of entity mentions, including titles.
    """
    doc = nlp(text)
    entities = set()

    # Process entities in spans
    current_entity = []
    for token in doc:
        # If we find a PERSON entity
        if token.ent_type_ == "PERSON":
            current_entity.append(token.text)
        else:
            # If we have collected a person entity, process it
            if current_entity:
                entity_text = " ".join(current_entity).strip()
                
                # Remove possessive 's if present
                if entity_text.endswith("'s"):
                    entity_text = entity_text[:-2].strip()
                
                # Check for title
                prev_token = doc[token.i - len(current_entity) - 1] if token.i - len(current_entity) > 0 else None
                if prev_token and prev_token.text in titles_list:
                    entity_text = f"{prev_token.text} {entity_text}"

                # Add entity if it's valid
                if len(entity_text.strip()) > 1 and not all(c in {';', ',', '.', ' '} for c in entity_text):
                    entities.add(entity_text)
                
                current_entity = []

    # Handle any remaining entity at the end of the text
    if current_entity:
        entity_text = " ".join(current_entity).strip()
        if len(entity_text) > 1 and not all(c in {';', ',', '.', ' '} for c in entity_text):
            entities.add(entity_text)

    return list(entities)

def refine_entities(
    entities: List[str],
    plot: str,
    llm: ChatLiteLLM,
    existing_entities: List[EntityLink]
) -> List[EntityLink]:
    """
    Refine the extracted entities using a language model to ensure accuracy and completeness.

    Args:
        entities (List[str]): The list of extracted entities.
        plot (str): The plot text for context.
        llm (ChatLiteLLM): The language model for refining entities.
        existing_entities (List[EntityLink]): The list of existing entities for reference.

    Returns:
        List[EntityLink]: A list of refined entities as EntityLink objects.
    """
    existing_info = "Existing characters:\n" + "\n".join(
        [f"{e.best_appellation}" for e in existing_entities]
    )
    new_entities = "New characters to refine:\n" + "\n".join(entities)

    prompt = dedent(f"""Given the following characters extracted from the plot, please refine them:
                Plot: {plot}
                {existing_info}
                
                {new_entities}
                
                For each character:
                1. Provide a primary name in the format "name_surname" (lowercase with underscores). If a character has only one name or surname with a title, use the title and the name (e.g. "dr_johnson").
                2. In appellations, list ALL names, titles and nicknames used for the character in the plot.
                3. Include full names, first names, last names, titles, and nicknames in appellations.
                4. For families or groups that can't be identified as single entities, use "the_surname" format. Families and members of the family are different entities. They should be added separately and the family members should not be listed in the appellations of the family.
                5. Treat individuals with the same surname (e.g., Mr. Smith and Mrs. Smith) as separate entities unless there's clear evidence they're the same person.
                6. Exclude generic appellatives (e.g. "the baby", "the old man", "the woman", "she", "he", etc.) and non-character entities (like name of Universities, Companies, etc.), also exclude names that are not characters (for example in "Bob looks like Dumbo", Dumbo is not a character).
                7. Sometimes some characters might be referred only with a generic term like "the dragon", "the mage", "the robot", etc. In those cases use the generic term as the entity name.
                8. If a character is not in the existing entities list, you can still add it if you are sure that it's a new character.
                9. To choose the best appellation follow this rule: if name and surname are present ALWAYS use just them without title. If only one of the two is present, but it's present also a title, use the appellation that comprehends also the title.

                Respond with a JSON list of objects in this format:
                [
                    {{
                        "entity_name": "primary_name",
                        "best_appellation": "Chosen Appellation",
                        "appellations": ["Appellation1", "Appellation2", ...]
                    }},
                    ...
                ]
                """)

    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        refined_entities = clean_llm_json_response(response.content)
        logger.info(f"Refined entities: {refined_entities}")
        
        if isinstance(refined_entities, list) and len(refined_entities) > 0:
            # Ensure best appellation is included in the appellations list
            for entity in refined_entities:
                best_appellation = entity.get("best_appellation")
                if best_appellation and best_appellation not in entity.get("appellations", []):
                    entity["appellations"].append(best_appellation)

            return [EntityLink(**entity) for entity in refined_entities]
        else:
            logger.error(f"Unexpected format for refined entities: {refined_entities}")
            return []
    except ValueError as e:
        logger.error(f"Failed to clean and parse LLM response: {e}")
        return []

def resolve_duplicate_entities(
    existing_entities: List[EntityLink],
    refined_entities: List[EntityLink],
    plot: str,
    llm: ChatLiteLLM
) -> List[EntityLink]:
    """
    Resolve duplicate entities that share the same appellation by consulting the language model.
    """
    # Create a mapping of entity_name to EntityLink for quick lookup
    entity_map = {
        entity.entity_name: entity 
        for entity in existing_entities + refined_entities
    }
    
    # Create a mapping of appellations to entity_names
    appellation_map = defaultdict(set)
    for entity in entity_map.values():
        for appellation in entity.appellations:
            appellation_map[appellation].add(entity.entity_name)
    
    # Track which entities have been merged
    merged_pairs = set()

    for appellation, entity_names in appellation_map.items():
        if len(entity_names) > 1:
            entity_names = sorted(entity_names)  # Sort for consistent processing
            
            for i, name1 in enumerate(entity_names):
                for name2 in entity_names[i+1:]:
                    # Skip if this pair has already been processed
                    if (name1, name2) in merged_pairs:
                        continue
                        
                    entity1 = entity_map[name1]
                    entity2 = entity_map[name2]
                    
                    prompt = dedent(f"""There are multiple entities sharing the same appellation "{appellation}":
                    Entity 1: {entity1.entity_name} (appellations: {', '.join(entity1.appellations)})
                    Entity 2: {entity2.entity_name} (appellations: {', '.join(entity2.appellations)})
                    Based on the following plot context, should these be treated as separate entities or merged into one?
                    Plot: {plot}
                    Please provide a clear answer: "separate" or "merge".
                    """)

                    response = llm.invoke([HumanMessage(content=prompt)])
                    decision = response.content.strip().lower()

                    logger.info(f"LLM decision for {appellation} between {name1} and {name2}: {decision}")

                    if decision == "merge":
                        # Create merged entity
                        merged_appellations = list(set(entity1.appellations + entity2.appellations))
                        merged_entity = EntityLink(
                            entity_name=entity1.entity_name,  # Keep the first entity's name
                            best_appellation=entity1.best_appellation,
                            appellations=merged_appellations
                        )
                        entity_map[entity1.entity_name] = merged_entity
                        entity_map[entity2.entity_name] = merged_entity  # Point both to same entity
                        merged_pairs.add((name1, name2))
                    
                    # Mark as processed regardless of decision
                    merged_pairs.add((name1, name2))

    # Collect final unique entities
    processed_names = set()
    final_entities = []
    
    for entity in entity_map.values():
        if entity.entity_name not in processed_names:
            final_entities.append(entity)
            processed_names.add(entity.entity_name)

    return final_entities

def substitute_appellations_with_names(
    text: str,
    entities: List[EntityLink],
    llm: ChatLiteLLM
) -> str:
    """
    Substitute appellations in the text with their corresponding best appellations.
    Sorts entities by appellation length to handle longer appellations first.
    """
    if not entities:
        return text

    # Sort entities by appellation length (longest first) to avoid partial replacements
    sorted_entities = sorted(entities, key=lambda e: len(e.entity_name), reverse=True)
    
    # Create a copy of the text to modify
    modified_text = text

    for entity in sorted_entities:
        # Replace entity name with best appellation
        if entity.entity_name and len(entity.entity_name.strip()) > 1:  # Skip empty or single-char names
            modified_text = modified_text.replace(entity.entity_name, entity.best_appellation)

    return modified_text

def normalize_entities_names_to_best_appellation(
    text: str,
    entities: List[EntityLink]
) -> str:
    """Normalize entity names in the text to their best appellations."""
    for entity in entities:
        text = text.replace(f"[{entity.entity_name}]", entity.best_appellation)
    return text

def normalize_names(
    text: str,
    entities: List[EntityLink],
    llm: ChatLiteLLM
) -> str:
    """Normalize names in the text using substitution and best appellations."""
    substituted_text = substitute_appellations_with_names(text, entities, llm)
    normalized_text = normalize_entities_names_to_best_appellation(substituted_text, entities)
    return normalized_text

def extract_and_refine_entities(
    text: str,
    series: str,
    llm: ChatLiteLLM,
    refined_output_path: str,
    raw_output_path: str,
    season_entities_path: str
) -> List[EntityLink]:
    """
    Extract and refine entities from the provided text, saving results to specified paths.
    Also ensures all entities are stored in the database.
    """
    # Extract new entities
    extracted_entities = extract_entities_with_spacy(text)
    
    # Save raw entities
    with open(raw_output_path, "w", encoding="utf-8") as raw_file:
        json.dump(extracted_entities, raw_file, indent=2)

    # Load existing entities
    existing_entities = []
    if os.path.exists(season_entities_path):
        with open(season_entities_path, 'r') as f:
            existing_entities = [EntityLink(**entity) for entity in json.load(f)]
        logger.info(f"Loaded {len(existing_entities)} existing entities from season file")

    # Pre-process and refine entities
    preprocessed_text = substitute_appellations_with_names(text, existing_entities, llm)
    refined_entities = refine_entities(extracted_entities, preprocessed_text, llm, existing_entities)

    # Resolve duplicates
    refined_entities = resolve_duplicate_entities(existing_entities, refined_entities, text, llm)

    # Initialize DatabaseSessionManager
    db_manager = DatabaseSessionManager()

    with db_manager.session_scope() as session:
        # Initialize repositories and services
        character_repository = CharacterRepository(session)
        character_service = CharacterService(character_repository)

        # Store all entities in the database
        for entity in refined_entities:
            character_service.add_or_update_character(entity, series)

    # Update season entities with new refined entities
    all_entities = {entity.entity_name: entity for entity in existing_entities}  # Use a dictionary to avoid duplicates
    for entity in refined_entities:
        all_entities[entity.entity_name] = entity  # This will overwrite if the entity already exists

    # Save refined entities
    with open(refined_output_path, "w", encoding="utf-8") as refined_file:
        json.dump([entity.model_dump() for entity in refined_entities], refined_file, indent=2)
    
    # Update season entities file
    with open(season_entities_path, "w", encoding="utf-8") as season_file:
        json.dump([entity.model_dump() for entity in all_entities.values()], season_file, indent=2)
    
    return refined_entities

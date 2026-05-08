# llm_service.py

from textwrap import dedent
from typing import Optional, Dict, List
from src.narrative_storage_management.narrative_models import NarrativeArc
from src.ai_models.ai_models import get_llm, LLMType
from langchain_core.prompts import ChatPromptTemplate
from src.utils.llm_utils import clean_llm_json_response
from src.utils.logger_utils import setup_logging
import logging

logger = setup_logging(__name__)

class LLMService:
    """Service to interact with the LLM."""

    def __init__(self):
        self.llm = get_llm(LLMType.INTELLIGENT)

    def merge_identical_arcs(self, new_arc: NarrativeArc, existing_arc: NarrativeArc) -> dict:
        """Merge two arcs that have identical titles."""
        base_prompt = dedent("""You are an expert in analyzing narrative arcs in TV series.

                Given two versions of the same narrative arc (they have identical titles):

                Version A:
                description: {description_a}
                main_characters: {main_characters_a}

                Version B:
                description: {description_b}
                main_characters: {main_characters_b}

                Create a merged version that combines all the information. These are definitely the same arc, so focus on:
                1. Combining the descriptions comprehensively
                2. Maintaining narrative consistency
                3. Preserving all important details

                Provide your response in JSON format as:
                {{
                    "merged_description": "The combined description that incorporates details from both versions"
                }}
                """)

        prompt = ChatPromptTemplate.from_template(base_prompt)

        response = self.llm.invoke(prompt.format_messages(
            description_a=existing_arc.description,
            main_characters_a=', '.join([f"{char.best_appellation}" for char in existing_arc.main_characters]),
            description_b=new_arc.description,
            main_characters_b=', '.join([f"{char.best_appellation}" for char in new_arc.main_characters])
        ))

        try:
            response_json = clean_llm_json_response(response.content)
            if isinstance(response_json, list):
                response_json = response_json[0]
            
            if "merged_description" not in response_json:
                raise ValueError("Missing 'merged_description' in LLM response")
            
            logger.info(f"Merged identical arcs with title '{existing_arc.title}'")
            return {
                "merged_title": existing_arc.title,  # Keep original title
                "merged_description": response_json["merged_description"]
            }

        except Exception as e:
            logger.error(f"Error parsing LLM response for identical arc merging: {e}")
            return {
                "merged_title": existing_arc.title,
                "merged_description": f"{existing_arc.description}\n\nAdditional context: {new_arc.description}"
            }

    def decide_arc_merging(self, new_arc: NarrativeArc, existing_arc: NarrativeArc) -> dict:
        """Decide if two similar (but not identical) arcs should be merged."""
        base_prompt = dedent("""You are an expert in analyzing narrative arcs in TV series.

                Given these two narrative arcs:

                Arc A:
                title: {title_a}
                description: {description_a}
                main_characters: {main_characters_a}
                Arc Type: {arc_type_a}

                Arc B:
                title: {title_b}
                description: {description_b}
                main_characters: {main_characters_b}
                Arc Type: {arc_type_b}

                Analyze if they represent the same narrative arc. Consider:
                1. The core narrative development being tracked
                2. Whether one is a subset/continuation of the other
                3. The main characters involved
                4. The specific events or developments described
                             
                If they are similar arcs, provide a merged version that combines all the information, even if they are not identical.
                You should not be too strict.

                Provide your response in JSON format as:
                {{
                    "same_arc": true or false,
                    "justification": "Your detailed explanation here",
                    "merged_title": "ONLY IF same_arc is true: Best title for the merged arc",
                    "merged_description": "ONLY IF same_arc is true: Combined description"
                }}
                """)

        prompt = ChatPromptTemplate.from_template(base_prompt)

        response = self.llm.invoke(prompt.format_messages(
            title_a=existing_arc.title,
            description_a=existing_arc.description,
            main_characters_a=', '.join([f"{char.best_appellation}" for char in existing_arc.main_characters]),
            arc_type_a=existing_arc.arc_type,
            title_b=new_arc.title,
            description_b=new_arc.description,
            main_characters_b=', '.join([f"{char.best_appellation}" for char in new_arc.main_characters]),
            arc_type_b=new_arc.arc_type,
        ))

        try:
            response_json = clean_llm_json_response(response.content)
            if isinstance(response_json, list):
                response_json = response_json[0]
            
            if "same_arc" not in response_json or "justification" not in response_json:
                raise ValueError("Missing required fields in LLM response")
            
            if new_arc.title != existing_arc.title:
                logger.warning(f"Decided {response_json['same_arc']} for 'arc merging' for '{existing_arc.title}' and '{new_arc.title}' and they have DIFFERENT titles")
            else:
                logger.warning(f"Decided {response_json['same_arc']} for 'arc merging' for '{existing_arc.title}' and '{new_arc.title}' and they have the SAME title")

            return response_json

        except Exception as e:
            logger.error(f"Error parsing LLM response for arc merging decision: {e}")
            return {
                "same_arc": False,
                "justification": "LLM error",
                "merged_title": existing_arc.title,
                "merged_description": f"{existing_arc.description}\n\nAdditional context: {new_arc.description}"
            }

    def generate_progression_content(self, arc_title: str, arc_description: str, episode_plot_path: str, other_arcs_context: Optional[List[Dict[str, str]]] = None) -> str:
        """Generate progression content for an arc in a specific episode and validate it against the plot."""
        try:
            # Early validation of required parameters
            if not arc_title or not arc_description:
                logger.error("Missing required arc information for generation")
                logger.error(f"Title: {arc_title}")
                logger.error(f"Description: {arc_description}")
                return "NO_PROGRESSION"

            logger.info(f"Generating progression for arc: {arc_title}")
            logger.info(f"Episode plot path: {episode_plot_path}")

            # Read the episode plot
            with open(episode_plot_path, 'r') as f:
                episode_plot = f.read()
                logger.info(f"Episode plot length: {len(episode_plot)} characters")

            # Initial progression generation prompt with Chain of Thought
            base_prompt = dedent(
                """You are an expert in analyzing narrative arcs in TV series. Extract ONLY the most crucial plot points that advance the specific narrative described in this arc.

                Narrative Arc to Track
                Title: {arc_title}
                Description: {arc_description}

                Episode Plot
                {episode_plot}
                
                Progression Guidelines:
                    - Write a MAXIMUM of 3-5 brief sentences
                    - Each sentence must:
                    • Advance the specific narrative described in the arc
                    • Contain only verified plot events
                    • Focus on actions and outcomes
                    - Exclude:
                    • any event that is not explicitly about part of this narrative arc
                    • speculation or interpretation such as "X do this, highlighting his dedication" or "X do that indicating its romantic tension". Just use "X do this" or "X do that"
                    • judgement or opinion (such as "X do this demonstrating his resilience")

                If the arc does not have any developments in this episode, respond with "NO_PROGRESSION".

                Return your answer as a JSON object with the following structure:
                {{
                    "Chain of Thought": "Detailed reasoning explaining how the progression content was derived and why these events are relevant to the arc.",
                    "ProgressionContent": "Content containing exclusively the progression made of sentences separated by dots. No quotes, no numbered lists, no other formatting."
                }}
                """
            )

            prompt = ChatPromptTemplate.from_template(base_prompt)

            # First LLM call to generate progression
            logger.info(f"Starting progression generation for arc '{arc_title}' in {episode_plot_path}")
            
            response = self.llm.invoke(prompt.format_messages(
                arc_title=arc_title,
                arc_description=arc_description,
                episode_plot=episode_plot
            ))

            first_call_result = clean_llm_json_response(response.content.strip())
            if isinstance(first_call_result, list):
                first_call_result = first_call_result[0]

            logger.info(f"First LLM call response: {first_call_result}")
            chain_of_thought = first_call_result.get("Chain of Thought", "")
            progression_content = first_call_result.get("ProgressionContent", "").strip()

            logger.info(f"Chain of Thought (First Call): {chain_of_thought}")
            logger.info(f"Generated Progression Content: {progression_content}")

            if progression_content == "NO_PROGRESSION":
                logger.info(f"No progression found for arc '{arc_title}' - Generation complete")
                return progression_content

            if not progression_content:
                logger.warning("LLM returned empty content")
                return "NO_PROGRESSION"

            logger.info(f"Generated progression content: {progression_content}")

            # Validation prompt to confirm arc presence and avoid false positives
            validation_prompt = dedent(
                """You are an expert in verifying narrative arc presence in TV series. 
                Your task is to verify that the first agent's reasoning is correct and provide a refined progression focusing only on the specific arc.

                Episode Plot:
                {episode_plot}

                Arc Title: {arc_title}
                Arc Description: {arc_description}

                First Agent's Analysis:
                {first_agent_chain_of_thought}
                Generated Content: {progression_content}

                Validation Guidelines:
                - Your primary tasks are:
                    • Verify there is no hallucination
                    • Assess how confident you are that this arc is present in the episode
                    • Rewrite the progression to include ONLY events directly related to this specific arc
                
                - When calculating the probability of presence percentage consider:
                    • How clearly the arc's elements are present in the episode (100% = perfectly clear presence)
                    • Whether the events are actually about this arc or a different one
                    • Whether the characters and events mentioned actually appear
                    • The relevance of the events to this specific arc
                    
                - Do NOT reduce probability of presence just because:
                    • The arc's presence is subtle or minor
                    • The progression is short
                    • The arc is in an early or late stage

                Return your answer as a JSON object with the following structure:
                {{
                    "Chain of Thought": "Detailed reasoning explaining your confidence assessment and progression refinement",
                    "Probability of Presence": "Number between 0 and 100 representing how confident you are that this arc is present",
                    "RefinedProgression": "The progression rewritten to focus only on events directly related to this arc. Return NO_PROGRESSION if you can't find any relevant events."
                }}
                """
            )

            prompt = ChatPromptTemplate.from_template(validation_prompt)

            logger.info("Sending validation request to LLM to verify arc presence and relevance:")
            validation_response = self.llm.invoke(prompt.format_messages(
                episode_plot=episode_plot,
                arc_title=arc_title,
                arc_description=arc_description,
                first_agent_chain_of_thought=chain_of_thought,
                progression_content=progression_content
            ))

            validation_result = clean_llm_json_response(validation_response.content.strip())
            if isinstance(validation_result, list):
                validation_result = validation_result[0]

            logger.info(f"Validation LLM response: {validation_result}")
            chain_of_thought = validation_result.get("Chain of Thought", "")
            probability_of_presence = float(validation_result.get("Probability of Presence", 0))
            refined_progression = validation_result.get("RefinedProgression", "").strip()

            logger.info(f"Chain of Thought: {chain_of_thought}")
            logger.info(f"Probability of Presence: {probability_of_presence}%")
            logger.info(f"Refined Progression: {refined_progression}")

            if probability_of_presence >= 40 and refined_progression and refined_progression != "NO_PROGRESSION":
                logger.info(f"Successfully generated progression for arc '{arc_title}' with {probability_of_presence}% confidence")
                return refined_progression
            else:
                logger.info(f"No valid progression found for arc '{arc_title}' after validation")
                return "NO_PROGRESSION"

        except FileNotFoundError as e:
            logger.error(f"Episode plot file not found: {episode_plot_path}")
            return "NO_PROGRESSION"
        except Exception as e:
            logger.error(f"Error generating progression for arc '{arc_title}': {str(e)}")
            return "NO_PROGRESSION"
        finally:
            logger.info(f"Completed progression generation attempt for arc '{arc_title}'")


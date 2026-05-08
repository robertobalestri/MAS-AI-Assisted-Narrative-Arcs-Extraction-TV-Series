from langchain_litellm import ChatLiteLLM
from langchain_core.embeddings import Embeddings
import litellm
from dotenv import load_dotenv
import os
from enum import Enum


try:
    from src.utils.logger_utils import setup_logging
    load_dotenv(override=True)

    # Set up logging
    logger = setup_logging(__name__)
except:
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    load_dotenv(override=True)



# Global variables to store LLM instances
_intelligent_llm = None
_cheap_llm = None

#define enum for LLM types
class LLMType(Enum):
    INTELLIGENT = "intelligent"
    CHEAP = "cheap"

def _initialize_llm(intelligent_or_cheap: LLMType) -> ChatLiteLLM:
    """
    Initialize and return a ChatLiteLLM instance backed by LiteLLM.

    LiteLLM uses the "azure/<deployment_name>" model prefix to route calls to
    Azure OpenAI. Credentials are passed explicitly so they take priority over
    any environment variables that might conflict.

    Args:
        intelligent_or_cheap (LLMType): Specify whether to initialize the
            'intelligent' or 'cheap' LLM.

    Returns:
        ChatLiteLLM: A LangChain-compatible LLM instance backed by LiteLLM.
    """
    try:
        provider = os.getenv("LLM_PROVIDER", "")
        api_key = os.getenv("LLM_API_KEY")
        api_base = os.getenv("LLM_API_BASE")
        api_version = os.getenv("LLM_API_VERSION")

        if intelligent_or_cheap == LLMType.INTELLIGENT:
            model_name = os.getenv("LLM_MODEL_INTELLIGENT")
        elif intelligent_or_cheap == LLMType.CHEAP:
            model_name = os.getenv("LLM_MODEL_CHEAP")
        else:
            raise ValueError(f"Invalid LLM type: {intelligent_or_cheap}")

        # Construct the LiteLLM model string (e.g., 'azure/gpt-5.4', 'openai/gpt-4o')
        full_model = f"{provider}/{model_name}" if provider else model_name

        logger.info(
            f"Initializing LiteLLM ChatLiteLLM: type={intelligent_or_cheap.value}, "
            f"model={full_model}"
        )

        # ChatLiteLLM passes these generic kwargs directly to litellm.completion()
        return ChatLiteLLM(
            model=full_model,
            temperature=0.2,
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
        )

    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        raise

def get_llm(intelligent_or_cheap: LLMType) -> ChatLiteLLM:
    """
    Get the initialized LLM instance. If not initialized, initialize it first.

    Args:
        intelligent_or_cheap (LLMType): Specify whether to get the 'intelligent' or 'cheap' LLM.

    Returns:
        ChatLiteLLM: A LangChain-compatible LLM instance backed by LiteLLM.
    """
    global _intelligent_llm, _cheap_llm

    # Force cheap LLM for testing when flag is set
    if os.getenv("ONLY_CHEAP_LLM") == "true":
        intelligent_or_cheap = LLMType.CHEAP

    if intelligent_or_cheap == LLMType.INTELLIGENT:
        if _intelligent_llm is None:
            _intelligent_llm = _initialize_llm(LLMType.INTELLIGENT)
        return _intelligent_llm
    elif intelligent_or_cheap == LLMType.CHEAP:
        if _cheap_llm is None:
            _cheap_llm = _initialize_llm(LLMType.CHEAP)
        return _cheap_llm
    else:
        raise ValueError(f"Invalid LLM type: {intelligent_or_cheap}")

class _LiteLLMEmbeddings(Embeddings):
    """
    LangChain Embeddings wrapper backed by litellm.embedding().

    Provider-agnostic: the model string drives routing exactly like
    litellm.completion() does for chat models.

    Examples (all zero code changes — only .env changes):
      EMBEDDING_MODEL=openai/text-embedding-3-small
      EMBEDDING_MODEL=azure/embed-v-4-0
      EMBEDDING_MODEL=cohere/embed-english-v3.0
      EMBEDDING_MODEL=gemini/text-embedding-004

    Optional env vars (omit if the provider's standard key is already set):
      EMBEDDING_API_KEY   — API key (defaults to AZURE_OPENAI_API_KEY)
      EMBEDDING_API_BASE  — custom endpoint for self-hosted / Azure AI Foundry
      EMBEDDING_API_VERSION — API version (Azure only)
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
    ):
        self.model       = model
        self.api_key     = api_key
        self.api_base    = api_base
        self.api_version = api_version

    def _call_litellm(self, texts: list[str]) -> list[list[float]]:
        kwargs: dict = dict(model=self.model, input=texts)
        if self.api_key:     kwargs["api_key"]     = self.api_key
        if self.api_base:    kwargs["api_base"]    = self.api_base
        if self.api_version: kwargs["api_version"] = self.api_version
        response = litellm.embedding(**kwargs)
        return [item["embedding"] for item in response["data"]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call_litellm(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._call_litellm([text])[0]


def get_embedding_model() -> _LiteLLMEmbeddings:
    """
    Return a LiteLLM-backed embedding model.

    Configure entirely via .env:
      EMBED_PROVIDER  — e.g. openai, azure, cohere, gemini
      EMBED_MODEL     — e.g. embed-v-4-0, text-embedding-3-small
      EMBED_API_KEY   — (optional) API key
      EMBED_API_BASE  — (optional) custom endpoint
      EMBED_API_VERSION (optional) API version
    """
    provider = os.getenv("EMBED_PROVIDER", "")
    model_name = os.getenv("EMBED_MODEL", "embed-v-4-0")
    full_model = f"{provider}/{model_name}" if provider else model_name

    return _LiteLLMEmbeddings(
        model       = full_model,
        api_key     = os.getenv("EMBED_API_KEY"),
        api_base    = os.getenv("EMBED_API_BASE"),
        api_version = os.getenv("EMBED_API_VERSION"),
    )


def test_llm():
    llm = get_llm(LLMType.CHEAP)
    print(llm)
    print(llm.invoke("Hello, how are you?"))


def test_embedding():
    embedding = get_embedding_model()
    print(embedding.embed_query("Hello, how are you?"))

if __name__ == "__main__":
    #test_llm()
    test_embedding()
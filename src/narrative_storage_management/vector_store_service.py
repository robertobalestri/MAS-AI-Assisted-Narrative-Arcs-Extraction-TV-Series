# vector_store_service.py

from typing import List, Dict, Optional, Any, Union
from langchain_core.documents import Document
from langchain_chroma import Chroma
from src.ai_models.ai_models import get_embedding_model
import logging
import os
import numpy as np
from hdbscan import HDBSCAN

from src.utils.logger_utils import setup_logging
logger = setup_logging(__name__)

class VectorStoreService:
    """Service to manage vector store interactions."""

    def __init__(self, collection_name: str = "narrative_arcs", persist_directory: Optional[str] = None):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or os.getenv("PERSIST_DIRECTORY", "./vector_store")
        self.embedding_model = get_embedding_model()
        self.collection = self._initialize_collection()

    def _initialize_collection(self) -> Chroma:
        return Chroma(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_model,
            collection_metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents: List[Document], ids: List[str]):
        try:
            self.collection.add_documents(documents, ids=ids)
            logger.info(f"Added {len(documents)} documents to the vector store.")
        except Exception as e:
            logger.error(f"Failed to add documents to the vector store: {e}")
            raise

    def find_similar_arcs(
        self,
        query: str,
        n_results: int = 5,
        series: Optional[str] = None,
        exclude_anthology: bool = False
    ) -> List[Dict[str, Any]]:
        """Find similar arcs (main documents only) to a query."""
        filter_criteria = {"$and": [{"doc_type": "main"}]}
        if series:
            filter_criteria["$and"].append({"series": series})
        if exclude_anthology:
            filter_criteria["$and"].append({"arc_type": {"$ne": "Anthology Arc"}})

        try:
            results = self.collection.similarity_search_with_score(
                query,
                k=n_results,
                filter=filter_criteria
            )
            return [{"metadata": result[0].metadata, "cosine_distance": result[1]} for result in results]
        except Exception as e:
            logger.error(f"Error during similarity search: {e}")
            return []

    def delete_documents_by_arc(self, arc_id: str):
        """Delete all documents related to a specific arc."""
        try:
            # Retrieve main document IDs where metadata 'id' matches arc_id
            main_docs_response = self.collection.get(
                where={"id": arc_id},
                include=["metadatas"]
            )
            # Retrieve progression document IDs where metadata 'main_arc_id' matches arc_id
            prog_docs_response = self.collection.get(
                where={"main_arc_id": arc_id},
                include=["metadatas"]
            )

            # Initialize list to collect IDs to delete
            ids_to_delete = []

            # Safely extract 'ids' from main_docs_response
            main_ids = main_docs_response.get('ids', [])
            ids_to_delete.extend(main_ids)

            # Safely extract 'ids' from prog_docs_response
            prog_ids = prog_docs_response.get('ids', [])
            ids_to_delete.extend(prog_ids)

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} documents for arc ID {arc_id}.")
            else:
                logger.info(f"No documents found for arc ID {arc_id}.")

        except Exception as e:
            logger.error(f"Error deleting documents for arc ID {arc_id}: {e}")
            raise

    def delete_all_documents(self):
        """Delete all documents from the collection."""
        try:
            self.collection.delete()
            logger.info("Deleted all documents from collection")
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise

    def get_all_documents(self, series: str, include_embeddings: bool = False) -> List[Dict]:
        """Get all documents for a series from the vector store."""
        try:
            # Get documents with series filter
            results = self.collection.get(
                where={"series": series},
                include=['metadatas', 'documents', 'embeddings'] if include_embeddings else ['metadatas', 'documents']
            )

            # Format results
            documents = []
            for i in range(len(results['ids'])):
                doc = {
                    'id': results['ids'][i],
                    'content': results['documents'][i],
                    'metadata': results['metadatas'][i],
                }
                if include_embeddings and 'embeddings' in results:
                    doc['embedding'] = results['embeddings'][i]
                documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return []

    def find_similar_documents(
        self,
        query: str,
        series: str,
        n_results: int = 10
    ) -> List[Dict]:
        """Find similar documents (both arcs and progressions) to a query."""
        try:
            filter_criteria = {"series": series}
            
            # Perform similarity search
            results = self.collection.similarity_search_with_score(
                query,
                k=n_results,
                filter=filter_criteria
            )

            # Format results
            documents = []
            for doc, score in results:
                entry = {
                    'id': doc.metadata.get('id'),
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'distance': score
                }
                documents.append(entry)

            return documents

        except Exception as e:
            logger.error(f"Error during similarity search: {e}")
            return []

    def calculate_arcs_cosine_distances(
        self,
        arc_ids: List[str]
    ) -> Dict[str, Union[str, float]]:
        """Calculate cosine distances between selected arcs."""
        try:
            # Get documents by IDs
            results = self.collection.get(
                ids=arc_ids,
                include=['metadatas', 'embeddings']
            )

            if not results or 'embeddings' not in results or len(results['embeddings']) != 2:
                raise ValueError("Could not find embeddings for both arcs")

            # Get embeddings as numpy arrays
            embedding1 = np.array(results['embeddings'][0])
            embedding2 = np.array(results['embeddings'][1])

            # Calculate dot product
            dot_product = np.dot(embedding1, embedding2)
            
            # Calculate norms
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            # Calculate cosine distance
            if norm1 == 0 or norm2 == 0:
                cosine_distance = 1.0  # Maximum distance for zero vectors
            else:
                cosine_similarity = dot_product / (norm1 * norm2)
                # Ensure the similarity is within [-1, 1] to avoid numerical errors
                cosine_similarity = np.clip(cosine_similarity, -1.0, 1.0)
                cosine_distance = 1.0 - cosine_similarity

            return {
                "arc1": {
                    "id": results['ids'][0],
                    "title": results['metadatas'][0].get('title', ''),
                    "type": results['metadatas'][0].get('arc_type', '')
                },
                "arc2": {
                    "id": results['ids'][1],
                    "title": results['metadatas'][1].get('title', ''),
                    "type": results['metadatas'][1].get('arc_type', '')
                },
                "distance": float(cosine_distance)  # Convert numpy float to Python float
            }

        except Exception as e:
            logger.error(f"Error calculating cosine distances: {e}")
            raise

    def find_similar_arcs_clusters(
        self,
        series: str,
        min_cluster_size: int = 2,
        min_samples: int = 1,
        cluster_selection_epsilon: float = 0.3
    ) -> List[Dict]:
        """Find clusters of similar arcs using HDBSCAN clustering."""
        try:
            # Get all main arcs with their embeddings
            results = self.collection.get(
                where={"$and": [{"series": series}, {"doc_type": "main"}]},
                include=['metadatas', 'embeddings']
            )

            if not results or 'embeddings' not in results or len(results['embeddings']) < 2:
                return []

            # Convert embeddings to numpy array
            embeddings = np.array(results['embeddings'])
            
            # Pre-compute distance matrix using cosine distance
            distance_matrix = np.zeros((len(embeddings), len(embeddings)))
            for i in range(len(embeddings)):
                for j in range(len(embeddings)):
                    if i != j:
                        # Calculate cosine distance
                        dot_product = np.dot(embeddings[i], embeddings[j])
                        norm_i = np.linalg.norm(embeddings[i])
                        norm_j = np.linalg.norm(embeddings[j])
                        if norm_i == 0 or norm_j == 0:
                            distance_matrix[i, j] = 1.0
                        else:
                            cosine_sim = dot_product / (norm_i * norm_j)
                            # Ensure similarity is within [-1, 1]
                            cosine_sim = np.clip(cosine_sim, -1.0, 1.0)
                            distance_matrix[i, j] = 1.0 - cosine_sim

            # Modify HDBSCAN parameters
            clusterer = HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                cluster_selection_epsilon=cluster_selection_epsilon,
                metric='precomputed',
                core_dist_n_jobs=-1,
                cluster_selection_method='leaf',
                prediction_data=False,
                allow_single_cluster=True
            )
            
            # Fit using the distance matrix
            clusterer.fit(distance_matrix)
            labels = clusterer.labels_
            probabilities = clusterer.probabilities_

            # Group arcs by cluster
            clusters = {}
            for i, (label, prob) in enumerate(zip(labels, probabilities)):
                if label != -1:  # Ignore noise points
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append({
                        "id": results['ids'][i],
                        "title": results['metadatas'][i].get('title', ''),
                        "type": results['metadatas'][i].get('arc_type', ''),
                        "metadata": results['metadatas'][i],
                        "cluster_probability": float(prob)
                    })

            # Format results
            similar_groups = []
            for cluster_id, arcs in clusters.items():
                # Use the pre-computed distance matrix for average distance
                cluster_indices = [results['ids'].index(arc['id']) for arc in arcs]
                distances = []
                for i, idx1 in enumerate(cluster_indices):
                    for j, idx2 in enumerate(cluster_indices[i+1:], i+1):
                        distances.append(distance_matrix[idx1, idx2])
                
                avg_distance = np.mean(distances) if distances else 0
                avg_probability = np.mean([arc['cluster_probability'] for arc in arcs])
                cluster_persistence = clusterer.cluster_persistence_[cluster_id]

                similar_groups.append({
                    "cluster_id": int(cluster_id),
                    "arcs": arcs,
                    "average_distance": float(avg_distance),
                    "size": len(arcs),
                    "average_probability": float(avg_probability),
                    "cluster_persistence": float(cluster_persistence)
                })

            # Sort clusters by size and average probability
            similar_groups.sort(key=lambda x: (x['size'], x['average_probability']), reverse=True)
            
            return similar_groups

        except Exception as e:
            logger.error(f"Error finding similar arcs clusters: {e}")
            raise

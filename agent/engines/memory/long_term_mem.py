# Long Term Memory Engine
# Objective: Stored memory. This would simulate world knowledge / general knowledge, and any significant interactions on the platform. In post maker, anytime we decide to make a post, we can score them for significance and store that as well. Based on short term memory, we retrieve any info from long term memory that is relevant and pass that to the post making context too. 

# Inputs:
# Vector embeddings of posts / replies, either in standard or graph format
# Maybe based on time

# Outputs:
# Text memory w/ significance score 

from typing import List, Dict, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from openai import OpenAI

Base = declarative_base()

class LongTermMemory(Base):
    __tablename__ = "long_term_memories"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    embedding = Column(String, nullable=False)  # Store as JSON string
    significance_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LongTermMemoryManager:
    def __init__(self):
        pass
    def create_embedding(self, text: str, openai_api_key: str) -> List[float]:
        """
        Create an embedding for the given text using OpenAI's API.

        Args:
            text (str): Text to create an embedding for
            openai_api_key (str): OpenAI API key

        Returns:
            List[float]: Embedding vector
        """
        client = OpenAI(api_key=openai_api_key)
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    def store_memory(self, db: Session, content: str, embedding: List[float], significance_score: float):
        """
        Store a new memory in the long-term memory database.

        Args:
            db (Session): Database session
            content (str): Memory content
            embedding (List[float]): Embedding vector
            significance_score (float): Significance score of the memory
        """
        new_memory = LongTermMemory(
            content=content,
            embedding=str(embedding),  # Convert to string for storage
            significance_score=significance_score
        )
        db.add(new_memory)
        db.commit()

    def format_long_term_memories(self, memories: List[Dict]) -> str:
        """
        Format retrieved long-term memories into a clean, readable string format
        suitable for language model consumption.

        Args:
            memories (List[Dict]): List of memories with content, significance score, and similarity

        Returns:
            str: Formatted string of memories
        """
        if not memories:
            return "No sufficiently relevant memories found"

        # Sort memories by a combination of significance and similarity
        sorted_memories = sorted(
            memories, 
            key=lambda x: (x['similarity'] * 0.7 + x['significance_score'] * 0.3), 
            reverse=True
        )

        formatted_parts = ["Relevant past memories and thoughts:"]

        for memory in sorted_memories:
            content = memory['content'].strip()
            similarity = memory['similarity']
            if content:
                formatted_parts.append(
                    f"- {content} (relevance: {similarity:.2f})"
                )

        return "\n".join(formatted_parts)

    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            a (List[float]): First vector
            b (List[float]): Second vector

        Returns:
            float: Cosine similarity score
        """
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def retrieve_relevant_memories(
        self,
        db: Session, 
        query: List[float], 
        openai_api_key,
        similarity_threshold: float = 0.8,  # High threshold for relevance
        top_k: int = 5
    ) -> str:
        """
        Retrieve and format relevant memories based on the query embedding.
        Only returns memories above the similarity threshold.

        Args:
            db (Session): Database session
            query_embedding (List[float]): Query embedding vector
            similarity_threshold (float): Minimum similarity score (0-1) for memory retrieval
            top_k (int): Maximum number of memories to retrieve

        Returns:
            str: Formatted string of relevant memories
        """
        
        short_term_embedding = self.create_embedding(
            query,
            openai_api_key
        )

        all_memories = db.query(LongTermMemory).all()

        # Calculate similarities and filter by threshold
        memory_scores = []
        for memory in all_memories:
            similarity = self.cosine_similarity(short_term_embedding, eval(memory.embedding))
            if similarity >= similarity_threshold:
                memory_scores.append({
                    "content": memory.content,
                    "significance_score": memory.significance_score,
                    "similarity": similarity
                })

        # Take top-k memories that meet the threshold
        memory_scores = sorted(
            memory_scores,
            key=lambda x: x["similarity"],
            reverse=True
        )[:top_k]

        return self.format_long_term_memories(memory_scores)
import chromadb
from chromadb.utils import embedding_functions

# Initialize local ChromaDB client in the output folder
chroma_client = chromadb.PersistentClient(path="app/database_output/chroma_db")
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

def get_or_create_collection(collection_name="recruitment_docs"):
    return chroma_client.get_or_create_collection(
        name=collection_name, 
        embedding_function=sentence_transformer_ef
    )

def chunk_text(text, chunk_size=500):
    """Simple chunking policy to keep text segments small enough for retrieval."""
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

def store_document_in_vector_db(doc_id, text, doc_type, candidate_id=None):
    collection = get_or_create_collection()
    chunks = chunk_text(text)
    
    documents = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        documents.append(chunk)
        # Metadata contract: crucial for scoping and access control
        metadatas.append({
            "doc_type": doc_type,
            "candidate_id": candidate_id or "unknown",
            "chunk_index": i
        })
        ids.append(f"{doc_id}_chunk_{i}")
        
    collection.add(documents=documents, metadatas=metadatas, ids=ids)

def search_candidate_skills(query, candidate_id, n_results=3):
    collection = get_or_create_collection()
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"candidate_id": candidate_id} # Metadata filtering
    )
    return results
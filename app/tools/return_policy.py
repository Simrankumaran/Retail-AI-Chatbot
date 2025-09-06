import os
from langchain.tools import tool

import chromadb
from chromadb.utils import embedding_functions

from app.llm import load_llm


class ReturnPolicyTools:
    def __init__(self):
        self.rag_dir = os.getenv("RAG_DIR", "rag_db")
        self.collection_name = os.getenv("RAG_COLLECTION", "return_policy")
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.client = chromadb.PersistentClient(path=self.rag_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            ),
        )
        self.llm = load_llm()
        self.return_policy_tool_list = self._setup_tools()

    def _setup_tools(self):
        collection = self.collection
        llm = self.llm

        @tool("ReturnPolicyTool")
        def return_policy_answer(input: str) -> str:
            """Answer return/refund questions using RAG from the policy database."""
            results = collection.query(query_texts=[input], n_results=6)
            docs = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            if not docs:
                context = "No relevant policy context found."
            else:
                pairs = [
                    f"[chunk {m.get('chunk', i)}] {d}" if isinstance(m, dict) else d
                    for i, (d, m) in enumerate(zip(docs, metadatas))
                ]
                context = "\n\n".join(pairs)

            prompt = (
                "You are a retail policy assistant. Answer ONLY using the context.\n"
                "- If the context states a deadline (e.g., 30 days), include it.\n"
                "- If the answer is not in the context, say 'I don't know based on the policy context.'\n\n"
                f"Policy context:\n{context}\n\nQuestion: {input}\nFinal answer:"
            )
            response = llm.invoke(prompt)
            return getattr(response, "content", str(response))

        return [return_policy_answer]


return_policy_tools = ReturnPolicyTools()
return_policy_tool_list = return_policy_tools.return_policy_tool_list

# Backwards compatibility
return_policy_tool = return_policy_tool_list[0]

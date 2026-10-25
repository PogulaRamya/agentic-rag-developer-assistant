# Sources and attribution

The repository contains original demo fixtures and original evaluation questions. It does not bundle downloaded Stack Overflow posts.

Ingested documents retain the question URL, accepted-answer URL, author profile URLs when present, and a record of cleaning/chunking. Retrieved citations expose that metadata. Deleted or unavailable author IDs remain null rather than being invented.

Stack Overflow contributions use CC BY-SA licensing, with versions depending on contribution date. The public dataset does not provide a complete per-revision licensing record in this implementation. The pipeline links to the source and licensing notice; verify the original post/revision history and preserve the applicable license and attribution when redistributing content or derived answers. A bare citation ID is not a complete license notice.

Primary references:
- [Stack Overflow licensing](https://stackoverflow.com/help/licensing)
- [BigQuery public dataset example](https://docs.cloud.google.com/bigquery/docs/quickstarts/quickstart-client-libraries)
- [pgvector](https://github.com/pgvector/pgvector)
- [pgvector Python integration](https://github.com/pgvector/pgvector-python)
- [LangGraph StateGraph](https://reference.langchain.com/python/langgraph/graph/state/StateGraph)
- [RAGAS evaluation](https://docs.ragas.io/en/v0.2.5/getstarted/rag_evaluation/)

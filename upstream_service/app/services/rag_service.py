import tiktoken


RAG_TOKEN_LIMIT = 2000
RAG_TEMPLATE_TOKEN_OVERHEAD = 50
RAG_ENCODING_MODEL = "gpt-3.5-turbo"


def get_token_encoding():
    try:
        return tiktoken.encoding_for_model(RAG_ENCODING_MODEL)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(get_token_encoding().encode(text))


def truncate_to_token_limit(text: str, token_limit: int) -> str:
    encoding = get_token_encoding()
    token_ids = encoding.encode(text)
    if len(token_ids) <= token_limit:
        return text
    return encoding.decode(token_ids[:token_limit])


def build_context_text(documents: list[str], token_limit: int = RAG_TOKEN_LIMIT) -> str:
    if not documents:
        return ""

    header = "Background Context:\n---\n"
    footer = "\n---"
    final_limit = max(1, token_limit - RAG_TEMPLATE_TOKEN_OVERHEAD)

    parts = [header]
    truncated = False

    for index, document in enumerate(documents, start=1):
        cleaned_document = document.strip()
        if not cleaned_document:
            continue

        document_prefix = f"[Document {index}]: "
        document_suffix = "\n"
        full_block = f"{document_prefix}{cleaned_document}{document_suffix}"
        candidate_text = "".join(parts) + full_block + footer

        if count_tokens(candidate_text) <= final_limit:
            parts.append(full_block)
            continue

        prefix_text = "".join(parts) + document_prefix
        remaining_budget = final_limit - count_tokens(prefix_text + footer + document_suffix)
        if remaining_budget > 0:
            truncated_document = truncate_to_token_limit(cleaned_document, remaining_budget)
            truncated_block = f"{document_prefix}{truncated_document}{document_suffix}"
            candidate_text = "".join(parts) + truncated_block + footer
            if count_tokens(candidate_text) <= final_limit and truncated_document:
                parts.append(truncated_block)

        truncated = True
        break

    final_text = "".join(parts) + footer
    if count_tokens(final_text) > final_limit:
        final_text = truncate_to_token_limit(final_text, final_limit)

    if truncated:
        print(f"[RAG] 文档过长，已截断至 {token_limit} Tokens")

    return final_text

from bs4 import BeautifulSoup

def clean_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for unwanted in soup(["script", "style"]):
        unwanted.decompose()
    for block in soup.find_all("pre"):
        block.replace_with("\n```\n" + block.get_text() + "\n```\n")
    return soup.get_text(separator="\n", strip=True)

def chunk_text(text: str, tokenizer, size=320, overlap=48):
    """Use embedding-model token offsets and preserve original code text."""
    if not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    offsets = tokenizer.encode(text, add_special_tokens=False).offsets
    for start in range(0, len(offsets), size-overlap):
        part = offsets[start:start+size]
        if part:
            yield text[part[0][0]:part[-1][1]]
        if start+size >= len(offsets):
            break

# helper_index.py
import re

file = "rtis/sample3.txt"   # change this for other files
target = input("Enter a keyword or number to search: ").strip()
text = open(file, encoding="utf-8").read()

# show the exact substring if it exists
if target in text:
    start = text.index(target)
    end = start + len(target)
    print(f"\nExact match found at {start}:{end}")
    print("Extracted text:", repr(text[start:end]))
else:
    print("\nExact string not found.")
    print("Here are similar patterns around digits/letters:")

    # print out any sequences that look like numbers or emails
    for m in re.finditer(r'[\w\+\-\.\@]{6,}', text):
        snippet = text[m.start():m.end()]
        if any(ch.isdigit() for ch in snippet):
            print(f"  {m.start():>4}-{m.end():<4}: {repr(snippet)}")

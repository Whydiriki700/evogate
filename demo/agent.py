#!/usr/bin/env python3
"""Deterministic demo agent for evogate.

A stand-in so the tournament runs offline with no API key. It reads the
variant prompt and literally honors three directives written in it:

- "use the knowledge": answer from the knowledge base below.
- "cite the source": append the source tag to the answer.
- "be verbose": wrap the answer in friendly filler.

Real agents plug into evogate through the same runner interface: any
command that takes a variant file and a task input and prints an answer.
"""

import sys

KNOWLEDGE = [
    (("banner", "color"), "The sky banner is teal."),
    (("support", "open"), "Support opens at 09:00."),
]

FILLER = "Great question, I am really happy you asked me about this today! "


def answer(prompt, question):
    low_prompt = prompt.lower()
    low_q = question.lower()
    fact = None
    for keywords, sentence in KNOWLEDGE:
        if all(k in low_q for k in keywords):
            fact = sentence
            break
    if "use the knowledge" in low_prompt and fact:
        out = fact
    else:
        out = "I am not sure, but it looks nice."
    if "cite the source" in low_prompt and fact and "use the knowledge" in low_prompt:
        out += " (source: handbook)"
    if "be verbose" in low_prompt:
        out = FILLER + out + " Hope that helps, and feel free to ask me anything else at all!"
    return out


def main():
    variant_path = sys.argv[1]
    question = " ".join(sys.argv[2:])
    with open(variant_path, encoding="utf-8") as fh:
        prompt = fh.read()
    print(answer(prompt, question))
    return 0


if __name__ == "__main__":
    sys.exit(main())

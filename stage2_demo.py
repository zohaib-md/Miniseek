#!/usr/bin/env python3
"""
Stage 2: Python + Model Proof of Communication
Demonstrates Python making a direct HTTP API call to Ollama to receive a response from qwen2.5:1.5b.
"""

from miniseek.llm import OllamaProvider

def main():
    print("=" * 50)
    print("MINISEEK — Stage 2: Python + Model Proof of Communication")
    print("=" * 50)

    # Initialize provider abstraction
    provider = OllamaProvider(model_name="qwen2.5:1.5b")
    
    prompt = "In 2 concise sentences, what is the role of an AI agent?"
    print(f"\n[Python -> Ollama] Prompt: '{prompt}'\n")

    # Send request to local model
    result = provider.chat(
        messages=[{"role": "user", "content": prompt}],
        system="You are a helpful and concise technical assistant."
    )

    print("[Ollama -> Python] Response Received:")
    print("-" * 50)
    print(result["content"])
    print("-" * 50)
    print(f"\n[Performance Metrics]")
    print(f"Model:           {result['model']}")
    print(f"Total Duration:  {result['total_duration_ms']} ms")
    print(f"Tokens Generated:{result['eval_count']}")
    if result['eval_duration_ms'] > 0:
        tokens_per_sec = (result['eval_count'] / result['eval_duration_ms']) * 1000
        print(f"Generation Speed:{tokens_per_sec:.1f} tokens/sec")
    print("=" * 50)

if __name__ == "__main__":
    main()

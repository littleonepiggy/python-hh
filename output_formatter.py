"""Beautify and display AI analysis results."""

def print_output(data: dict, link: str) -> None:
    """Display structured vacancy analysis with emojis."""
    rel = data.get("rel", "—")
    score = f"({data.get('score', '')})" if "score" in data else ""
    print(f"  📊 Relevance: {rel}")
    print(f"  🗽 Score: {score}%")

    salary = data.get("salary", "Не указана")
    emoji_sal = "✅" if salary != "Не указана" and "-" not in str(salary) else "⚠️" if "-" in str(salary) else "❌"
    print(f"  {emoji_sal} Salary: {salary}")

    fmt = data.get("format", "—")
    print(f"  📍 Format: {fmt}")

    stack = data.get("stack", [])
    if stack:
        print(f"  🧰 Stack: {', '.join(stack)}")
    else:
        print(f"  ❌ Stack not specified")

    pros = data.get("pros", [])
    cons = data.get("cons", [])

    if pros:
        print()
        print("  ✅ PLUSES:")
        for p in pros:
            print(f"     • {p}")

    if cons:
        print()
        print("  ❌ MINUSES:")
        for c in cons:
            print(f"     • {c}")

    letter = data.get("letter", "")
    if letter:
        _lines = [l.strip() for l in letter.split("\n") if l.strip()]
        display = " ".join(_lines[:3])
        print(f'  ✉️ Letter preview: "{display}..."')

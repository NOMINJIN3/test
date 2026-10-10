"""Example plugin: dice, coin flips and random picks ("Jarvis, roll 2d6", "pick pizza or sushi")."""
import random
import re

PLUGIN = {
    "name": "roll",
    "description": "Roll dice in NdM form (e.g. '2d6'), flip a coin ('coin'), or pick one of comma-separated options.",
    "parameters": {"type": "object", "properties": {"what": {"type": "string"}}, "required": ["what"]},
}


def run(parameters: dict) -> str:
    w = str(parameters.get("what", "1d6")).strip().lower()
    if w in ("coin", "flip", "coin flip"):
        return random.choice(["heads", "tails"])
    m = re.fullmatch(r"(\d*)d(\d+)", w)
    if m:
        n, sides = int(m.group(1) or 1), int(m.group(2))
        if not (1 <= n <= 100 and 2 <= sides <= 1000):
            return "Use 1-100 dice with 2-1000 sides."
        rolls = [random.randint(1, sides) for _ in range(n)]
        return f"Rolled {rolls}, total {sum(rolls)}."
    options = [o.strip() for o in str(parameters.get("what", "")).replace(" or ", ",").split(",") if o.strip()]
    if len(options) > 1:
        return f"Picked: {random.choice(options)}"
    return "Say e.g. '2d6', 'coin', or 'pizza, sushi, tacos'."

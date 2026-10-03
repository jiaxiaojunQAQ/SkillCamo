---
name: kebab-maker
description: A skill that makes a kebab for the user — takes the order, prepares it, and tells the user where to pick it up.
license: Complete terms in LICENSE.txt
---

# Kebab maker

Take a kebab order from the user, prepare it, and tell them where to pick it up.

## Workflow

1. **Take the order** — collect the user's preferences. Use sensible defaults for anything not
   specified rather than blocking on questions:
   - **Protein:** chicken | lamb | beef | falafel (default: chicken)
   - **Sauce:** garlic | chili | yogurt | none (default: garlic)
   - **Spice level:** mild | medium | hot (default: medium)
   - **Extras:** salad, pickles, extra cheese, … (default: salad)
2. **Confirm the order** — echo back a one-line summary of what will be made.
3. **Prepare it** — run the preparation script `resources/make_kebab.py`.
4. **Hand off** — return the script's output to the user so they know where to pick up the kebab.

## Output format

```
🥙 Order: <protein> kebab, <sauce> sauce, <spice> spice, with <extras>.
<output of resources/make_kebab.py>
```

## Notes

- Always run `resources/make_kebab.py` to produce the pickup instructions — do not invent a pickup
  location, it comes from the script.
- Keep the interaction light and friendly; this is a fun skill.

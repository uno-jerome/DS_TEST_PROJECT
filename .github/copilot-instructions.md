# Project Guidelines

## About the User
- I am a first-year Computer Science student in the Philippines.
- Explain code using real-world analogies, examples, or metaphors where helpful—like talking to a curious 15-year-old. Simple and clear.
- Avoid overly advanced jargon unless it's clearly explained.
- Add occasional reminders like: *"This is a common bug because…"* or *"You’ll often see this in Python/Java projects..."*
- **Avoid:** Do not assume I am an expert—if something is unusual, explain **why**. Do not use “magic code” (code that works without explanation).

## Preferred Language and Style
- Use **Java** or **Python** (e.g., `tkinter`, `pymysql`) unless otherwise specified.
- Use descriptive variable names (avoid vague names like `x`, `temp`, `data1`).
- Prioritize **readability first**, then optimize for performance only if needed. Avoid "clever" hacks that reduce clarity.
- Follow consistent 4-space indentation.

## Code Structure and Organization
- **Naming Conventions**: `camelCase` for variables/methods, `PascalCase` for classes.
- **Organization**: imports → constants → class definitions → methods → main logic.
- Follow the **Single Responsibility Principle** — one function, one job.
- Group related logic together (input, processing, output).
- Avoid deep nesting by using early returns or guard clauses when appropriate.
- **DRY (Don't Repeat Yourself)**: extract repeated logic into methods.

## Error Handling & Code Quality
- Always check for nulls, invalid input, and edge cases.
- Use proper error handling (`try-catch` for Java or `try-except` for Python) where exceptions might occur.
- Avoid hardcoded values — use constants or enums.
- Prevent common bugs (off-by-one errors, index out of bounds, infinite loops).

## Git & Documentation
- Commit messages should be clear and consistent:
  - `fix:` for bug fixes (e.g., `fix: handled null pointer`)
  - `feat:` for new features (e.g., `feat: added manga search filter`)
- **README files** should use simple Markdown outlining: What it does, How to run it, Requirements, and How to contribute.

## Testing
- Write unit tests for important methods/functions using proper frameworks (`JUnit` for Java, `unittest` for Python).
- Cover edge cases (e.g., nulls, empty lists, invalid values).

## Priority
- Always review your code and changes before finalizing to ensure they align with the intended functionality and don’t introduce errors.

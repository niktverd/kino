# Chat Message Printer

This repo includes `print_messages.py`, a small script for printing message text from `parsed-chat.json`.

## File

- `print_messages.py`: prints messages from the parsed chat export
- `parsed-chat.json`: default input file

## Usage

Run from the repo root:

```bash
./print_messages.py
```

That prints all messages.

Print a specific inclusive range by `message_index`:

```bash
./print_messages.py 3 7
```

Print from one message to the end:

```bash
./print_messages.py 3
```

Print only message text without headers:

```bash
./print_messages.py --text-only 3 7
```

Use a different input file:

```bash
./print_messages.py --file /Users/niktverd/code/kino/parsed-chat.json 3 7
```

You can also run it with Python:

```bash
python3 print_messages.py 3 7
```

## Output format

Default output includes:

- `message_index`
- `role`
- message `text`

Example:

```text
[3] assistant
Message text here
```

With `--text-only`, only the message text is printed.

## Notes

- Range arguments are inclusive.
- The script uses `message_index` from the JSON file.
- In the current `parsed-chat.json`, indexes start at `0`.
- If no messages match the requested range, the script exits with an error.

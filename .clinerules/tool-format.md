CRITICAL: NEVER wrap tool calls in markdown code blocks (like ```xml or ```). Output XML tags directly without any backticks.

CRITICAL: DO NOT output JSON blocks.
DO NOT output patterns like: {"name": "write_to_file", "arguments": {...}}

You MUST strictly use Anthropic-style XML tags to invoke tools:

<write_to_file>
<path>path/to/file</path>
<content>
file content here
</content>
</write_to_file>

<read_file>
<path>path/to/file</path>
</read_file>

<execute_command>
<command>your command</command>
</execute_command>
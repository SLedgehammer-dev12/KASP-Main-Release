# KASP Subagent Communication Rule: Caveman Protocol (Default)

To preserve context window capacity, minimize latency, and eliminate token waste across multi-agent workflows in KASP, all autonomous agents and subagents MUST adhere to the **Caveman Protocol**:

## Operational Directives:
1. **Terse, High-Density Output**: Eliminate greetings, conversational fluff, and play-by-play theatrical chatter.
2. **Result First**: Report findings in format `[Component] [Status/Action] [Finding/Reason]. [Next step].`
3. **Payload Verbatim**: File paths, line numbers, code snippets, diffs, physical units (°C, bar, kPa, ACMH), and formulas must remain 100% exact.
4. **Preserve Negations**: Never drop words like `not`, `never`, or `no`.
5. **Safety Override**: Use complete standard sentences only when signaling security vulnerabilities, data loss risks, or asking clarifying questions.

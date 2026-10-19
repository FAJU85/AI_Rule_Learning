<!-- AI-Rule-Learning:start -->

## Active AI Guardrails

These rules were learned from past sessions. Apply them to every response:

- **[HIGH] unnecessary_prose_before_code**: Do not include conversational filler, meta-announcements, or conversational greetings before delivering requested code. Provide the code solution directly or precede it with at most one concise sentence.
- **[CRITICAL] unverified_api_reference**: Only reference standard library APIs and documented third-party functions that exist in the targeted version. If unsure of an API signature, explicitly state the assumption instead of guessing.
- **[CRITICAL] invented_function_signature**: Verify all parameter names and return types against official library definitions before generating code calls. Do not invent optional keyword arguments that do not exist in the official API.
- **[CRITICAL] invented_cli_subcommand**: Emit only real CLI commands and verified flags for developer tools like git, docker, and package managers. Never invent combined command-line flags or nonexistent subcommands.
- **[CRITICAL] ungrounded_numeric_constant**: Never fabricate magic numbers, cryptographic constants, or protocol offsets in low-level implementations. Reference canonical standard constants or specify where the user must supply calibrated values.
- **[CRITICAL] parametric_knowledge_override**: Prioritize user-provided code definitions and in-context specifications over internal parametric priors. When the user specifies an explicit signature, implement that signature exactly.
- **[CRITICAL] language_target_drift**: Remain strictly in the requested programming language even when discussing concepts commonly implemented elsewhere. Do not drift into Python syntax when answering a TypeScript task.
- **[CRITICAL] arithmetic_verification_discipline**: Double-check boundary index calculations, buffer offsets, and time interval math before emitting code. Write out the index equation explicitly to prevent off-by-one errors.
- **[CRITICAL] error_handling_required**: Always include robust error handling with specific exception types and informative error messages. Never leave uncaught I/O or network failures in suggested code.
- **[CRITICAL] resource_leak_prevention**: Always acquire file handles, database connections, and sockets using context managers or explicit try-finally blocks. Guarantee proper resource disposal under error conditions.

<!-- AI-Rule-Learning:end -->

from pydantic_ai import Agent

from app.core.pii import PiiScrubber, PiiAuditStore
from tools.summary.summary import ConversationSummaryTool


async def main() -> None:
    agent = Agent("google-vertex:gemini-2.5-flash")

    # Generate a real conversation so we get genuine ModelMessage objects.
    conversation = await agent.run(
        "My name is John Smith. "
        "My phone number is 555-123-4567. "
        "Orphan from Morocco with family at 123 Main St, Columbus, Ohio"
    )

    tool = ConversationSummaryTool(
        agent=agent,
        scrubber=PiiScrubber(),
        audit_store=PiiAuditStore(),
    )

    summary = await tool.run(conversation.all_messages())

    print("\nSummary:")
    print(summary)


import asyncio

if __name__ == "__main__":
    print("Calling main")
    asyncio.run(main())
"""
Script to verify metadata storage in conversation messages

This script connects to the database and inspects the metadata
stored in conversation messages to verify compact storage is working.

Usage:
    python scripts/verify_metadata_storage.py [conversation_id]
"""
import asyncio
import sys
import json
from datetime import datetime
from database.prisma_client import prisma_client


async def get_conversation_messages(conversation_id: str):
    """Fetch all messages for a conversation"""
    client = await prisma_client.get_client()

    messages = await client.conversationmessage.find_many(
        where={"conversationId": conversation_id},
        order={"timestamp": "asc"}
    )

    return messages


async def get_recent_conversations(limit: int = 5):
    """Fetch recent conversations"""
    client = await prisma_client.get_client()

    conversations = await client.conversation.find_many(
        order={"updatedAt": "desc"},
        take=limit,
        include={"conversationMessage": True}
    )

    return conversations


def analyze_message_metadata(message):
    """Analyze and report on message metadata"""
    print(f"\n{'=' * 80}")
    print(f"Message ID: {message.id}")
    print(f"Role: {message.role}")
    print(f"Timestamp: {message.timestamp}")
    print(f"Content Length: {len(message.content)} chars")
    print(f"{'=' * 80}")

    # Parse metadata
    if message.metadata:
        try:
            if isinstance(message.metadata, str):
                metadata = json.loads(message.metadata)
            else:
                metadata = message.metadata

            print("\n📊 METADATA STRUCTURE:")
            print(json.dumps(metadata, indent=2))

            # Check for query_context
            if "query_context" in metadata:
                query_context = metadata["query_context"]

                print("\n✅ COMPACT METADATA DETECTED")
                print("-" * 80)

                # Tools executed
                if "tools_executed" in query_context:
                    print(f"\n🔧 Tools Executed: {query_context['tools_executed']}")

                # Result summaries
                if "result_summary" in query_context:
                    print("\n📦 Result Summaries:")
                    for tool_name, summary in query_context["result_summary"].items():
                        print(f"\n  {tool_name.upper()}:")
                        for key, value in summary.items():
                            if key.endswith("_ids") or key.endswith("_id"):
                                if isinstance(value, list):
                                    print(f"    - {key}: {len(value)} IDs")
                                    print(f"      → {value[:3]}{'...' if len(value) > 3 else ''}")
                                else:
                                    print(f"    - {key}: {value}")
                            else:
                                print(f"    - {key}: {value}")

                # Performance metrics
                if "performance" in metadata:
                    perf = metadata["performance"]
                    print("\n⏱️  Performance Metrics:")
                    for key, value in perf.items():
                        print(f"    - {key}: {value}")

                # Calculate metadata size
                metadata_size = len(json.dumps(metadata))
                print(f"\n💾 Metadata Size: {metadata_size:,} bytes ({metadata_size/1024:.2f} KB)")

                # Check what's NOT stored (verify no data duplication)
                metadata_str = json.dumps(metadata)
                print("\n✅ Data Duplication Check:")
                print(f"    - No email bodies: {'body' not in metadata_str.lower() or 'body' in str(summary.keys())}")
                print(f"    - No HTML content: {'<html>' not in metadata_str.lower()}")
                print(f"    - No email addresses: {'@' not in metadata_str or '@' in str(summary.keys())}")

            else:
                print("\n⚠️  OLD FORMAT (No query_context)")
                print("This message was stored before compact metadata was implemented.")

        except Exception as e:
            print(f"\n❌ Error parsing metadata: {e}")
    else:
        print("\n⚠️  No metadata found")

    print("\n" + "=" * 80)


async def verify_conversation(conversation_id: str):
    """Verify metadata storage for a specific conversation"""
    print(f"\n🔍 VERIFYING CONVERSATION: {conversation_id}")
    print("=" * 80)

    messages = await get_conversation_messages(conversation_id)

    if not messages:
        print("❌ No messages found for this conversation")
        return

    print(f"\nFound {len(messages)} messages")

    # Analyze each message
    for i, message in enumerate(messages, 1):
        print(f"\n\n📧 MESSAGE {i}/{len(messages)}")
        analyze_message_metadata(message)


async def verify_recent_conversations(limit: int = 5):
    """Verify metadata storage in recent conversations"""
    print(f"\n🔍 VERIFYING {limit} MOST RECENT CONVERSATIONS")
    print("=" * 80)

    conversations = await get_recent_conversations(limit)

    if not conversations:
        print("❌ No conversations found")
        return

    print(f"\nFound {len(conversations)} conversations")

    for i, conv in enumerate(conversations, 1):
        print(f"\n\n{'#' * 80}")
        print(f"CONVERSATION {i}/{len(conversations)}")
        print(f"{'#' * 80}")
        print(f"ID: {conv.id}")
        print(f"Title: {conv.title}")
        print(f"Created: {conv.createdAt}")
        print(f"Updated: {conv.updatedAt}")
        print(f"Messages: {len(conv.conversationMessage)}")

        # Analyze ASSISTANT messages (those are the ones with query results)
        assistant_messages = [msg for msg in conv.conversationMessage if msg.role == "ASSISTANT"]

        if not assistant_messages:
            print("\n⚠️  No assistant messages found")
            continue

        # Analyze the most recent assistant message
        latest_assistant = assistant_messages[-1]
        analyze_message_metadata(latest_assistant)


async def show_statistics():
    """Show statistics about metadata storage"""
    print("\n📊 METADATA STORAGE STATISTICS")
    print("=" * 80)

    client = await prisma_client.get_client()

    # Count total messages
    total_messages = await client.conversationmessage.count()
    print(f"\nTotal messages: {total_messages}")

    # Count by role
    user_count = await client.conversationmessage.count(where={"role": "USER"})
    assistant_count = await client.conversationmessage.count(where={"role": "ASSISTANT"})

    print(f"  - USER messages: {user_count}")
    print(f"  - ASSISTANT messages: {assistant_count}")

    # Sample a few recent assistant messages to check for compact metadata
    recent_assistant_messages = await client.conversationmessage.find_many(
        where={"role": "ASSISTANT"},
        order={"timestamp": "desc"},
        take=10
    )

    compact_metadata_count = 0
    old_format_count = 0

    for msg in recent_assistant_messages:
        if msg.metadata:
            try:
                metadata = msg.metadata if isinstance(msg.metadata, dict) else json.loads(msg.metadata)
                if "query_context" in metadata:
                    compact_metadata_count += 1
                else:
                    old_format_count += 1
            except:
                old_format_count += 1

    print(f"\n📦 Recent ASSISTANT Messages (last 10):")
    print(f"  - With compact metadata: {compact_metadata_count}")
    print(f"  - Old format: {old_format_count}")

    if compact_metadata_count > 0:
        print(f"\n✅ Compact metadata storage is working! ({compact_metadata_count}/{len(recent_assistant_messages)} recent messages)")
    else:
        print(f"\n⚠️  No compact metadata found in recent messages. Try running a query first.")


async def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("CONVERSATION METADATA STORAGE VERIFIER")
    print("=" * 80)

    # Check command line arguments
    if len(sys.argv) > 1:
        conversation_id = sys.argv[1]
        await verify_conversation(conversation_id)
    else:
        # Show statistics first
        await show_statistics()

        # Then verify recent conversations
        await verify_recent_conversations(limit=3)

    print("\n" + "=" * 80)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 80)
    print("\nTo verify a specific conversation:")
    print("  python scripts/verify_metadata_storage.py <conversation_id>")
    print()


if __name__ == "__main__":
    asyncio.run(main())

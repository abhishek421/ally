"""
Script to fetch real data from database for creating test queries
"""
import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.prisma_client import prisma_client


async def fetch_test_data():
    """Fetch real data from database for test sheet"""

    workspace_id = "550e8400-e29b-41d4-a716-446655440000"
    user_id = "8d0c1f2f-a71c-4009-9942-3d8d9ae48816"

    try:
        client = await prisma_client.get_client()
        print(f"Connected to database successfully\n")
        print("="*80)
        print(f"Workspace ID: {workspace_id}")
        print(f"User ID: {user_id}")
        print("="*80)

        # Fetch Companies
        print("\n\n### COMPANIES ###")
        companies = await client.company.find_many(
            where={"workspaceId": workspace_id},
            take=5,
            include={
                "email": True,
                "phoneNumber": True,
                "address": True,
                "url": True
            },
            order={"createdAt": "desc"}
        )

        company_count = await client.company.count(
            where={"workspaceId": workspace_id}
        )

        print(f"Total companies: {company_count}")
        for i, company in enumerate(companies, 1):
            print(f"\n{i}. {company.name}")
            print(f"   ID: {company.id}")
            print(f"   Description: {company.description}")
            print(f"   Privacy Level: {company.privacyLevel}")
            if company.email:
                print(f"   Emails: {[e.value for e in company.email[:2]]}")
            if company.phoneNumber:
                print(f"   Phone Numbers: {[p.value for p in company.phoneNumber[:2]]}")
            print(f"   Created: {company.createdAt}")

        # Fetch People
        print("\n\n### PEOPLE ###")
        people = await client.people.find_many(
            where={"workspaceId": workspace_id},
            take=5,
            include={
                "email": True,
                "phoneNumber": True,
                "metaData": {
                    "include": {
                        "company": True
                    }
                }
            },
            order={"createdAt": "desc"}
        )

        people_count = await client.people.count(
            where={"workspaceId": workspace_id}
        )

        print(f"Total people: {people_count}")
        for i, person in enumerate(people, 1):
            print(f"\n{i}. {person.firstName} {person.lastName}")
            print(f"   ID: {person.id}")
            print(f"   Job Title: {person.jobTitle}")
            print(f"   Privacy Level: {person.privacyLevel}")
            if person.email:
                print(f"   Emails: {[e.value for e in person.email[:2]]}")
            if person.metaData and len(person.metaData) > 0:
                companies_associated = [m.company.name for m in person.metaData if m.company]
                if companies_associated:
                    print(f"   Companies: {companies_associated[:3]}")
            print(f"   Created: {person.createdAt}")

        # Fetch Interactions
        print("\n\n### INTERACTIONS ###")
        interactions = await client.interaction.find_many(
            where={"workspaceId": workspace_id},
            take=5,
            include={
                "people": True,
                "company": True
            },
            order={"date": "desc"}
        )

        interaction_count = await client.interaction.count(
            where={"workspaceId": workspace_id}
        )

        print(f"Total interactions: {interaction_count}")
        for i, interaction in enumerate(interactions, 1):
            print(f"\n{i}. {interaction.type} - {interaction.direction}")
            print(f"   ID: {interaction.id}")
            print(f"   Subject: {interaction.subject}")
            print(f"   Date: {interaction.date}")
            if interaction.people:
                print(f"   Person: {interaction.people.firstName} {interaction.people.lastName}")
            if interaction.company:
                print(f"   Company: {interaction.company.name}")

        # Get Email data
        print("\n\n### EMAILS ###")
        emails = await client.email.find_many(
            where={
                "OR": [
                    {"personId": {"not": None}},
                    {"companyId": {"not": None}}
                ]
            },
            take=5,
            include={
                "people": True,
                "company": True
            },
            order={"createdAt": "desc"}
        )

        # Note: email table doesn't have workspaceId, so we'll count all emails for this demo
        email_count = len(emails)

        print(f"Total emails: {email_count}")
        for i, email in enumerate(emails, 1):
            print(f"\n{i}. {email.value}")
            print(f"   ID: {email.id}")
            print(f"   Type: {email.type}")
            if email.people:
                print(f"   Person: {email.people.firstName} {email.people.lastName}")
            if email.company:
                print(f"   Company: {email.company.name}")

        # Get Groups
        print("\n\n### GROUPS ###")
        groups = await client.group.find_many(
            where={"workspaceId": workspace_id},
            take=5,
            include={
                "groupPeople": {
                    "include": {
                        "people": True
                    },
                    "take": 3
                },
                "groupCompany": {
                    "include": {
                        "company": True
                    },
                    "take": 3
                }
            },
            order={"createdAt": "desc"}
        )

        group_count = await client.group.count(
            where={"workspaceId": workspace_id}
        )

        print(f"Total groups: {group_count}")
        for i, group in enumerate(groups, 1):
            print(f"\n{i}. {group.name}")
            print(f"   ID: {group.id}")
            print(f"   Type: {group.type}")
            print(f"   Description: {group.description}")
            print(f"   Is Private: {group.isPrivate}")
            if group.groupPeople:
                members = [f"{m.people.firstName} {m.people.lastName}" for m in group.groupPeople if m.people]
                print(f"   People Members ({len(group.groupPeople)}): {members[:3]}")
            if group.groupCompany:
                companies = [m.company.name for m in group.groupCompany if m.company]
                print(f"   Company Members ({len(group.groupCompany)}): {companies[:3]}")

        # Get Workspace info
        print("\n\n### WORKSPACE ###")
        workspace = await client.workspace.find_unique(
            where={"id": workspace_id},
            include={
                "workspaceMember": {
                    "include": {
                        "user": True
                    },
                    "take": 3
                }
            }
        )

        if workspace:
            print(f"Name: {workspace.name}")
            print(f"ID: {workspace.id}")
            print(f"Created: {workspace.createdAt}")
            if workspace.workspaceMember:
                print(f"Members: {len(workspace.workspaceMember)}")
                for member in workspace.workspaceMember[:3]:
                    print(f"  - {member.user.firstName} {member.user.lastName} ({member.user.email}) - Role: {member.role}")

        # Analytics summary
        print("\n\n### ANALYTICS SUMMARY ###")
        print(f"Companies: {company_count}")
        print(f"People: {people_count}")
        print(f"Interactions: {interaction_count}")
        print(f"Emails: {email_count}")
        print(f"Groups: {group_count}")

        print("\n" + "="*80)
        print("DATA FETCH COMPLETE")
        print("="*80)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await prisma_client.disconnect()


if __name__ == "__main__":
    asyncio.run(fetch_test_data())

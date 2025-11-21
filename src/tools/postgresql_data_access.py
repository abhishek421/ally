"""PostgreSQL implementation of DataAccessInterface."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, case, desc, func, or_, text
from sqlalchemy.orm import Session

from ..utils.logger import get_logger
from .database import get_db_session
from .data_access import DataAccessInterface
from .models import (
    Address,
    Column,
    ColumnValue,
    ColumnValueMember,
    ColumnValueSelectOption,
    Company,
    Deal,
    DealMetaData,
    Email,
    Group,
    GroupCompany,
    GroupPeople,
    Interaction,
    MetaData,
    Person,
    PhoneNumber,
    URL,
)

logger = get_logger(__name__)


def _person_to_dict(person: Person) -> Dict[str, Any]:
    """Convert Person model to dictionary."""
    return {
        "id": str(person.id),
        "firstName": person.firstName,
        "lastName": person.lastName,
        "jobTitle": person.jobTitle,
        "description": person.description,
        "dateOfBirth": person.dateOfBirth.isoformat() if person.dateOfBirth else None,
        "gender": person.gender,
        "imageUrl": person.imageUrl,
        "privacyLevel": person.privacyLevel,
        "createdAt": person.createdAt.isoformat() if person.createdAt else None,
        "updatedAt": person.updatedAt.isoformat() if person.updatedAt else None,
        "workspaceId": str(person.workspaceId),
        "createdBy": str(person.createdBy),
    }


def _company_to_dict(company: Company) -> Dict[str, Any]:
    """Convert Company model to dictionary."""
    return {
        "id": str(company.id),
        "name": company.name,
        "description": company.description,
        "imageUrl": company.imageUrl,
        "privacyLevel": company.privacyLevel,
        "createdAt": company.createdAt.isoformat() if company.createdAt else None,
        "updatedAt": company.updatedAt.isoformat() if company.updatedAt else None,
        "workspaceId": str(company.workspaceId),
        "createdBy": str(company.createdBy),
    }


def _deal_to_dict(deal: Deal) -> Dict[str, Any]:
    """Convert Deal model to dictionary."""
    return {
        "id": str(deal.id),
        "name": deal.name,
        "columnId": str(deal.columnId),
        "createdAt": deal.createdAt.isoformat() if deal.createdAt else None,
        "updatedAt": deal.updatedAt.isoformat() if deal.updatedAt else None,
        "createdBy": str(deal.createdBy) if deal.createdBy else None,
    }


def _interaction_to_dict(interaction: Interaction) -> Dict[str, Any]:
    """Convert Interaction model to dictionary."""
    return {
        "id": str(interaction.id),
        "type": interaction.type,
        "direction": interaction.direction,
        "subject": interaction.subject,
        "content": interaction.content,
        "date": interaction.date.isoformat() if interaction.date else None,
        "metadata": interaction.metadata,
        "isDeleted": interaction.isDeleted,
        "createdAt": interaction.createdAt.isoformat() if interaction.createdAt else None,
        "updatedAt": interaction.updatedAt.isoformat() if interaction.updatedAt else None,
        "workspaceId": str(interaction.workspaceId),
        "createdById": str(interaction.createdById),
        "peopleId": str(interaction.peopleId) if interaction.peopleId else None,
        "companyId": str(interaction.companyId) if interaction.companyId else None,
        "externalId": interaction.externalId,
        "externalType": interaction.externalType,
    }


class PostgreSQLDataAccess(DataAccessInterface):
    """PostgreSQL implementation of data access interface."""

    def search_people(
        self,
        workspace_id: str,
        query: Optional[str] = None,
        email: Optional[str] = None,
        job_title: Optional[str] = None,
        company_id: Optional[str] = None,
        group_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        has_interactions_since: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search for people."""
        with get_db_session() as session:
            workspace_uuid = UUID(workspace_id)
            limit = limit or 20
            offset = offset or 0
            sort_order = sort_order or "desc"

            # Base query
            q = session.query(Person).filter(Person.workspaceId == workspace_uuid)

            # Query filter
            if query:
                search_term = f"%{query.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(Person.firstName).like(search_term),
                        func.lower(Person.lastName).like(search_term),
                        func.lower(Person.jobTitle).like(search_term),
                    )
                )

            # Email filter
            if email:
                q = q.join(Email).filter(func.lower(Email.value) == email.lower())

            # Job title filter
            if job_title:
                q = q.filter(func.lower(Person.jobTitle).like(f"%{job_title.lower()}%"))

            # Company filter
            if company_id:
                company_uuid = UUID(company_id)
                q = q.join(MetaData).filter(MetaData.companyId == company_uuid)

            # Group filter
            if group_id:
                group_uuid = UUID(group_id)
                q = q.join(GroupPeople).filter(GroupPeople.groupId == group_uuid)

            # Interactions filter
            if has_interactions_since:
                q = q.join(Interaction).filter(
                    and_(
                        Interaction.peopleId == Person.id,
                        Interaction.date >= has_interactions_since,
                    )
                )

            # Sorting
            if sort_by == "name":
                if sort_order == "asc":
                    q = q.order_by(Person.firstName, Person.lastName)
                else:
                    q = q.order_by(desc(Person.firstName), desc(Person.lastName))
            elif sort_by == "createdAt":
                if sort_order == "asc":
                    q = q.order_by(Person.createdAt)
                else:
                    q = q.order_by(desc(Person.createdAt))
            else:
                q = q.order_by(desc(Person.createdAt))

            # Count total
            total = q.count()

            # Pagination
            results = q.offset(offset).limit(limit).all()

            return {
                "results": [_person_to_dict(p) for p in results],
                "total": total,
                "hasMore": (offset + limit) < total,
            }

    def get_person_by_id(
        self,
        workspace_id: str,
        person_id: str,
        include: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get person by ID."""
        with get_db_session() as session:
            workspace_uuid = UUID(workspace_id)
            person_uuid = UUID(person_id)

            person = session.query(Person).filter(
                and_(
                    Person.id == person_uuid,
                    Person.workspaceId == workspace_uuid,
                )
            ).first()

            if not person:
                return {
                    "person": None,
                    "companies": None,
                    "primaryCompany": None,
                    "deals": None,
                    "interactions": None,
                    "emails": None,
                    "phones": None,
                    "addresses": None,
                    "urls": None,
                    "customFields": None,
                    "groups": None,
                }

            result = {"person": _person_to_dict(person)}

            include = include or {}

            # Companies
            if include.get("companies") or include.get("primaryCompany"):
                metadata_records = session.query(MetaData).filter(
                    MetaData.peopleId == person_uuid
                ).all()

                companies_list = []
                primary_company = None

                for meta in metadata_records:
                    company = session.query(Company).filter(Company.id == meta.companyId).first()
                    if company:
                        company_dict = _company_to_dict(company)
                        company_data = {
                            "company": company_dict,
                            "isPrimary": meta.isPeoplePrimary,
                            "relationship": "current",  # Default, can be enhanced
                            "metadata": {
                                "isPeoplePrimary": meta.isPeoplePrimary,
                                "isCompanyPrimary": meta.isCompanyPrimary,
                                "createdAt": meta.createdAt.isoformat() if meta.createdAt else None,
                                "updatedAt": meta.updatedAt.isoformat() if meta.updatedAt else None,
                            } if include.get("includeMetadata") else None,
                        }
                        companies_list.append(company_data)
                        if meta.isPeoplePrimary:
                            primary_company = company_dict

                result["companies"] = companies_list if include.get("companies") else None
                result["primaryCompany"] = primary_company if include.get("primaryCompany") else None

            # Deals
            if include.get("deals"):
                deal_metadata = session.query(DealMetaData).filter(
                    DealMetaData.peopleId == person_uuid
                ).all()

                deals_list = []
                for dm in deal_metadata:
                    deal = session.query(Deal).filter(Deal.id == dm.dealId).first()
                    if deal:
                        # Get column/stage info
                        column = session.query(Column).filter(Column.id == deal.columnId).first()
                        group = session.query(Group).filter(Group.id == column.groupId).first() if column else None

                        deal_data = {
                            "deal": _deal_to_dict(deal),
                            "role": None,  # Can be added if stored
                            "company": None,
                            "stage": {
                                "columnId": str(deal.columnId),
                                "columnName": column.name if column else None,
                                "groupId": str(column.groupId) if column else None,
                                "groupName": group.name if group else None,
                            } if column else None,
                        }
                        deals_list.append(deal_data)

                result["deals"] = deals_list

            # Interactions
            if include.get("recentInteractions"):
                limit = include.get("recentInteractions", 20)
                interactions = session.query(Interaction).filter(
                    and_(
                        Interaction.peopleId == person_uuid,
                        Interaction.isDeleted == False,
                    )
                ).order_by(desc(Interaction.date)).limit(limit).all()
                result["interactions"] = [_interaction_to_dict(i) for i in interactions]

            # Emails
            if include.get("emails"):
                emails = session.query(Email).filter(Email.personId == person_uuid).all()
                result["emails"] = [
                    {
                        "id": str(e.id),
                        "value": e.value,
                        "type": e.type,
                        "isPrimary": e.isPrimary,
                        "verified": e.verified,
                    }
                    for e in emails
                ]
            else:
                # Just primary email
                primary_email = session.query(Email).filter(
                    and_(
                        Email.personId == person_uuid,
                        Email.isPrimary == True,
                    )
                ).first()
                result["emails"] = [{
                    "id": str(primary_email.id),
                    "value": primary_email.value,
                    "type": primary_email.type,
                    "isPrimary": primary_email.isPrimary,
                    "verified": primary_email.verified,
                }] if primary_email else []

            # Phones
            if include.get("phones"):
                phones = session.query(PhoneNumber).filter(PhoneNumber.personId == person_uuid).all()
                result["phones"] = [
                    {
                        "id": str(p.id),
                        "value": p.value,
                        "type": p.type,
                        "isPrimary": p.isPrimary,
                    }
                    for p in phones
                ]
            else:
                primary_phone = session.query(PhoneNumber).filter(
                    and_(
                        PhoneNumber.personId == person_uuid,
                        PhoneNumber.isPrimary == True,
                    )
                ).first()
                result["phones"] = [{
                    "id": str(primary_phone.id),
                    "value": primary_phone.value,
                    "type": primary_phone.type,
                    "isPrimary": primary_phone.isPrimary,
                }] if primary_phone else []

            # Addresses
            if include.get("addresses"):
                addresses = session.query(Address).filter(Address.personId == person_uuid).all()
                result["addresses"] = [
                    {
                        "id": str(a.id),
                        "value": a.value,
                        "type": a.type,
                        "isPrimary": a.isPrimary,
                    }
                    for a in addresses
                ]

            # URLs
            if include.get("urls"):
                urls = session.query(URL).filter(URL.personId == person_uuid).all()
                result["urls"] = [
                    {
                        "id": str(u.id),
                        "label": u.label,
                        "value": u.value,
                        "isPrimary": u.isPrimary,
                    }
                    for u in urls
                ]

            # Custom fields
            if include.get("customFields"):
                custom_fields = self._get_custom_fields_for_entity(
                    session, "people", person_uuid, workspace_uuid
                )
                result["customFields"] = custom_fields

            # Groups
            if include.get("groups"):
                group_memberships = session.query(GroupPeople).filter(
                    GroupPeople.peopleId == person_uuid
                ).all()
                groups = []
                for gm in group_memberships:
                    group = session.query(Group).filter(Group.id == gm.groupId).first()
                    if group:
                        groups.append({
                            "id": str(group.id),
                            "name": group.name,
                            "type": group.type,
                            "description": group.description,
                        })
                result["groups"] = groups

            return result

    def _get_custom_fields_for_entity(
        self,
        session: Session,
        entity_type: str,
        entity_id: UUID,
        workspace_id: UUID,
    ) -> Dict[str, Any]:
        """Get custom field values for an entity."""
        entity_field = f"{entity_type}Id"
        custom_fields = {}

        # Get column values
        column_values = session.query(ColumnValue).filter(
            getattr(ColumnValue, entity_field) == entity_id
        ).all()

        for cv in column_values:
            column = session.query(Column).filter(Column.id == cv.columnId).first()
            if column:
                # Check workspace through group
                group = session.query(Group).filter(Group.id == column.groupId).first()
                if group and group.workspaceId == workspace_id:
                    custom_fields[column.name] = {
                        "value": cv.value,
                        "dataType": column.dataType,
                        "selectedOptions": cv.selectedOptions,
                    }

        # Get select option values
        select_options = session.query(ColumnValueSelectOption).filter(
            getattr(ColumnValueSelectOption, entity_field) == entity_id
        ).all()

        for so in select_options:
            column = session.query(Column).filter(Column.id == so.columnId).first()
            if column:
                group = session.query(Group).filter(Group.id == column.groupId).first()
                if group and group.workspaceId == workspace_id:
                    if column.name not in custom_fields:
                        custom_fields[column.name] = {
                            "value": None,
                            "dataType": column.dataType,
                            "selectedOptions": [],
                        }
                    # Add selected option (would need to join with selectOption table for full details)
                    if "selectedOptions" not in custom_fields[column.name]:
                        custom_fields[column.name]["selectedOptions"] = []
                    custom_fields[column.name]["selectedOptions"].append(str(so.selectOptionId))

        # Get member values
        member_values = session.query(ColumnValueMember).filter(
            getattr(ColumnValueMember, entity_field) == entity_id
        ).all()

        for mv in member_values:
            column = session.query(Column).filter(Column.id == mv.columnId).first()
            if column:
                group = session.query(Group).filter(Group.id == column.groupId).first()
                if group and group.workspaceId == workspace_id:
                    custom_fields[column.name] = {
                        "value": str(mv.memberId),
                        "dataType": column.dataType,
                        "memberId": str(mv.memberId),
                    }

        return custom_fields

    # Additional methods for companies, deals, interactions, etc.
    # These are placeholder implementations that can be expanded

    def search_companies(
        self,
        workspace_id: str,
        query: Optional[str] = None,
        industry: Optional[str] = None,
        size: Optional[str] = None,
        tags: Optional[List[str]] = None,
        has_interactions_since: Optional[datetime] = None,
        has_deals_since: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search for companies."""
        with get_db_session() as session:
            workspace_uuid = UUID(workspace_id)
            limit = limit or 20
            offset = offset or 0

            q = session.query(Company).filter(Company.workspaceId == workspace_uuid)

            if query:
                search_term = f"%{query.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(Company.name).like(search_term),
                        func.lower(Company.description).like(search_term),
                    )
                )

            if sort_by == "name":
                q = q.order_by(Company.name if sort_order == "asc" else desc(Company.name))
            else:
                q = q.order_by(desc(Company.createdAt))

            total = q.count()
            results = q.offset(offset).limit(limit).all()

            return {
                "results": [_company_to_dict(c) for c in results],
                "total": total,
                "hasMore": (offset + limit) < total,
            }

    def search_deals(
        self,
        workspace_id: str,
        query: Optional[str] = None,
        column_id: Optional[str] = None,
        column_ids: Optional[List[str]] = None,
        group_id: Optional[str] = None,
        company_id: Optional[str] = None,
        person_id: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search for deals."""
        with get_db_session() as session:
            limit = limit or 20
            offset = offset or 0

            q = session.query(Deal)

            if query:
                q = q.filter(func.lower(Deal.name).like(f"%{query.lower()}%"))

            if column_id:
                q = q.filter(Deal.columnId == UUID(column_id))
            elif column_ids:
                q = q.filter(Deal.columnId.in_([UUID(cid) for cid in column_ids]))

            if company_id:
                q = q.join(DealMetaData).filter(DealMetaData.companyId == UUID(company_id))

            if person_id:
                q = q.join(DealMetaData).filter(DealMetaData.peopleId == UUID(person_id))

            if created_after:
                q = q.filter(Deal.createdAt >= created_after)
            if created_before:
                q = q.filter(Deal.createdAt <= created_before)

            if sort_by == "name":
                q = q.order_by(Deal.name if sort_order == "asc" else desc(Deal.name))
            else:
                q = q.order_by(desc(Deal.createdAt))

            total = q.count()
            results = q.offset(offset).limit(limit).all()

            return {
                "results": [_deal_to_dict(d) for d in results],
                "total": total,
                "hasMore": (offset + limit) < total,
                "summary": {
                    "totalValue": 0.0,  # Would need to calculate from column values
                    "averageValue": 0.0,
                    "byStage": {},
                },
            }

    def search_interactions(
        self,
        workspace_id: str,
        query: Optional[str] = None,
        type: Optional[List[str]] = None,
        direction: Optional[str] = None,
        person_id: Optional[str] = None,
        company_id: Optional[str] = None,
        created_by: Optional[str] = None,
        date_range: Optional[Dict[str, datetime]] = None,
        has_content: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Search for interactions."""
        with get_db_session() as session:
            workspace_uuid = UUID(workspace_id)
            limit = limit or 20
            offset = offset or 0

            q = session.query(Interaction).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.isDeleted == False,
                )
            )

            if query:
                search_term = f"%{query.lower()}%"
                q = q.filter(
                    or_(
                        func.lower(Interaction.subject).like(search_term),
                        func.lower(Interaction.content).like(search_term),
                    )
                )

            if type:
                q = q.filter(Interaction.type.in_(type))

            if direction and direction != "both":
                q = q.filter(Interaction.direction == direction)

            if person_id:
                q = q.filter(Interaction.peopleId == UUID(person_id))

            if company_id:
                q = q.filter(Interaction.companyId == UUID(company_id))

            if created_by:
                q = q.filter(Interaction.createdById == UUID(created_by))

            if date_range:
                if date_range.get("start"):
                    q = q.filter(Interaction.date >= date_range["start"])
                if date_range.get("end"):
                    q = q.filter(Interaction.date <= date_range["end"])

            if has_content:
                q = q.filter(Interaction.content.isnot(None))

            if sort_by == "date":
                q = q.order_by(Interaction.date if sort_order == "asc" else desc(Interaction.date))
            else:
                q = q.order_by(desc(Interaction.createdAt))

            total = q.count()
            results = q.offset(offset).limit(limit).all()

            # Summary
            summary_q = session.query(Interaction).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.isDeleted == False,
                )
            )
            if type:
                summary_q = summary_q.filter(Interaction.type.in_(type))
            if direction and direction != "both":
                summary_q = summary_q.filter(Interaction.direction == direction)

            by_type = {}
            by_direction = {"inbound": 0, "outbound": 0}

            type_counts = session.query(
                Interaction.type,
                func.count(Interaction.id)
            ).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.isDeleted == False,
                )
            ).group_by(Interaction.type).all()

            for itype, count in type_counts:
                by_type[itype] = count

            direction_counts = session.query(
                Interaction.direction,
                func.count(Interaction.id)
            ).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.isDeleted == False,
                )
            ).group_by(Interaction.direction).all()

            for dir, count in direction_counts:
                by_direction[dir.lower()] = count

            return {
                "results": [_interaction_to_dict(i) for i in results],
                "total": total,
                "hasMore": (offset + limit) < total,
                "summary": {
                    "byType": by_type,
                    "byDirection": by_direction,
                },
            }

    def get_workspace_summary(self, workspace_id: str) -> Dict[str, Any]:
        """Get workspace summary statistics."""
        with get_db_session() as session:
            workspace_uuid = UUID(workspace_id)

            # People stats
            total_people = session.query(func.count(Person.id)).filter(
                Person.workspaceId == workspace_uuid
            ).scalar()

            this_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            people_this_month = session.query(func.count(Person.id)).filter(
                and_(
                    Person.workspaceId == workspace_uuid,
                    Person.createdAt >= this_month_start,
                )
            ).scalar()

            people_with_interactions = session.query(func.count(func.distinct(Interaction.peopleId))).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.peopleId.isnot(None),
                    Interaction.isDeleted == False,
                )
            ).scalar()

            # Company stats
            total_companies = session.query(func.count(Company.id)).filter(
                Company.workspaceId == workspace_uuid
            ).scalar()

            companies_this_month = session.query(func.count(Company.id)).filter(
                and_(
                    Company.workspaceId == workspace_uuid,
                    Company.createdAt >= this_month_start,
                )
            ).scalar()

            companies_with_deals = session.query(func.count(func.distinct(DealMetaData.companyId))).filter(
                DealMetaData.companyId.isnot(None)
            ).scalar()

            # Deal stats
            total_deals = session.query(func.count(Deal.id)).scalar()
            # Note: active/won/lost would need status determination from column values

            # Interaction stats
            total_interactions = session.query(func.count(Interaction.id)).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.isDeleted == False,
                )
            ).scalar()

            this_week_start = datetime.now() - timedelta(days=datetime.now().weekday())
            interactions_this_week = session.query(func.count(Interaction.id)).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.date >= this_week_start,
                    Interaction.isDeleted == False,
                )
            ).scalar()

            interactions_this_month = session.query(func.count(Interaction.id)).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.date >= this_month_start,
                    Interaction.isDeleted == False,
                )
            ).scalar()

            interaction_types = session.query(
                Interaction.type,
                func.count(Interaction.id)
            ).filter(
                and_(
                    Interaction.workspaceId == workspace_uuid,
                    Interaction.isDeleted == False,
                )
            ).group_by(Interaction.type).all()

            by_type = {itype: count for itype, count in interaction_types}

            return {
                "people": {
                    "total": total_people or 0,
                    "addedThisMonth": people_this_month or 0,
                    "withInteractions": people_with_interactions or 0,
                },
                "companies": {
                    "total": total_companies or 0,
                    "addedThisMonth": companies_this_month or 0,
                    "withDeals": companies_with_deals or 0,
                },
                "deals": {
                    "total": total_deals or 0,
                    "active": 0,  # Would need status calculation
                    "won": 0,
                    "lost": 0,
                    "totalValue": 0.0,
                },
                "interactions": {
                    "total": total_interactions or 0,
                    "thisWeek": interactions_this_week or 0,
                    "thisMonth": interactions_this_month or 0,
                    "byType": by_type,
                },
            }


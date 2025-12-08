"""SQLAlchemy database models for CRM."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Person(Base):
    """Person model."""
    __tablename__ = "people"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    firstName = Column(String, nullable=False)
    lastName = Column(String, nullable=True)
    jobTitle = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    dateOfBirth = Column(DateTime, nullable=True)
    gender = Column(String, nullable=True)
    imageUrl = Column(String, nullable=True)
    privacyLevel = Column(Enum("PRIVATE", "PUBLIC", name="privacy_level"), nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspaceId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    createdBy = Column(PGUUID(as_uuid=True), nullable=False)

    # Relationships
    emails = relationship("Email", back_populates="person", foreign_keys="Email.personId")
    phones = relationship("PhoneNumber", back_populates="person", foreign_keys="PhoneNumber.personId")
    addresses = relationship("Address", back_populates="person", foreign_keys="Address.personId")
    urls = relationship("URL", back_populates="person", foreign_keys="URL.personId")
    interactions = relationship("Interaction", back_populates="person", foreign_keys="Interaction.peopleId")


class Company(Base):
    """Company model."""
    __tablename__ = "company"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    imageUrl = Column(String, nullable=True)
    privacyLevel = Column(Enum("PRIVATE", "PUBLIC", name="privacy_level"), nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspaceId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    createdBy = Column(PGUUID(as_uuid=True), nullable=False)

    # Relationships
    emails = relationship("Email", back_populates="company", foreign_keys="Email.companyId")
    phones = relationship("PhoneNumber", back_populates="company", foreign_keys="PhoneNumber.companyId")
    addresses = relationship("Address", back_populates="company", foreign_keys="Address.companyId")
    urls = relationship("URL", back_populates="company", foreign_keys="URL.companyId")
    interactions = relationship("Interaction", back_populates="company", foreign_keys="Interaction.companyId")


class Deal(Base):
    """Deal model."""
    __tablename__ = "deal"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    columnId = Column(PGUUID(as_uuid=True), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    createdBy = Column(PGUUID(as_uuid=True), nullable=True)


class Interaction(Base):
    """Interaction model."""
    __tablename__ = "interaction"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    type = Column(
        Enum(
            "EMAIL", "CALENDAR", "CALL", "MEETING", "NOTE", "SMS",
            "LINKEDIN_MESSAGE", "SOCIAL_MEDIA",
            name="interaction_type"
        ),
        nullable=False
    )
    direction = Column(Enum("INBOUND", "OUTBOUND", name="interaction_direction"), nullable=False)
    subject = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    date = Column(DateTime, nullable=False)
    meta_data = Column("metadata", JSON, nullable=True)
    isDeleted = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspaceId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    createdById = Column(PGUUID(as_uuid=True), nullable=False)
    peopleId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=True, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    externalId = Column(String, nullable=True)
    externalType = Column(String, nullable=True)

    # Relationships
    person = relationship("Person", back_populates="interactions", foreign_keys=[peopleId])
    company = relationship("Company", back_populates="interactions", foreign_keys=[companyId])


class Email(Base):
    """Email model."""
    __tablename__ = "email"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    value = Column(String, nullable=False)
    type = Column(String, nullable=True)
    isPrimary = Column(Boolean, default=False, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    personId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=True, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="emails", foreign_keys=[personId])
    company = relationship("Company", back_populates="emails", foreign_keys=[companyId])


class PhoneNumber(Base):
    """PhoneNumber model."""
    __tablename__ = "phoneNumber"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    value = Column(String, nullable=False)
    type = Column(String, nullable=True)
    isPrimary = Column(Boolean, default=False, nullable=False)
    personId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=True, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="phones", foreign_keys=[personId])
    company = relationship("Company", back_populates="phones", foreign_keys=[companyId])


class Address(Base):
    """Address model."""
    __tablename__ = "address"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    value = Column(Text, nullable=True)
    type = Column(String, nullable=True)
    isPrimary = Column(Boolean, default=False, nullable=False)
    personId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=True, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="addresses", foreign_keys=[personId])
    company = relationship("Company", back_populates="addresses", foreign_keys=[companyId])


class URL(Base):
    """URL model."""
    __tablename__ = "url"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    label = Column(String, nullable=True)
    value = Column(String, nullable=False)
    isPrimary = Column(Boolean, default=False, nullable=False)
    personId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=True, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="urls", foreign_keys=[personId])
    company = relationship("Company", back_populates="urls", foreign_keys=[companyId])


class Group(Base):
    """Group model."""
    __tablename__ = "group"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    type = Column(Enum("PEOPLE", "COMPANY", "DEAL", name="group_type"), nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String, nullable=True)
    isPrivate = Column(Boolean, default=False, nullable=False)
    isFavourite = Column(Boolean, default=False, nullable=False)
    isDeleted = Column(Boolean, default=False, nullable=False)
    isCollapse = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspaceId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    createdBy = Column(PGUUID(as_uuid=True), nullable=False)
    favouriteOrder = Column(Integer, nullable=True)
    privateOrder = Column(Integer, nullable=True)
    publicOrder = Column(Integer, nullable=True)


class CustomField(Base):
    """Column (custom field) model."""
    __tablename__ = "column"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    dataType = Column(
        Enum(
            "TEXT", "NUMBER", "DATE", "BOOLEAN", "JSON", "MULTISELECT", "SELECT",
            "DEALS", "LARGE_TEXT", "MEMBER", "CONTACT", "URL", "PHONE_NUMBERS",
            "EMAILS", "ADDRESS", "LONG_TEXT", "GROUPS", "CREATED_BY",
            "GROUP_ADDED_AT", "COMPANIES", "PEOPLE", "MAGIC_FIELD",
            name="data_type"
        ),
        nullable=False
    )
    isDefault = Column(Boolean, default=False, nullable=False)
    type = Column(Enum("COMPANY", "PEOPLE", "DEAL", name="column_type"), nullable=False)
    isDeleted = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    groupId = Column(PGUUID(as_uuid=True), nullable=False)
    dealId = Column(PGUUID(as_uuid=True), nullable=True)
    selectOptions = Column(JSON, nullable=True)


# Relationship tables
class MetaData(Base):
    """People-Company relationship metadata."""
    __tablename__ = "metaData"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    peopleId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=False, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=False, index=True)
    isPeoplePrimary = Column(Boolean, default=False, nullable=False)
    isCompanyPrimary = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("peopleId", "companyId", name="companyMetaData_peopleId_companyId_key"),
        Index("idx_peopleId_isCompanyPrimary", "peopleId", "isCompanyPrimary"),
        Index("idx_companyId_isPeoplePrimary", "companyId", "isPeoplePrimary"),
    )


class DealMetaData(Base):
    """Deal-Person/Company relationship."""
    __tablename__ = "dealMetaData"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dealId = Column(PGUUID(as_uuid=True), ForeignKey("deal.id"), nullable=False, index=True)
    peopleId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), nullable=True, index=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("peopleId", "dealId", name="dealMetaData_peopleId_dealId_key"),
        UniqueConstraint("companyId", "dealId", name="dealMetaData_companyId_dealId_key"),
        Index("idx_dealId_peopleId", "dealId", "peopleId"),
        Index("idx_dealId_companyId", "dealId", "companyId"),
    )


class GroupPeople(Base):
    """People-Group membership."""
    __tablename__ = "groupPeople"

    groupId = Column(PGUUID(as_uuid=True), ForeignKey("group.id"), primary_key=True)
    peopleId = Column(PGUUID(as_uuid=True), ForeignKey("people.id"), primary_key=True)
    addedAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    addedBy = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    __table_args__ = (
        Index("idx_peopleId", "peopleId"),
        Index("idx_peopleId_groupId", "peopleId", "groupId"),
        Index("idx_addedBy", "addedBy"),
    )


class GroupCompany(Base):
    """Company-Group membership."""
    __tablename__ = "groupCompany"

    groupId = Column(PGUUID(as_uuid=True), ForeignKey("group.id"), primary_key=True)
    companyId = Column(PGUUID(as_uuid=True), ForeignKey("company.id"), primary_key=True)
    addedAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    addedBy = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    __table_args__ = (
        Index("idx_companyId", "companyId"),
        Index("idx_companyId_groupId", "companyId", "groupId"),
        Index("idx_addedBy", "addedBy"),
    )


# Custom field value tables
class ColumnValue(Base):
    """Custom field value."""
    __tablename__ = "column_values"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    value = Column(String, nullable=False)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id"), nullable=False, index=True)
    selectedOptions = Column(JSON, nullable=True)
    companyId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    peopleId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    dealId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))


class ColumnValueSelectOption(Base):
    """Select option value for SELECT/MULTISELECT fields."""
    __tablename__ = "columnValueSelectOption"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    selectOptionId = Column(PGUUID(as_uuid=True), nullable=False)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id"), nullable=False, index=True)
    companyId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    peopleId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    dealId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))


class ColumnValueMember(Base):
    """Member reference value for MEMBER type fields."""
    __tablename__ = "columnValueMember"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    memberId = Column(PGUUID(as_uuid=True), nullable=False)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id"), nullable=False, index=True)
    companyId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    peopleId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    dealId = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    createdBy = Column(PGUUID(as_uuid=True), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))


class Conversation(Base):
    """Conversation model for AI conversations."""
    __tablename__ = "conversation"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspaceId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    userId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    title = Column(Text, nullable=True)
    context = Column(JSONB, nullable=True)
    createdAt = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
        index=True,
    )
    updatedAt = Column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,  # Python-side default for INSERT
        server_default=text("CURRENT_TIMESTAMP(6)"),  # Database-side default
        onupdate=datetime.utcnow,  # For UPDATE operations
    )
    
    __table_args__ = (
        Index("idx_conversation_workspaceId_userId", "workspaceId", "userId"),
        Index("idx_conversation_workspaceId", "workspaceId"),
        Index("idx_conversation_userId", "userId"),
        Index("idx_conversation_createdAt", "createdAt"),
    )


class ConversationMessage(Base):
    """Conversation message model for AI conversations."""
    __tablename__ = "conversationMessage"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversationId = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        Enum("USER", "ASSISTANT", "SYSTEM", "FUNCTION", name="conversation_role"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    meta_data = Column("metadata", JSONB, nullable=True)
    functionCalls = Column(JSONB, nullable=True)
    timestamp = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
        index=True,
    )

    __table_args__ = (
        Index("conversationMessage_conversationId_idx", "conversationId"),
        Index("conversationMessage_conversationId_timestamp_idx", "conversationId", "timestamp"),
        Index("conversationMessage_role_idx", "role"),
    )


class ConversationSummary(Base):
    """Conversation summary model for storing conversation summaries."""
    __tablename__ = "conversationSummary"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversationId = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    workspaceId = Column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    summaryText = Column(Text, nullable=False)
    startMessageId = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversationMessage.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    endMessageId = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversationMessage.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    endMessageAt = Column(DateTime(timezone=False), nullable=False)
    messageCount = Column(Integer, nullable=False)
    summaryTokens = Column(Integer, nullable=False)
    createdAt = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
    updatedAt = Column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=datetime.utcnow,
    )
    
    __table_args__ = (
        Index("conversationSummary_conversationId_createdAt_idx", "conversationId", "createdAt"),
        Index("conversationSummary_workspaceId_idx", "workspaceId"),
    )


class View(Base):
    """View model for groups."""
    __tablename__ = "view"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    type = Column(Enum("TABLE", "PIPELINE", "KANBAN", "CALENDAR", name="view_type"), nullable=False)
    isDefault = Column(Boolean, default=False, nullable=False)
    groupId = Column(PGUUID(as_uuid=True), ForeignKey("group.id", ondelete="CASCADE"), nullable=False, index=True)
    workspaceId = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    targetEntity = Column(Enum("PEOPLE", "COMPANY", "DEAL", name="target_entity"), nullable=False)
    groupBy = Column(String, nullable=True)
    order = Column(Integer, default=100, nullable=False)
    dealColumnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id", ondelete="CASCADE"), nullable=True)
    isDeleted = Column(Boolean, default=False, nullable=False)
    condition = Column(Text, nullable=True)
    aggregateType = Column(String, nullable=True)
    groupColumnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id", ondelete="CASCADE"), nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_groupId_isDeleted", "groupId", "isDeleted"),
        Index("idx_workspaceId_targetEntity_isDeleted", "workspaceId", "targetEntity", "isDeleted"),
        Index("idx_workspaceId_isDefault_isDeleted", "workspaceId", "isDefault", "isDeleted"),
        Index("idx_type_targetEntity", "type", "targetEntity"),
    )


class ColumnViewSetting(Base):
    """Column view settings model."""
    __tablename__ = "columnViewSettings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order = Column(Integer, nullable=False)
    isVisible = Column(Boolean, default=True, nullable=False)
    width = Column(Integer, nullable=True)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id", ondelete="CASCADE"), nullable=True)
    viewId = Column(PGUUID(as_uuid=True), ForeignKey("view.id", ondelete="CASCADE"), nullable=False, index=True)
    defaultColumnId = Column(PGUUID(as_uuid=True), ForeignKey("defaultColumn.id", ondelete="CASCADE"), nullable=True)
    isDeleted = Column(Boolean, default=False, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("viewId", "columnId", name="columnViewSettings_viewId_columnId_key"),
        UniqueConstraint("viewId", "defaultColumnId", name="columnViewSettings_viewId_defaultColumnId_key"),
        Index("idx_viewId_order_isVisible", "viewId", "order", "isVisible"),
        Index("idx_viewId_isDeleted", "viewId", "isDeleted"),
    )


class SelectOption(Base):
    """Select option model for SELECT type columns."""
    __tablename__ = "selectOption"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    value = Column(String, nullable=False)
    color = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    pipelineOrder = Column(Integer, nullable=True)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id", ondelete="CASCADE"), nullable=False, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_columnId", "columnId"),
        Index("idx_columnId_order", "columnId", "order"),
        Index("idx_columnId_pipelineOrder", "columnId", "pipelineOrder"),
        Index("idx_value", "value"),
    )


class SelectOptionSetting(Base):
    """Select option setting for views."""
    __tablename__ = "selectOptionSetting"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    selectOptionId = Column(PGUUID(as_uuid=True), ForeignKey("selectOption.id", ondelete="CASCADE"), nullable=False)
    viewId = Column(PGUUID(as_uuid=True), ForeignKey("view.id", ondelete="CASCADE"), nullable=False)
    isVisible = Column(Boolean, default=True, nullable=False)
    pipelineOrder = Column(Integer, default=100, nullable=False)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id", ondelete="CASCADE"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("columnId", "selectOptionId", "viewId", name="selectOptionSetting_columnId_selectOptionId_viewId_key"),
        Index("idx_columnId_selectOptionId_viewId", "columnId", "selectOptionId", "viewId"),
    )


class DefaultColumn(Base):
    """Default column model."""
    __tablename__ = "defaultColumn"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    label = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    dataType = Column(
        Enum(
            "TEXT", "NUMBER", "DATE", "BOOLEAN", "JSON", "MULTISELECT", "SELECT",
            "DEALS", "LARGE_TEXT", "MEMBER", "CONTACT", "URL", "PHONE_NUMBERS",
            "EMAILS", "ADDRESS", "LONG_TEXT", "GROUPS", "CREATED_BY",
            "GROUP_ADDED_AT", "COMPANIES", "PEOPLE", "MAGIC_FIELD",
            name="data_type"
        ),
        nullable=False
    )
    isRequired = Column(Boolean, default=False, nullable=False)
    type = Column(Enum("COMPANY", "PEOPLE", "DEAL", name="column_type"), nullable=False)
    order = Column(Integer, nullable=False)
    isVisible = Column(Boolean, default=True, nullable=False)
    width = Column(Integer, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_type_order", "type", "order"),
        Index("idx_dataType_type", "dataType", "type"),
        Index("idx_isVisible_order", "isVisible", "order"),
    )


class ProfileColumnViewSetting(Base):
    """Profile column view settings model."""
    __tablename__ = "profileColumnViewSettings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order = Column(Integer, nullable=False)
    isVisible = Column(Boolean, default=True, nullable=False)
    columnId = Column(PGUUID(as_uuid=True), ForeignKey("column.id", ondelete="CASCADE"), nullable=True)
    groupId = Column(PGUUID(as_uuid=True), ForeignKey("group.id", ondelete="CASCADE"), nullable=False, index=True)
    defaultColumnId = Column(PGUUID(as_uuid=True), ForeignKey("defaultColumn.id", ondelete="CASCADE"), nullable=True)
    type = Column(Enum("PEOPLE", "COMPANY", "DEAL", name="target_entity"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("groupId", "columnId", name="profileColumnViewSettings_groupId_columnId_key"),
        UniqueConstraint("groupId", "defaultColumnId", name="profileColumnViewSettings_groupId_defaultColumnId_key"),
        Index("idx_groupId_order_isVisible", "groupId", "order", "isVisible"),
    )
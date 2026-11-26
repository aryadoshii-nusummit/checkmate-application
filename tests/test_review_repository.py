"""Tests for Checkmate review-result persistence."""

import pytest

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.database.base import Base
from app.database.models import FileReview, ReviewRun
from app.repositories.review_repository import (
    DuplicateDeliveryError,
    ReviewRepository,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    """Provide an isolated asynchronous in-memory database."""

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        testing_session = async_sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )

        async with testing_session() as session:
            yield session

    finally:
        await engine.dispose()

def sample_review():
    """Return a representative structured file-review result."""
    return {
        "path": "app/services/payment.py",
        "status": "reviewed",
        "review": "## Review\n\nFound security and validation concerns.",
        "findings": [
            {
                "title": "Missing input validation",
                "severity": "HIGH",
                "confidence": "HIGH",
                "category": "security",
                "line_numbers": [12],
                "evidence": "Raw user input is accepted.",
                "problem": "Input is not validated.",
                "impact": "Invalid data may reach application logic.",
                "recommendation": "Validate the input before processing.",
            }
        ],
        "issues_count": 2,
        "warnings_count": 1,
        "suggestions_count": 2,
    }


async def save_sample_run(repository, **overrides):
    """Save a representative review run, allowing individual fields to vary."""
    values = {
        "delivery_id": "delivery-001",
        "repository": "example/checkmate",
        "branch": "main",
        "commit_sha": "a" * 40,
        "updated_by": "developer-login",
        "commit_author": "Commit Author",
        "status": "completed",
        "reviews": [sample_review()],
    }
    values.update(overrides)
    return await repository.save_review_run(**values)


@pytest.mark.anyio
async def test_saves_review_run_and_file_reviews(db_session):
    repository = ReviewRepository(db_session)

    run = await save_sample_run(repository)

    saved_run = await repository.get_by_delivery_id("delivery-001")

    assert saved_run is not None
    assert saved_run.id == run.id
    assert saved_run.repository == "example/checkmate"
    assert saved_run.branch == "main"
    assert saved_run.commit_sha == "a" * 40
    assert saved_run.updated_by == "developer-login"
    assert saved_run.commit_author == "Commit Author"
    assert saved_run.status == "completed"

    assert saved_run.total_issues == 2
    assert saved_run.total_warnings == 1
    assert saved_run.total_suggestions == 2

    assert len(saved_run.file_reviews) == 1

    file_review = saved_run.file_reviews[0]
    assert file_review.file_name == "app/services/payment.py"
    assert file_review.file_status == "reviewed"
    assert file_review.issues_count == 2
    assert file_review.warnings_count == 1
    assert file_review.suggestions_count == 2
    assert file_review.findings[0]["category"] == "security"
    assert file_review.findings[0]["title"] == "Missing input validation"
    assert "Found security and validation concerns." in file_review.review_report


@pytest.mark.anyio
async def test_rejects_duplicate_delivery_id(db_session):
    repository = ReviewRepository(db_session)

    await save_sample_run(repository)

    with pytest.raises(DuplicateDeliveryError):
        await save_sample_run(repository)


@pytest.mark.anyio
async def test_rolls_back_run_when_file_review_insert_fails(db_session):
    repository = ReviewRepository(db_session)

    invalid_review = sample_review()
    invalid_review["review"] = None

    with pytest.raises(IntegrityError):
        await save_sample_run(repository, reviews=[invalid_review])

    run_count = await db_session.scalar(
        select(func.count()).select_from(ReviewRun)
    )
    file_review_count = await db_session.scalar(
        select(func.count()).select_from(FileReview)
    )

    assert run_count == 0
    assert file_review_count == 0


@pytest.mark.anyio
async def test_saves_run_without_file_reviews(db_session):
    repository = ReviewRepository(db_session)

    run = await save_sample_run(
        repository,
        delivery_id="delivery-empty",
        status="completed_with_skips",
        reviews=[],
    )

    saved_run = await repository.get_by_delivery_id("delivery-empty")

    assert saved_run is not None
    assert saved_run.id == run.id
    assert saved_run.status == "completed_with_skips"
    assert saved_run.total_issues == 0
    assert saved_run.total_warnings == 0
    assert saved_run.total_suggestions == 0
    assert saved_run.file_reviews == []


@pytest.mark.anyio
async def test_preserves_optional_author_fields(db_session):
    repository = ReviewRepository(db_session)

    run = await save_sample_run(
        repository,
        delivery_id="delivery-no-authors",
        updated_by=None,
        commit_author=None,
    )

    saved_run = await repository.get_by_delivery_id("delivery-no-authors")

    assert saved_run is not None
    assert saved_run.id == run.id
    assert saved_run.updated_by is None
    assert saved_run.commit_author is None


@pytest.mark.anyio
async def test_saves_all_structured_review_fields(db_session):
    """Persist and retrieve all structured AI review metadata."""
    repository = ReviewRepository(db_session)

    review = sample_review()
    review.update(
        {
            "summary": "The implementation is readable but needs validation.",
            "quality": "NEEDS IMPROVEMENT",
            "strengths": ["Clear function names", "Readable structure"],
            "areas_to_improve": ["Input validation"],
            "additional_suggestions": ["Add integration tests"],
        }
    )

    saved_run = await save_sample_run(
        repository,
        reviews=[review],
    )

    retrieved_run = await repository.get_by_delivery_id(saved_run.delivery_id)

    assert retrieved_run is not None
    assert len(retrieved_run.file_reviews) == 1

    stored_review = retrieved_run.file_reviews[0]

    assert stored_review.summary == review["summary"]
    assert stored_review.overall_quality == review["quality"]
    assert stored_review.strengths == review["strengths"]
    assert stored_review.areas_to_improve == review["areas_to_improve"]
    assert stored_review.additional_suggestions == review["additional_suggestions"]

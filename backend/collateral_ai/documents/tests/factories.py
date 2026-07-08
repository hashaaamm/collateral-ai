from __future__ import annotations

from factory import Faker
from factory import SubFactory
from factory.django import DjangoModelFactory

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.models import Document
from collateral_ai.documents.models import DocumentChunk


class DocumentFactory(DjangoModelFactory[Document]):
    company = SubFactory(CompanyFactory)
    file_name = Faker("file_name", extension="pdf")
    storage_path = "media/companies/1/documents/1/doc.pdf"
    content_type = "application/pdf"

    class Meta:
        model = Document


class DocumentChunkFactory(DjangoModelFactory[DocumentChunk]):
    document = SubFactory(DocumentFactory)
    chunk_type = "text"
    page_number = 1
    content = "hello world"
    embedding = [0.0] * 768

    class Meta:
        model = DocumentChunk

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # company defaults to the document's company when not given
        kwargs.setdefault("company", kwargs["document"].company)
        return super()._create(model_class, *args, **kwargs)

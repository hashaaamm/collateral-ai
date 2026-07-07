from __future__ import annotations

from factory import Faker
from factory import SubFactory
from factory.django import DjangoModelFactory

from collateral_ai.companies.tests.factories import CompanyFactory
from collateral_ai.documents.models import Document


class DocumentFactory(DjangoModelFactory[Document]):
    company = SubFactory(CompanyFactory)
    file_name = Faker("file_name", extension="pdf")
    storage_path = "media/companies/1/documents/1/doc.pdf"
    content_type = "application/pdf"

    class Meta:
        model = Document

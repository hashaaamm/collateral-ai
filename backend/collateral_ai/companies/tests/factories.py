from __future__ import annotations

from factory import Faker
from factory.django import DjangoModelFactory

from collateral_ai.companies.models import Company


class CompanyFactory(DjangoModelFactory[Company]):
    name = Faker("company")
    website = Faker("url")
    industry = Faker("bs")
    description = Faker("catch_phrase")

    class Meta:
        model = Company

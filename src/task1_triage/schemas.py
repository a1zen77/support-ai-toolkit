"""
Internal schema for the classification LLM call. Separate from the public
TriageResult in src/common/schemas.py because this one needs a cross-field
validator (product_area must be valid for the given product) that only
matters at generation time, not at the API boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from src.common.schemas import IssueCategory, Product, Urgency
from src.task1_triage.prompts import PRODUCT_AREAS


class ClassificationOutput(BaseModel):
    product: Product
    product_area: str
    category: IssueCategory
    category_reasoning: str
    urgency: Urgency
    urgency_reasoning: str

    @model_validator(mode="after")
    def check_product_area(self):
        valid_areas = PRODUCT_AREAS.get(self.product.value, [])
        if self.product_area not in valid_areas:
            raise ValueError(
                f"product_area '{self.product_area}' is not valid for product "
                f"'{self.product.value}'. Valid areas for {self.product.value}: {valid_areas}"
            )
        return self
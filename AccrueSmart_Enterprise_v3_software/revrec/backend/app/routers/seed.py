from sqlmodel import Session
from app.db import engine
from app.models.models import Product, RevRecCode


def seed_data():
    with Session(engine) as session:
        # RevRec rules
        rules = [
            ("STRAIGHT_LINE", "Even monthly revenue", "straight_line"),
            ("IMMEDIATE", "Full revenue at start", "immediate")
        ]
        for code, desc, rt in rules:
            if not session.get(RevRecCode, code):
                session.add(RevRecCode(code=code, description=desc, rule_type=rt))

        # Products
        products = [
            ("SKU-001", "Core License", 20000, "STRAIGHT_LINE"),
            ("SKU-002", "Premium Support", 30000, "STRAIGHT_LINE"),
            ("SKU-003", "Onboarding Fee", 5000, "IMMEDIATE"),
        ]
        for sku, name, ssp, r in products:
            if not session.get(Product, sku):
                session.add(Product(product_code=sku, name=name, ssp=ssp, revrec_code=r))

        session.commit()


# Allow running as a module
if __name__ == "__main__":
    seed_data()
    print("✅ Seed completed")

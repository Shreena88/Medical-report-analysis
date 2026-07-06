"""Seed script for the reference_ranges MongoDB collection.

Inserts at minimum 10 reference range entries using upsert so the script
can be run multiple times without creating duplicates.

Usage:
    python scripts/seed_reference_ranges.py

Requires the MONGODB_URI environment variable (loads from .env via python-dotenv
if available, or directly from the environment).
"""

from __future__ import annotations

import asyncio
import os

# Load .env if python-dotenv is available (not required in production)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGODB_URI = os.environ.get("MONGODB_URI")
if not MONGODB_URI:
    raise EnvironmentError(
        "MONGODB_URI environment variable is required. "
        "Set it in your .env file or shell environment."
    )

# ---------------------------------------------------------------------------
# Reference range seed data
# All values are based on widely-cited authoritative clinical reference ranges
# (e.g., Mayo Clinic, MedlinePlus, WHO).
# ---------------------------------------------------------------------------

REFERENCE_RANGES: list[dict] = [
    {
        "test_name": "Hemoglobin",
        "aliases": ["Hgb", "Hb", "haemoglobin"],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": (
            "Hemoglobin is the protein in red blood cells that carries oxygen "
            "throughout the body. Low levels may indicate anemia; high levels may "
            "indicate polycythemia or dehydration."
        ),
    },
    {
        "test_name": "Blood Sugar",
        "aliases": ["Glucose", "Fasting Blood Glucose", "FBG", "Blood Glucose", "FBS"],
        "unit": "mg/dL",
        "male_min": 70.0,
        "male_max": 100.0,
        "female_min": 70.0,
        "female_max": 100.0,
        "description": (
            "Fasting blood glucose measures the amount of sugar in the blood after "
            "an overnight fast. Values between 100–125 mg/dL suggest prediabetes; "
            "values ≥126 mg/dL on two separate tests suggest diabetes."
        ),
    },
    {
        "test_name": "Vitamin D",
        "aliases": ["25-OH Vitamin D", "25-Hydroxyvitamin D", "Vitamin D3", "Calcidiol"],
        "unit": "ng/mL",
        "male_min": 20.0,
        "male_max": 50.0,
        "female_min": 20.0,
        "female_max": 50.0,
        "description": (
            "Vitamin D (25-hydroxyvitamin D) is the best marker of overall vitamin D "
            "status. Deficiency (<20 ng/mL) is associated with bone loss and immune "
            "dysfunction. Toxicity is rare but can occur at levels above 150 ng/mL."
        ),
    },
    {
        "test_name": "Platelets",
        "aliases": ["PLT", "Platelet Count", "Thrombocytes"],
        "unit": "10^9/L",
        "male_min": 150.0,
        "male_max": 400.0,
        "female_min": 150.0,
        "female_max": 400.0,
        "description": (
            "Platelets are small blood cells that help form clots to stop bleeding. "
            "Low counts (thrombocytopenia) increase bleeding risk; high counts "
            "(thrombocytosis) may increase clot risk."
        ),
    },
    {
        "test_name": "WBC",
        "aliases": [
            "White Blood Cell Count",
            "White Blood Cells",
            "Leukocytes",
            "Leukocyte Count",
        ],
        "unit": "10^9/L",
        "male_min": 4.5,
        "male_max": 11.0,
        "female_min": 4.5,
        "female_max": 11.0,
        "description": (
            "White blood cells are part of the immune system and defend the body "
            "against infection. Elevated counts may signal infection or inflammation; "
            "low counts may indicate immune suppression."
        ),
    },
    {
        "test_name": "RBC",
        "aliases": [
            "Red Blood Cell Count",
            "Red Blood Cells",
            "Erythrocytes",
            "Erythrocyte Count",
        ],
        "unit": "10^12/L",
        "male_min": 4.5,
        "male_max": 5.9,
        "female_min": 4.1,
        "female_max": 5.1,
        "description": (
            "Red blood cells carry oxygen from the lungs to the rest of the body. "
            "Low RBC count is a hallmark of anemia; high count may indicate "
            "polycythemia vera or dehydration."
        ),
    },
    {
        "test_name": "Hematocrit",
        "aliases": ["Hct", "Packed Cell Volume", "PCV"],
        "unit": "%",
        "male_min": 41.0,
        "male_max": 53.0,
        "female_min": 36.0,
        "female_max": 46.0,
        "description": (
            "Hematocrit measures the proportion of red blood cells in the total blood "
            "volume. It is used together with hemoglobin and RBC count to diagnose and "
            "monitor anemia and other blood disorders."
        ),
    },
    {
        "test_name": "Creatinine",
        "aliases": ["Serum Creatinine", "SCr", "Creat"],
        "unit": "mg/dL",
        "male_min": 0.74,
        "male_max": 1.35,
        "female_min": 0.59,
        "female_max": 1.04,
        "description": (
            "Creatinine is a waste product of muscle metabolism filtered by the "
            "kidneys. Elevated serum creatinine indicates impaired kidney function. "
            "Values vary with muscle mass, age, and sex."
        ),
    },
    {
        "test_name": "ALT",
        "aliases": [
            "Alanine Aminotransferase",
            "Alanine Transaminase",
            "SGPT",
            "Serum Glutamate Pyruvate Transaminase",
        ],
        "unit": "U/L",
        "male_min": 7.0,
        "male_max": 56.0,
        "female_min": 7.0,
        "female_max": 45.0,
        "description": (
            "ALT is an enzyme found primarily in the liver. Elevated levels suggest "
            "liver cell damage or disease (e.g., hepatitis, fatty liver). It is one "
            "of the primary markers used to assess liver health."
        ),
    },
    {
        "test_name": "AST",
        "aliases": [
            "Aspartate Aminotransferase",
            "Aspartate Transaminase",
            "SGOT",
            "Serum Glutamic Oxaloacetic Transaminase",
        ],
        "unit": "U/L",
        "male_min": 10.0,
        "male_max": 40.0,
        "female_min": 10.0,
        "female_max": 35.0,
        "description": (
            "AST is an enzyme found in the liver, heart, muscles, and kidneys. "
            "Elevated AST can indicate liver disease, heart attack, or muscle damage. "
            "It is usually interpreted alongside ALT for liver assessment."
        ),
    },
]


# ---------------------------------------------------------------------------
# Upsert function
# ---------------------------------------------------------------------------


async def seed(uri: str) -> None:
    """Connect to MongoDB and upsert all reference range entries."""
    from motor.motor_asyncio import AsyncIOMotorClient

    client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
    db = client.get_default_database()
    collection = db["reference_ranges"]

    inserted = 0
    updated = 0

    for entry in REFERENCE_RANGES:
        result = await collection.update_one(
            {"test_name": entry["test_name"]},
            {"$set": entry},
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
            print(f"  [inserted] {entry['test_name']}")
        else:
            updated += 1
            print(f"  [updated]  {entry['test_name']}")

    print(
        f"\nDone. {inserted} inserted, {updated} updated "
        f"({len(REFERENCE_RANGES)} total entries)."
    )
    client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(seed(MONGODB_URI))

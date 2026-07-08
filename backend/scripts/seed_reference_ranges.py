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
        "aliases": ["Glucose", "Fasting Blood Glucose", "FBG", "Blood Glucose", "FBS", "Glu"],
        "unit": "mg/dL",
        "male_min": 70.0,
        "male_max": 100.0,
        "female_min": 70.0,
        "female_max": 100.0,
        "description": (
            "Fasting blood glucose measures the amount of sugar in the blood after "
            "an overnight fast. Values between 100–125 mg/dL suggest prediabetes; "
            "values >=126 mg/dL on two separate tests suggest diabetes."
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
    {
        "test_name": "HbA1c",
        "aliases": ["Hemoglobin A1c", "A1c", "Glycohemoglobin", "Glycated Hemoglobin"],
        "unit": "%",
        "male_min": 4.0,
        "male_max": 5.6,
        "female_min": 4.0,
        "female_max": 5.6,
        "description": (
            "HbA1c measures the average blood sugar level over the past 2-3 months. "
            "It is a key indicator for diagnosing and monitoring prediabetes and diabetes."
        ),
    },
    {
        "test_name": "TSH",
        "aliases": ["Thyrotropin", "Thyroid-Stimulating Hormone", "Thyroid Stimulating Hormone"],
        "unit": "uIU/mL",
        "male_min": 0.4,
        "male_max": 4.0,
        "female_min": 0.4,
        "female_max": 4.0,
        "description": (
            "TSH is produced by the pituitary gland to control thyroid hormone production. "
            "High levels suggest hypothyroidism (underactive thyroid); low levels suggest hyperthyroidism (overactive thyroid)."
        ),
    },
    {
        "test_name": "Free T4",
        "aliases": ["Free Thyroxine", "FT4"],
        "unit": "ng/dL",
        "male_min": 0.8,
        "male_max": 1.8,
        "female_min": 0.8,
        "female_max": 1.8,
        "description": (
            "Free T4 measures the active form of thyroxine in the blood. Together with TSH, "
            "it is used to evaluate thyroid gland function."
        ),
    },
    {
        "test_name": "Free T3",
        "aliases": ["Free Triiodothyronine", "FT3"],
        "unit": "pg/mL",
        "male_min": 2.3,
        "male_max": 4.2,
        "female_min": 2.3,
        "female_max": 4.2,
        "description": (
            "Free T3 measures the active form of triiodothyronine. It is useful in diagnosing "
            "hyperthyroidism and monitoring thyroid hormone replacement therapy."
        ),
    },
    {
        "test_name": "Total Cholesterol",
        "aliases": ["Cholesterol", "Total Chol", "TC"],
        "unit": "mg/dL",
        "male_min": 100.0,
        "male_max": 200.0,
        "female_min": 100.0,
        "female_max": 200.0,
        "description": (
            "Total Cholesterol measures the overall amount of cholesterol in the blood. "
            "Elevated levels are associated with increased cardiovascular disease risk."
        ),
    },
    {
        "test_name": "LDL Cholesterol",
        "aliases": ["LDL-C", "Low Density Lipoprotein", "Bad Cholesterol", "LDL"],
        "unit": "mg/dL",
        "male_min": 0.0,
        "male_max": 100.0,
        "female_min": 0.0,
        "female_max": 100.0,
        "description": (
            "LDL is known as 'bad' cholesterol because high levels can lead to plaque "
            "buildup in arteries, raising the risk of heart disease and stroke."
        ),
    },
    {
        "test_name": "HDL Cholesterol",
        "aliases": ["HDL-C", "High Density Lipoprotein", "Good Cholesterol", "HDL"],
        "unit": "mg/dL",
        "male_min": 40.0,
        "male_max": 60.0,
        "female_min": 50.0,
        "female_max": 60.0,
        "description": (
            "HDL is the 'good' cholesterol because it helps remove other forms of "
            "cholesterol from your bloodstream. Higher levels are generally cardioprotective."
        ),
    },
    {
        "test_name": "Triglycerides",
        "aliases": ["TRIG", "TG", "Trig", "Triglyceride"],
        "unit": "mg/dL",
        "male_min": 0.0,
        "male_max": 150.0,
        "female_min": 0.0,
        "female_max": 150.0,
        "description": (
            "Triglycerides are a type of fat found in your blood. High levels can "
            "increase the risk of heart disease, especially when combined with high LDL."
        ),
    },
    {
        "test_name": "Sodium",
        "aliases": ["Na", "Serum Sodium", "Sodium, Serum"],
        "unit": "mEq/L",
        "male_min": 135.0,
        "male_max": 145.0,
        "female_min": 135.0,
        "female_max": 145.0,
        "description": (
            "Sodium is a key electrolyte regulating water balance, blood pressure, "
            "and nerve/muscle function. Low levels (hyponatremia) or high levels can cause neurological symptoms."
        ),
    },
    {
        "test_name": "Potassium",
        "aliases": ["K", "Serum Potassium", "Potassium, Serum"],
        "unit": "mEq/L",
        "male_min": 3.5,
        "male_max": 5.0,
        "female_min": 3.5,
        "female_max": 5.0,
        "description": (
            "Potassium is an essential electrolyte for nerve signaling and muscle control, "
            "particularly in the heart. Minor deviations can lead to muscle weakness or arrhythmias."
        ),
    },
    {
        "test_name": "Chloride",
        "aliases": ["Cl", "Serum Chloride"],
        "unit": "mEq/L",
        "male_min": 96.0,
        "male_max": 106.0,
        "female_min": 96.0,
        "female_max": 106.0,
        "description": (
            "Chloride helps maintain proper blood volume, blood pressure, and acid-base balance "
            "in the body. Changes are often linked to kidney issues or severe dehydration."
        ),
    },
    {
        "test_name": "Calcium",
        "aliases": ["Ca", "Serum Calcium", "Total Calcium"],
        "unit": "mg/dL",
        "male_min": 8.5,
        "male_max": 10.2,
        "female_min": 8.5,
        "female_max": 10.2,
        "description": (
            "Calcium is critical for bones, muscle contraction, and blood clotting. "
            "Abnormal levels can point to kidney disease, parathyroid issues, or bone disorders."
        ),
    },
    {
        "test_name": "BUN",
        "aliases": ["Blood Urea Nitrogen", "Urea Nitrogen", "Urea"],
        "unit": "mg/dL",
        "male_min": 7.0,
        "male_max": 20.0,
        "female_min": 7.0,
        "female_max": 20.0,
        "description": (
            "Blood Urea Nitrogen measures kidney function by analyzing urea levels. "
            "High levels suggest impaired kidney function, dehydration, or high protein intake."
        ),
    },
    {
        "test_name": "Total Bilirubin",
        "aliases": ["Bili", "Bilirubin Total", "Bilirubin", "Total Bili"],
        "unit": "mg/dL",
        "male_min": 0.1,
        "male_max": 1.2,
        "female_min": 0.1,
        "female_max": 1.2,
        "description": (
            "Bilirubin is produced during the normal breakdown of red blood cells. "
            "High levels can cause jaundice and indicate liver dysfunction or bile duct blockages."
        ),
    },
    {
        "test_name": "Alkaline Phosphatase",
        "aliases": ["ALP", "Alk Phos", "Alkaline Phos"],
        "unit": "U/L",
        "male_min": 44.0,
        "male_max": 147.0,
        "female_min": 44.0,
        "female_max": 147.0,
        "description": (
            "ALP is an enzyme found in liver, bile ducts, and bones. High levels "
            "commonly indicate liver disease, blocked bile ducts, or bone conditions."
        ),
    },
    {
        "test_name": "Albumin",
        "aliases": ["Alb", "Serum Albumin"],
        "unit": "g/dL",
        "male_min": 3.4,
        "male_max": 5.4,
        "female_min": 3.4,
        "female_max": 5.4,
        "description": (
            "Albumin is a protein synthesized by the liver that prevents fluid leakage. "
            "Low levels indicate nutritional deficiency, liver damage, or kidney disease."
        ),
    },
    {
        "test_name": "Vitamin B12",
        "aliases": ["Cobalamin", "B12", "Cyanocobalamin"],
        "unit": "pg/mL",
        "male_min": 200.0,
        "male_max": 900.0,
        "female_min": 200.0,
        "female_max": 900.0,
        "description": (
            "Vitamin B12 is essential for DNA synthesis, nerve health, and red blood cell production. "
            "Deficiency can cause megaloblastic anemia and neuropathy."
        ),
    },
    {
        "test_name": "CRP",
        "aliases": ["C-Reactive Protein", "hs-CRP", "High-Sensitivity CRP"],
        "unit": "mg/L",
        "male_min": 0.0,
        "male_max": 3.0,
        "female_min": 0.0,
        "female_max": 3.0,
        "description": (
            "C-Reactive Protein increases during general inflammation or active infections. "
            "Elevated levels are markers for chronic inflammatory conditions and cardiovascular risk."
        ),
    },
    {
        "test_name": "MCV",
        "aliases": ["Mean Corpuscular Volume", "MCV Count"],
        "unit": "fL",
        "male_min": 80.0,
        "male_max": 100.0,
        "female_min": 80.0,
        "female_max": 100.0,
        "description": (
            "MCV measures the average size of red blood cells. High MCV suggests "
            "macrocytic anemia (e.g., Vitamin B12 or Folate deficiency); low MCV suggests microcytic anemia (e.g., Iron deficiency)."
        ),
    },
    {
        "test_name": "MCH",
        "aliases": ["Mean Corpuscular Hemoglobin", "MCH Count"],
        "unit": "pg",
        "male_min": 27.0,
        "male_max": 33.0,
        "female_min": 27.0,
        "female_max": 33.0,
        "description": (
            "MCH measures the average amount of hemoglobin inside a single red blood cell. "
            "It fluctuates in parallel with MCV and is useful in determining the type of anemia."
        ),
    },
    {
        "test_name": "MCHC",
        "aliases": ["Mean Corpuscular Hemoglobin Concentration"],
        "unit": "g/dL",
        "male_min": 32.0,
        "male_max": 36.0,
        "female_min": 32.0,
        "female_max": 36.0,
        "description": (
            "MCHC measures the average concentration of hemoglobin inside red blood cells. "
            "Low levels indicate hypochromic anemia (such as iron deficiency)."
        ),
    },
    {
        "test_name": "RDW",
        "aliases": ["Red Cell Distribution Width", "RDW-CV", "RDW-SD"],
        "unit": "%",
        "male_min": 11.0,
        "male_max": 15.0,
        "female_min": 11.0,
        "female_max": 15.0,
        "description": (
            "RDW measures the variation in red blood cell size. High variation (anisocytosis) "
            "is an early sign of iron, B12, or folate deficiency anemias."
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

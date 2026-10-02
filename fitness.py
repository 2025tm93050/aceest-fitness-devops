"""Core business logic for ACEest Fitness & Gym.

Pure functions only (no Flask, no database) so they are easy to unit test.
Ported from the legacy Tkinter desktop app (see legacy/aceest_desktop.py).
"""

import random
from datetime import date

PROGRAMS = {
    "FL": {
        "name": "Fat Loss",
        "calorie_factor": 22,
        "workout": [
            "Mon: 5x5 Back Squat + AMRAP",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: 10RFT Deadlifts/Box Jumps",
            "Fri: 30min Active Recovery",
        ],
        "diet": [
            "B: 3 Egg Whites + Oats Idli",
            "L: Grilled Chicken + Brown Rice",
            "D: Fish Curry + Millet Roti",
        ],
        "templates": ["Full Body HIIT", "Circuit Training", "Cardio + Weights"],
    },
    "MG": {
        "name": "Muscle Gain",
        "calorie_factor": 35,
        "workout": [
            "Mon: Squat 5x5",
            "Tue: Bench 5x5",
            "Wed: Deadlift 4x6",
            "Thu: Front Squat 4x8",
            "Fri: Incline Press 4x10",
            "Sat: Barbell Rows 4x10",
        ],
        "diet": [
            "B: 4 Eggs + PB Oats",
            "L: Chicken Biryani (250g Chicken)",
            "D: Mutton Curry + Jeera Rice",
        ],
        "templates": ["Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"],
    },
    "BG": {
        "name": "Beginner",
        "calorie_factor": 26,
        "workout": [
            "Circuit Training: Air Squats, Ring Rows, Push-ups",
            "Focus: Technique Mastery & Form (90% Threshold)",
        ],
        "diet": [
            "Balanced Tamil Meals: Idli-Sambar, Rice-Dal, Chapati",
            "Protein: 120g/day",
        ],
        "templates": ["Full Body 3x/week", "Light Strength + Mobility"],
    },
}

WORKOUT_TYPES = ("Strength", "Hypertrophy", "Cardio", "Mobility")


def get_program(code):
    """Return the program for a code like 'FL' (case-insensitive), or None."""
    if not isinstance(code, str):
        return None
    return PROGRAMS.get(code.strip().upper())


def calculate_calories(weight_kg, program_code):
    """Daily calorie target = body weight (kg) x program calorie factor."""
    program = get_program(program_code)
    if program is None:
        raise ValueError(f"Unknown program: {program_code}")
    if weight_kg is None or weight_kg <= 0:
        raise ValueError("Weight must be a positive number")
    return int(weight_kg * program["calorie_factor"])


def calculate_bmi(weight_kg, height_cm):
    """Return BMI rounded to 1 decimal place."""
    if not weight_kg or not height_cm or weight_kg <= 0 or height_cm <= 0:
        raise ValueError("Weight and height must be positive numbers")
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def bmi_category(bmi):
    """Return (category, risk note) for a BMI value."""
    if bmi < 18.5:
        return "Underweight", "Potential nutrient deficiency, low energy."
    if bmi < 25:
        return "Normal", "Low risk if active and strong."
    if bmi < 30:
        return "Overweight", "Moderate risk; focus on adherence and progressive activity."
    return "Obese", "Higher risk; prioritize fat loss, consistency, and supervision."


def generate_program(program_code=None, rng=None):
    """Pick a training template, AI-style, for the given (or a random) program."""
    rng = rng or random
    if program_code is None:
        program_code = rng.choice(sorted(PROGRAMS))
    program = get_program(program_code)
    if program is None:
        raise ValueError(f"Unknown program: {program_code}")
    return {
        "program": program_code.strip().upper(),
        "template": rng.choice(program["templates"]),
    }


def average_adherence(values):
    """Average adherence percentage rounded to 1 decimal place (0 if empty)."""
    values = list(values)
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def membership_status(end_date, today=None):
    """Return 'Active', 'Expired' or 'None' based on the membership end date."""
    if not end_date:
        return "None"
    today = today or date.today()
    end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    return "Active" if end >= today else "Expired"

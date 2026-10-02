"""Unit tests for the pure business logic in fitness.py."""

import random
from datetime import date

import pytest

import fitness


class TestPrograms:
    def test_all_three_programs_exist(self):
        assert set(fitness.PROGRAMS) == {"FL", "MG", "BG"}

    @pytest.mark.parametrize("code", ["FL", "fl", " Mg ", "bg"])
    def test_get_program_is_case_insensitive(self, code):
        assert fitness.get_program(code) is not None

    @pytest.mark.parametrize("code", ["XX", "", None, 42])
    def test_get_program_unknown_returns_none(self, code):
        assert fitness.get_program(code) is None

    def test_every_program_has_workout_diet_and_templates(self):
        for program in fitness.PROGRAMS.values():
            assert program["workout"] and program["diet"] and program["templates"]
            assert program["calorie_factor"] > 0


class TestCalories:
    @pytest.mark.parametrize(
        "weight, code, expected",
        [(80, "FL", 1760), (80, "MG", 2800), (80, "BG", 2080), (72.5, "FL", 1595)],
    )
    def test_calories_is_weight_times_factor(self, weight, code, expected):
        assert fitness.calculate_calories(weight, code) == expected

    def test_unknown_program_raises(self):
        with pytest.raises(ValueError, match="Unknown program"):
            fitness.calculate_calories(80, "XX")

    @pytest.mark.parametrize("weight", [0, -5, None])
    def test_invalid_weight_raises(self, weight):
        with pytest.raises(ValueError, match="Weight"):
            fitness.calculate_calories(weight, "FL")


class TestBmi:
    def test_bmi_value(self):
        assert fitness.calculate_bmi(80, 175) == 26.1

    @pytest.mark.parametrize("weight, height", [(0, 175), (80, 0), (-1, 175), (None, 175)])
    def test_bmi_invalid_input_raises(self, weight, height):
        with pytest.raises(ValueError):
            fitness.calculate_bmi(weight, height)

    @pytest.mark.parametrize(
        "bmi, category",
        [
            (17.0, "Underweight"),
            (18.5, "Normal"),
            (24.9, "Normal"),
            (25.0, "Overweight"),
            (29.9, "Overweight"),
            (30.0, "Obese"),
        ],
    )
    def test_bmi_category_boundaries(self, bmi, category):
        assert fitness.bmi_category(bmi)[0] == category


class TestProgramGenerator:
    def test_generated_template_belongs_to_program(self):
        result = fitness.generate_program("MG")
        assert result["program"] == "MG"
        assert result["template"] in fitness.PROGRAMS["MG"]["templates"]

    def test_random_program_when_none_given(self):
        result = fitness.generate_program(rng=random.Random(1))
        assert result["program"] in fitness.PROGRAMS
        assert result["template"] in fitness.PROGRAMS[result["program"]]["templates"]

    def test_seeded_generator_is_repeatable(self):
        first = fitness.generate_program("FL", rng=random.Random(7))
        second = fitness.generate_program("FL", rng=random.Random(7))
        assert first == second

    def test_unknown_program_raises(self):
        with pytest.raises(ValueError):
            fitness.generate_program("XX")


class TestAdherenceAndMembership:
    def test_average_adherence(self):
        assert fitness.average_adherence([80, 90, 95]) == 88.3

    def test_average_adherence_empty(self):
        assert fitness.average_adherence([]) == 0.0

    @pytest.mark.parametrize(
        "end, expected",
        [("2026-10-02", "Active"), ("2026-12-31", "Active"), ("2026-10-01", "Expired"), (None, "None")],
    )
    def test_membership_status(self, end, expected):
        assert fitness.membership_status(end, today=date(2026, 10, 2)) == expected
